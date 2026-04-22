# This file is part of Linien and based on redpid.
#
# Copyright (C) 2016-2024 Linien Authors (https://github.com/linien-org/linien#license)
#
# Linien is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Linien is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Linien.  If not, see <http://www.gnu.org/licenses/>.

from linien_common.common import AUTOLOCK_MAX_N_INSTRUCTIONS, AutolockMode
from migen import Array, If, Module, Signal, bits_for
from misoc.interconnect.csr import AutoCSR, CSRStatus, CSRStorage

from .autolock_utils import SumDiffCalculator

# FPGA健壮锁频算法的延迟周期数，用于校正指令触发延迟
ROBUST_AUTOLOCK_FPGA_DELAY = 3


class FPGAAutolock(Module, AutoCSR):
    """
    FPGA自动锁频管理模块

    该模块处理FPGA上的自动锁频逻辑，是服务器端Autolock类的硬件对应部分。
    根据autolock_mode参数，选择使用快速锁频或健壮锁频算法。
    通过设置request_lock信号触发锁频，一旦锁定成功，lock_running信号变为高电平。
    """

    def __init__(self, width=14, N_points=16383, max_delay=16383):
        """
        初始化FPGA自动锁频模块

        参数:
        - width: 数据位宽，默认为14位
        - N_points: 采样点数量，默认为16383
        - max_delay: 最大延迟，默认为16383
        """
        # 创建健壮锁频和快速锁频子模块
        self.submodules.robust = RobustAutolock(max_delay=max_delay)
        self.submodules.fast = SimpleAutolock(width=width)

        # 创建CSR寄存器
        self.request_lock = CSRStorage()  # 锁频请求信号
        self.autolock_mode = CSRStorage(2)  # 锁频模式选择
        self.lock_running = CSRStatus()  # 锁频运行状态

        # 连接请求信号到子模块
        self.comb += [
            self.fast.request_lock.eq(self.request_lock.storage),
            self.robust.request_lock.eq(self.request_lock.storage),
        ]

        # 同步逻辑：控制lock_running状态
        self.sync += [
            # 如果request_lock为低，lock_running也为低
            If(
                ~self.request_lock.storage,
                self.lock_running.status.eq(0),
            ),
            # 如果request_lock为高，快速锁频触发，且模式为SIMPLE，lock_running为高
            If(
                self.request_lock.storage
                & self.fast.turn_on_lock
                & (self.autolock_mode.storage == AutolockMode.SIMPLE),
                self.lock_running.status.eq(1),
            ),
            # 如果request_lock为高，健壮锁频触发，且模式为ROBUST，lock_running为高
            If(
                self.request_lock.storage
                & self.robust.turn_on_lock
                & (self.autolock_mode.storage == AutolockMode.ROBUST),
                self.lock_running.status.eq(1),
            ),
        ]


class SimpleAutolock(Module, AutoCSR):
    """
    FPGA快速锁频模块

    快速锁频的工作原理很简单：等待扫描到达某个特定位置，然后触发锁频。
    这种方法适用于信号抖动较小的系统。
    """

    def __init__(self, width=14):
        """
        初始化快速锁频模块

        参数:
        - width: 数据位宽，默认为14位
        """
        # 注意：PID不是由request_lock信号直接启动的
        # 相反，request_lock会排队运行，然后在扫描到达零目标位置时启动
        self.request_lock = Signal()  # 锁频请求信号
        self.turn_on_lock = Signal()  # 锁频触发信号
        self.sweep_value = Signal((width, True))  # 扫描当前位置值
        self.sweep_step = Signal(width)  # 扫描步长
        self.sweep_up = Signal()  # 扫描方向（向上为真）

        self.target_position = CSRStorage(width)  # 目标位置寄存器
        target_position_signed = Signal((width, True))

        self.comb += [target_position_signed.eq(self.target_position.storage)]

        # 同步逻辑：检测是否应该触发锁频
        self.sync += [
            If(
                ~self.request_lock,
                self.turn_on_lock.eq(0),  # 请求无效时，触发信号为低
            ).Else(
                # 请求有效时，检查以下条件：
                self.turn_on_lock.eq(
                    (
                        # 扫描值在目标位置附近（半步长范围内）
                        self.sweep_value
                        >= target_position_signed - (self.sweep_step >> 1)
                    )
                    & (
                        self.sweep_value
                        <= target_position_signed + 1 + (self.sweep_step >> 1)
                    )
                    # 并且扫描正在向上运行（这是记录光谱的时机）
                    & (self.sweep_up)
                ),
            ),
        ]


class RobustAutolock(Module, AutoCSR):
    """
    FPGA健壮锁频模块

    健壮锁频通过执行一系列锁频指令来实现锁定。
    每条指令包含一个等待时间和一个阈值，用于检测光谱中的峰值。
    当所有峰值都被正确检测后，触发锁频。
    """

    def __init__(self, width=14, N_points=16383, max_delay=16383):
        """
        初始化健壮锁频模块

        参数:
        - width: 数据位宽
        - N_points: 采样点数量
        - max_delay: 最大延迟
        """
        self.init_submodules(width, N_points, max_delay)  # 初始化子模块
        peak_height_bit, x_data_length_bit = self.init_csr(N_points)  # 初始化CSR寄存器
        self.init_inout_signals(width)  # 初始化输入输出信号

        # watching信号：表示自动锁频是否正在积极检测峰值
        # 当请求锁频且扫描在起始位置时，watching被设置为真
        watching = Signal()

        # 以下信号是自动锁频当前正在检测的峰值的属性
        self.current_instruction_idx = Signal(bits_for(AUTOLOCK_MAX_N_INSTRUCTIONS - 1))
        current_peak_height = Signal((peak_height_bit, True))  # 当前峰值高度
        abs_current_peak_height = Signal.like(current_peak_height)  # 峰值高度的绝对值
        current_wait_for = Signal(x_data_length_bit)  # 当前等待时间
        self.comb += [
            # 从CSR寄存器数组中获取当前指令的峰值高度
            current_peak_height.eq(
                Array([peak_height.storage for peak_height in self.peak_heights])[
                    self.current_instruction_idx
                ]
            ),
            # 从CSR寄存器数组中获取当前指令的等待时间
            current_wait_for.eq(
                Array([wait_for.storage for wait_for in self.wait_for])[
                    self.current_instruction_idx
                ]
            ),
        ]

        # waited_for: 检测到上一个峰值后经过的周期数
        waited_for = Signal(bits_for(N_points))
        # final_waited_for: 检测到所有峰值后经过的周期数
        final_waited_for = Signal(bits_for(N_points))

        # sum_diff: 用于峰值检测的信号（差分累加结果）
        sum_diff = Signal((len(self.sum_diff_calculator.output), True))
        abs_sum_diff = Signal.like(sum_diff)
        self.comb += [
            # 连接和差计算器
            self.sum_diff_calculator.writing_data_now.eq(self.writing_data_now),
            self.sum_diff_calculator.restart.eq(self.at_start),
            self.sum_diff_calculator.input.eq(self.input),
            self.sum_diff_calculator.delay_value.eq(self.time_scale.storage),
            sum_diff.eq(self.sum_diff_calculator.output),
        ]

        # 创建各种状态信号
        sign_equal = Signal()  # 当前信号符号是否与目标峰值符号相同
        over_threshold = Signal()  # 当前信号幅度是否超过阈值
        waited_long_enough = Signal()  # 距离上次检测是否已等待足够时间
        all_instructions_triggered = Signal()  # 是否所有指令都已触发（可以锁频）

        self.comb += [
            # 判断符号是否相同
            sign_equal.eq((sum_diff > 0) == (current_peak_height > 0)),
            # 计算绝对值
            If(sum_diff >= 0, abs_sum_diff.eq(sum_diff)).Else(
                abs_sum_diff.eq(-1 * sum_diff)
            ),
            If(
                current_peak_height >= 0,
                abs_current_peak_height.eq(current_peak_height),
            ).Else(abs_current_peak_height.eq(-1 * current_peak_height)),
            # 判断是否超过阈值
            over_threshold.eq(abs_sum_diff >= abs_current_peak_height),
            # 判断等待时间是否足够
            waited_long_enough.eq(waited_for > current_wait_for),
            # 判断是否所有指令都已触发
            all_instructions_triggered.eq(
                self.current_instruction_idx >= self.N_instructions.storage
            ),
            # 锁频触发条件：所有指令触发且最终等待时间足够
            self.turn_on_lock.eq(
                all_instructions_triggered
                & (final_waited_for >= self.final_wait_time.storage)
            ),
        ]

        # 同步逻辑：更新状态
        self.sync += [
            If(
                self.at_start,
                # 在起始位置时，重置计数器和指令索引
                waited_for.eq(0),
                # FPGA健壮锁频算法有延迟注册问题，提供初始偏移
                final_waited_for.eq(ROBUST_AUTOLOCK_FPGA_DELAY),
                self.current_instruction_idx.eq(0),
                # 根据request_lock设置watching状态
                If(self.request_lock, watching.eq(1)).Else(watching.eq(0)),
            ).Else(
                # 不在起始位置
                If(
                    ~self.request_lock,
                    # 如果在扫描运行时禁用了request_lock，禁用watching
                    watching.eq(0),
                ),
                # 如果正在写入数据、指令未全部触发、扫描向上
                If(
                    self.writing_data_now & ~all_instructions_triggered & self.sweep_up,
                    If(
                        # 满足所有检测条件
                        watching & sign_equal & over_threshold & waited_long_enough,
                        # 移动到下一个指令
                        self.current_instruction_idx.eq(
                            self.current_instruction_idx + 1
                        ),
                        waited_for.eq(0),  # 重置等待计数器
                    ).Else(
                        waited_for.eq(waited_for + 1),  # 增加等待计数器
                    ),
                ),
                # 如果正在写入数据、所有指令已触发、扫描向上
                If(
                    self.writing_data_now & all_instructions_triggered & self.sweep_up,
                    final_waited_for.eq(final_waited_for + 1),  # 增加最终等待计数器
                ),
            ),
        ]

        self.signal_out = []
        self.signal_in = []
        self.state_out = [
            watching,
            self.turn_on_lock,
            sign_equal,
            over_threshold,
            waited_long_enough,
        ]
        self.state_in = []

    def init_submodules(self, width, N_points, max_delay):
        """
        初始化子模块

        参数:
        - width: 数据位宽
        - N_points: 采样点数量
        - max_delay: 最大延迟
        """
        self.submodules.sum_diff_calculator = SumDiffCalculator(
            width, N_points, max_delay=max_delay
        )

    def init_csr(self, N_points):
        """
        初始化CSR寄存器

        参数:
        - N_points: 采样点数量

        返回:
        - peak_height_bit: 峰值高度位宽
        - x_data_length_bit: X数据长度位宽
        """
        # CSR存储寄存器
        self.time_scale = CSRStorage(bits_for(N_points))  # 时间尺度
        self.N_instructions = CSRStorage(bits_for(AUTOLOCK_MAX_N_INSTRUCTIONS - 1))  # 指令数量
        self.final_wait_time = CSRStorage(bits_for(N_points))  # 最终等待时间

        # 峰值高度寄存器数组
        peak_height_bit = len(self.sum_diff_calculator.sum_value)
        self.peak_heights = [
            CSRStorage(peak_height_bit, name=f"peak_height_{idx}")
            for idx in range(AUTOLOCK_MAX_N_INSTRUCTIONS)
        ]
        for idx, peak_height in enumerate(self.peak_heights):
            setattr(self, f"peak_height_{idx}", peak_height)

        # 等待时间寄存器数组
        x_data_length_bit = bits_for(N_points)
        self.wait_for = [
            CSRStorage(x_data_length_bit, name=f"wait_for_{idx}")
            for idx in range(AUTOLOCK_MAX_N_INSTRUCTIONS)
        ]
        for idx, wait_for in enumerate(self.wait_for):
            setattr(self, f"wait_for_{idx}", wait_for)

        return peak_height_bit, x_data_length_bit

    def init_inout_signals(self, width):
        """
        初始化输入输出信号

        参数:
        - width: 数据位宽
        """
        # 连接到其他模块的信号
        self.input = Signal((width, True))  # 输入信号
        self.request_lock = Signal()  # 锁频请求
        self.at_start = Signal()  # 扫描是否在起始位置
        self.writing_data_now = Signal()  # 是否正在写入数据
        self.sweep_up = Signal()  # 扫描是否向上
        self.turn_on_lock = Signal()  # 锁频触发信号
