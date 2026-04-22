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

import logging
from time import time

import numpy as np
from linien_common.common import (
    AUTOLOCK_MAX_N_INSTRUCTIONS,
    SpectrumUncorrelatedException,
    determine_shift_by_correlation,
)
from linien_server.autolock.utils import (
    crop_spectra_to_same_view,
    get_all_peaks,
    get_diff_at_time_scale,
    get_lock_region,
    get_target_peak,
    get_time_scale,
    sign,
    sum_up_spectrum,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class LockPositionNotFound(Exception):
    """锁频位置未找到异常，当无法确定锁频位置时抛出"""
    pass


class UnableToFindDescription(Exception):
    """无法找到锁频描述异常，当无法生成有效的锁频指令时抛出"""
    pass


class RobustAutolock:
    """
    健壮自动锁频算法类

    适用于信号抖动较大的系统。通过收集多个光谱数据，
    分析光谱特征并生成一系列锁频指令，FPGA根据这些指令
    在扫描过程中逐步逼近并锁定目标位置。
    """

    def __init__(
        self,
        control,
        parameters,
        first_error_signal,
        first_error_signal_rolled,
        x0,
        x1,
        N_spectra_required=5,
        additional_spectra=None,
    ):
        """
        初始化健壮锁频算法

        参数:
        - control: 控制接口，用于与硬件通信
        - parameters: 系统参数对象
        - first_error_signal: 第一个误差信号，作为参考光谱
        - first_error_signal_rolled: 滚动后的误差信号
        - x0, x1: 锁频区域的起始和结束索引
        - N_spectra_required: 需要的光谱数量，默认为5
        - additional_spectra: 额外的光谱数据
        """
        self.control = control
        self.parameters = parameters

        self.first_error_signal = first_error_signal
        self.x0 = x0
        self.x1 = x1

        self.N_spectra_required = N_spectra_required  # 需要的光谱数量

        self.spectra = [first_error_signal]  # 光谱列表

        self._done = False  # 是否完成锁频
        self._error_counter = 0  # 错误计数器

        if additional_spectra is not None:
            # 处理额外的光谱数据，最新的光谱优先处理
            additional_spectra = list(reversed(additional_spectra))
            for additional_spectrum in additional_spectra:
                self.handle_new_spectrum(additional_spectrum)

    def handle_new_spectrum(self, spectrum):
        """
        处理新的光谱数据

        收集足够的光谱后，计算锁频指令并启动锁频。

        参数:
        - spectrum: 新采集的光谱数据
        """
        if self._done:  # 已经完成锁频，直接返回
            return

        logger.debug("handle new spectrum")
        try:
            # 检查光谱与参考光谱的相关性
            determine_shift_by_correlation(1, self.first_error_signal, spectrum)
        except SpectrumUncorrelatedException:
            logger.warning("skipping spectrum because it is not correlated")
            self._error_counter += 1
            if self._error_counter > 2:  # 连续不相关超过2次，抛出异常
                raise

            return

        self.spectra.append(spectrum)  # 添加光谱到列表
        # 更新进度百分比
        self.parameters.autolock_percentage.value = int(
            round((len(self.spectra) / self.N_spectra_required) * 100)
        )

        if len(self.spectra) == self.N_spectra_required:
            logger.debug("enough spectra!, calculate")

            # 计算锁频指令
            t1 = time()
            description, final_wait_time, time_scale = calculate_autolock_instructions(
                self.spectra, (self.x0, self.x1)
            )
            t2 = time()
            dt = t2 - t1
            logger.debug(f"Calculation of autolock description took {dt}")

            # 设置超时：如果锁频在一定时间内未完成，抛出错误
            self.setup_timeout()

            # 首先重置锁频状态
            self.parameters.lock.value = False
            self.control.exposed_write_registers()

            # 设置锁频参数
            self.parameters.autolock_time_scale.value = time_scale
            self.parameters.autolock_instructions.value = description
            self.parameters.autolock_final_wait_time.value = final_wait_time

            self.control.exposed_write_registers()

            # 启动锁频
            self.parameters.lock.value = True
            self.control.exposed_write_registers()

            self.parameters.autolock_preparing.value = False

            self._done = True  # 标记为已完成

        else:
            logger.error(
                "Not enough spectra collected:"
                f"{len(self.spectra)} of {self.N_spectra_required}"
            )

    def setup_timeout(self, N_acquisitions_to_wait=5):
        """
        设置锁频超时检测

        健壮锁频将指令编程到FPGA，FPGA根据指令执行锁频。
        如果FPGA无法锁定，超时机制会检测到并报告错误。

        参数:
        - N_acquisitions_to_wait: 等待的采集次数
        """
        self._timeout_start_time = time()
        # 计算超时时间 = 采集次数 * 2 * 单次扫描时间
        self._timeout_time_to_wait = (
            N_acquisitions_to_wait
            * 2
            * sweep_speed_to_time(self.parameters.sweep_speed.value)
        )

        # 添加超时检查回调
        self.parameters.ping.add_callback(self.check_for_timeout, call_immediately=True)

    def check_for_timeout(self, ping):
        """
        检查是否超时

        如果等待时间超过设定值，停止锁频并报告错误。

        参数:
        - ping: ping信号（用于触发检查）
        """
        min_time_to_wait = 5  # 最小等待时间5秒

        if time() - self._timeout_start_time > max(
            self._timeout_time_to_wait, min_time_to_wait
        ):
            logger.error("Waited too long for autolock! Aborting")
            self.stop_timeout()  # 停止超时检测
            self.parameters.task.value.exposed_stop()  # 停止任务

    def stop_timeout(self):
        """停止超时检查"""
        self.parameters.ping.remove_callback(self.check_for_timeout)

    def after_lock(self):
        """锁频完成后的处理，停止超时检测"""
        self.stop_timeout()


def calculate_autolock_instructions(spectra_with_jitter, target_idxs):
    """
    计算自动锁频指令序列

    该函数分析多个带抖动的光谱数据，生成一系列锁频指令。
    每个指令包含两个值：(wait_for, threshold)，表示在检测到
    峰值前需要等待的时间步长和触发锁频的信号阈值。

    参数:
    - spectra_with_jitter: 包含抖动的光谱列表
    - target_idxs: 目标峰值的索引范围 (起始索引, 结束索引)

    返回:
    - description: 锁频指令列表
    - final_wait_time: 最终等待时间
    - time_scale: 时间尺度参数
    """
    # 裁剪光谱到相同的视图，去除边缘无效数据
    spectra, crop_left = crop_spectra_to_same_view(spectra_with_jitter)

    # 调整目标索引
    target_idxs = [idx - crop_left for idx in target_idxs]

    # 计算时间尺度（多个光谱的平均值）
    time_scale = int(
        round(np.mean([get_time_scale(spectrum, target_idxs) for spectrum in spectra]))
    )

    logger.debug(f"x scale is {time_scale}")

    # 准备光谱并获取峰值
    prepared_spectrum = get_diff_at_time_scale(sum_up_spectrum(spectra[0]), time_scale)
    peaks = get_all_peaks(prepared_spectrum, target_idxs)
    y_scale = peaks[0][1]

    # 获取锁频区域
    lock_regions = [get_lock_region(spectrum, target_idxs) for spectrum in spectra]

    # 尝试不同的容差因子，找到最优的锁频参数
    for tolerance_factor in [0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5]:
        logger.debug(f"Try out tolerance {tolerance_factor}")
        # 根据容差因子调整峰值高度
        peaks_filtered = [
            (peak_position, peak_height * tolerance_factor)
            for peak_position, peak_height in peaks
        ]
        # 重要的是在上一行之后进行过滤，因为上一行会缩小值
        peaks_filtered = [
            (peak_position, peak_height)
            for peak_position, peak_height in peaks_filtered
            if abs(peak_height) > abs(y_scale * (1 - tolerance_factor))
        ]

        # 计算最终等待时间（检测到峰值太早，需要等待校正）
        target_peak_described_height = peaks_filtered[0][1]
        target_peak_idx = get_target_peak(prepared_spectrum, target_idxs)
        current_idx = target_peak_idx
        while True:
            current_idx -= 1
            if np.abs(prepared_spectrum[current_idx]) < np.abs(
                target_peak_described_height
            ):
                break
        final_wait_time = target_peak_idx - current_idx
        logger.debug(f"final wait time is {final_wait_time} samples")

        # 生成锁频指令序列
        description = []

        last_peak_position = 0
        for peak_position, peak_height in list(reversed(peaks_filtered)):
            # 每个指令包含：峰值间隔和触发阈值
            description.append(
                (int(0.9 * (peak_position - last_peak_position)), int(peak_height))
            )
            last_peak_position = peak_position

        # 测试描述是否对每个记录的光谱都有效
        does_work = True
        for spectrum, lock_region in zip(spectra, lock_regions):
            try:
                lock_position = get_lock_position_from_autolock_instructions(
                    spectrum, description, time_scale, spectra[0], final_wait_time
                )
                if not lock_region[0] <= lock_position <= lock_region[1]:
                    raise LockPositionNotFound()

            except LockPositionNotFound:
                does_work = False

        if does_work:  # 找到有效参数，退出循环
            break
    else:
        # 无法找到有效参数
        raise UnableToFindDescription()

    # 检查指令长度是否超限
    if len(description) > AUTOLOCK_MAX_N_INSTRUCTIONS:
        logger.warning(f"Autolock description too long. Cropping! {description}")
        description = description[-AUTOLOCK_MAX_N_INSTRUCTIONS:]

    logger.debug(f"Description is {description}")
    return description, final_wait_time, time_scale


def get_lock_position_from_autolock_instructions(
    spectrum, description, time_scale, initial_spectrum, final_wait_time
):
    """
    根据锁频指令获取锁频位置

    该函数模拟FPGA执行锁频指令的过程，
    返回理论上锁频应该发生的位置。

    参数:
    - spectrum: 输入光谱
    - description: 锁频指令列表
    - time_scale: 时间尺度参数
    - initial_spectrum: 初始参考光谱
    - final_wait_time: 最终等待时间

    返回:
    - lock_position: 锁频位置索引

    异常:
    - LockPositionNotFound: 无法找到有效的锁频位置
    """
    # 对光谱进行求和和时间尺度缩放
    summed = sum_up_spectrum(spectrum)
    summed_xscaled = get_diff_at_time_scale(summed, time_scale)

    description_idx = 0  # 当前指令索引
    last_detected_peak = 0  # 上次检测到峰值的位置

    # 遍历光谱，检测峰值
    for idx, value in enumerate(summed_xscaled):
        wait_for, current_threshold = description[description_idx]

        # 检查是否满足触发条件
        if (
            sign(value) == sign(current_threshold)  # 符号相同
            and abs(value) >= abs(current_threshold)  # 幅度足够
            and idx - last_detected_peak > wait_for  # 间隔足够
        ):
            description_idx += 1  # 移动到下一个指令
            last_detected_peak = idx

            if description_idx == len(description):  # 所有指令执行完毕
                # 返回锁频位置 = 当前索引 + 最终等待时间
                return idx + final_wait_time

    raise LockPositionNotFound()  # 无法找到锁频位置


def sweep_speed_to_time(sweep_speed):
    """
    将扫描速度转换为扫描持续时间

    扫描速度是参数系统中的任意单位，此函数将其转换为
    扫描持续时间（以秒为单位）。

    参数:
    - sweep_speed: 扫描速度参数值

    返回:
    - duration: 扫描持续时间（秒）
    """
    f_real = 3.8e3 / (2**sweep_speed)  # 计算实际频率
    duration = 1 / f_real  # 计算周期
    return duration
