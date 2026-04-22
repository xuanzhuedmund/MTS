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
import pickle

from linien_common.common import (
    SpectrumUncorrelatedException,
    check_plot_data,
    combine_error_signal,
    get_lock_point,
)
from linien_server.autolock.algorithm_selection import AutolockAlgorithmSelector
from linien_server.autolock.robust import RobustAutolock
from linien_server.autolock.simple import SimpleAutolock
from linien_server.parameters import Parameters

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Autolock:
    """自动锁频核心类，管理整个自动锁频流程"""

    def __init__(self, control, parameters: Parameters) -> None:
        """
        初始化自动锁频系统

        参数:
        - control: 控制接口，用于与硬件通信
        - parameters: 系统参数对象，包含所有可配置参数
        """
        self.control = control  # 控制接口
        self.parameters = parameters  # 系统参数

        self.first_error_signal = None  # 第一个误差信号，用于作为参考
        self.first_error_signal_rolled = None  # 滚动后的误差信号
        self.parameters.autolock_running.value = False  # 锁频运行状态标志
        self.parameters.autolock_retrying.value = False  # 锁频重试状态标志

        self.should_watch_lock = False  # 是否监控锁频状态
        self._data_listener_added = False  # 数据监听器是否已添加

        self.reset_properties()  # 初始化属性

        self.algorithm = None  # 当前锁频算法实例

    def reset_properties(self):
        """重置锁频相关属性，避免频繁调用导致客户端崩溃"""
        # 检查并重置参数
        if self.parameters.autolock_failed.value:
            self.parameters.autolock_failed.value = False
        if self.parameters.autolock_locked.value:
            self.parameters.autolock_locked.value = False
        if self.parameters.autolock_watching.value:
            self.parameters.autolock_watching.value = False

    def run(
        self,
        x0,
        x1,
        spectrum,
        should_watch_lock: bool = False,
        auto_offset: bool = True,
        additional_spectra=None,
    ) -> None:
        """
        启动自动锁频

        参数:
        - x0, x1: 锁频区域的起始和结束索引，定义要锁定的光谱区域
        - spectrum: 初始光谱数据，作为参考光谱
        - should_watch_lock: 是否监控锁频状态，锁定后持续监控并自动重锁
        - auto_offset: 是否自动调整偏移量，自动调整到中心位置
        - additional_spectra: 额外的光谱数据，用于健壮锁频算法
        """
        self.parameters.autolock_running.value = True  # 设置运行状态为True
        self.parameters.autolock_preparing.value = True  # 设置准备状态为True
        self.parameters.autolock_percentage.value = 0  # 初始化进度为0
        self.parameters.fetch_additional_signals.value = False  # 停止获取额外信号
        self.x0, self.x1 = int(x0), int(x1)  # 转换并保存锁频区域边界
        self.should_watch_lock = should_watch_lock  # 保存是否监控标志

        # 保存初始扫描振幅，用于锁频结束后恢复
        self.parameters.autolock_initial_sweep_amplitude.value = (
            self.parameters.sweep_amplitude.value
        )

        self.additional_spectra = additional_spectra or []  # 初始化额外光谱列表

        # 记录第一个误差信号并提取关键特征
        (
            self.first_error_signal,
            self.first_error_signal_rolled,
            self.line_width,
            self.peak_idxs,
        ) = self.record_first_error_signal(spectrum, auto_offset)

        try:
            # 创建算法选择器，根据信号特性选择合适的锁频算法
            self.autolock_mode_detector = AutolockAlgorithmSelector(
                self.parameters.autolock_mode_preference.value,
                spectrum,
                additional_spectra,
                self.line_width,
            )

            # 如果算法选择已完成，立即启动锁频
            if self.autolock_mode_detector.done:
                self.start_autolock(self.autolock_mode_detector.mode)

        except SpectrumUncorrelatedException:
            # 处理光谱不相关的异常，这可能在additional_spectra包含不相关数据时发生
            logger.exception("Error while starting autolock")
            self.parameters.autolock_failed.value = True  # 设置失败标志
            self.exposed_stop()  # 停止锁频过程

        # 添加数据监听器，监听新的光谱数据
        self.add_data_listener()

    def start_autolock(self, mode):
        """
        启动指定模式的锁频算法

        参数:
        - mode: 锁频模式，决定使用哪种锁频算法
        """
        logger.debug(f"Start autolock with mode {mode}")
        self.parameters.autolock_mode.value = mode  # 保存当前锁频模式

        # 根据模式选择并初始化对应的锁频算法
        self.algorithm = [None, RobustAutolock, SimpleAutolock][mode](
            self.control,
            self.parameters,
            self.first_error_signal,
            self.first_error_signal_rolled,
            self.peak_idxs[0],
            self.peak_idxs[1],
            additional_spectra=self.additional_spectra,
        )

    def add_data_listener(self):
        """添加数据监听器，监听光谱数据更新"""
        if not self._data_listener_added:
            self._data_listener_added = True
            self.parameters.to_plot.add_callback(self.react_to_new_spectrum)

    def remove_data_listener(self) -> None:
        """移除数据监听器"""
        self._data_listener_added = False
        self.parameters.to_plot.remove_callback(self.react_to_new_spectrum)

    def react_to_new_spectrum(self, plot_data: bytes) -> None:
        """
        响应新的光谱数据，执行锁频逻辑

        首次执行时记录参考光谱，当自动锁频接近目标线时，
        计算光谱与参考光谱的相关函数并调整激光电流使目标线居中。
        完成后开启真正的锁频，一段时间后验证锁频效果。
        如果需要自动重锁，在锁频后持续监控控制和误差信号。
        """
        if self.parameters.pause_acquisition.value:  # 如果采集已暂停，直接返回
            return

        if plot_data is None or not self.parameters.autolock_running.value:
            return

        plot_data_unpickled = pickle.loads(plot_data)  # 反序列化光谱数据
        if plot_data_unpickled is None:
            return

        is_locked = self.parameters.lock.value  # 获取当前锁频状态

        # 检查plot_data是否包含所需信息
        if not check_plot_data(is_locked, plot_data_unpickled):
            return

        try:
            if not is_locked:
                # 组合误差信号
                combined_error_signal = combine_error_signal(
                    (
                        plot_data_unpickled["error_signal_1"],
                        plot_data_unpickled.get("error_signal_2"),
                    ),
                    self.parameters.dual_channel.value,
                    self.parameters.channel_mixing.value,
                    self.parameters.combined_offset.value,
                )

                # 处理算法选择器
                if (
                    self.autolock_mode_detector is not None
                    and not self.autolock_mode_detector.done
                ):
                    # 将新光谱发送给算法选择器
                    self.autolock_mode_detector.handle_new_spectrum(
                        combined_error_signal
                    )
                    self.additional_spectra.append(combined_error_signal)

                    if self.autolock_mode_detector.done:
                        # 算法选择完成，启动锁频
                        self.start_autolock(self.autolock_mode_detector.mode)
                    else:
                        return

                # 将光谱数据发送给当前锁频算法处理
                if self.algorithm is not None:
                    return self.algorithm.handle_new_spectrum(combined_error_signal)

            else:
                # 已锁定状态，监控锁频效果
                error_signal = plot_data_unpickled["error_signal"]
                control_signal = plot_data_unpickled["control_signal"]

                return self.after_lock(
                    error_signal,
                    control_signal,
                    plot_data_unpickled.get("slow_control_signal"),
                )

        except Exception:
            logger.exception("Error while handling new spectrum")
            self.parameters.autolock_failed.value = True  # 设置失败标志
            self.exposed_stop()  # 停止锁频过程

    def record_first_error_signal(self, error_signal, auto_offset):
        """
        记录第一个误差信号并提取锁频特征

        参数:
        - error_signal: 误差信号数据
        - auto_offset: 是否自动调整偏移

        返回:
        - error_signal: 调整后的误差信号
        - error_signal_rolled: 滚动后的误差信号
        - line_width: 线宽
        - peak_idxs: 峰值索引
        """
        # 获取锁频点和相关参数
        (
            mean_signal,
            target_slope_rising,
            target_zoom,
            error_signal_rolled,
            line_width,
            peak_idxs,
        ) = get_lock_point(error_signal, self.x0, self.x1)

        self.central_y = int(mean_signal)  # 记录中心位置

        if auto_offset:
            # 自动调整偏移，将信号中心对齐到零点
            self.control.exposed_pause_acquisition()  # 暂停采集
            self.parameters.combined_offset.value = -1 * self.central_y  # 设置偏移
            error_signal -= self.central_y  # 调整误差信号
            error_signal_rolled -= self.central_y  # 调整滚动后的信号
            self.additional_spectra = [
                s - self.central_y for s in self.additional_spectra
            ]
            self.control.exposed_write_registers()  # 写入寄存器
            self.control.exposed_continue_acquisition()  # 恢复采集

        self.parameters.target_slope_rising.value = target_slope_rising  # 设置目标斜率
        self.control.exposed_write_registers()  # 写入寄存器

        return error_signal, error_signal_rolled, line_width, peak_idxs

    def after_lock(self, error_signal, control_signal, slow_out):
        """
        锁频完成后的处理

        参数:
        - error_signal: 误差信号
        - control_signal: 控制信号
        - slow_out: 慢速输出信号
        """
        logger.debug("after lock")
        self.parameters.autolock_locked.value = True  # 设置已锁定标志

        self.remove_data_listener()  # 移除数据监听器
        self.parameters.autolock_running.value = False  # 设置运行状态为False

        self.algorithm.after_lock()  # 调用算法的锁频后处理

    def relock(self):
        """
        使用第一次锁频时记录的参考光谱重新锁频

        当锁定丢失时，调用此方法尝试重新锁定
        """
        # 检查并设置参数
        if not self.parameters.autolock_running.value:
            self.parameters.autolock_running.value = True
        if not self.parameters.autolock_retrying.value:
            self.parameters.autolock_retrying.value = True

        self.reset_properties()  # 重置属性
        self._reset_scan()  # 重置扫描

        # 添加监听器，监听新的光谱数据并尝试重新锁频
        self.add_data_listener()

    def exposed_stop(self) -> None:
        """中止任何锁频操作，重置所有状态"""
        self.parameters.autolock_preparing.value = False
        self.parameters.autolock_percentage.value = 0
        self.parameters.autolock_running.value = False
        self.parameters.autolock_locked.value = False
        self.parameters.autolock_watching.value = False
        self.parameters.fetch_additional_signals.value = True
        self.remove_data_listener()

        self._reset_scan()  # 重置扫描
        self.parameters.task.value = None  # 清除任务

    def _reset_scan(self):
        """重置扫描到初始状态"""
        self.control.exposed_pause_acquisition()  # 暂停采集

        # 恢复初始扫描振幅
        self.parameters.sweep_amplitude.value = (
            self.parameters.autolock_initial_sweep_amplitude.value
        )
        self.control.exposed_start_sweep()  # 启动扫描

        self.control.exposed_continue_acquisition()  # 恢复采集
