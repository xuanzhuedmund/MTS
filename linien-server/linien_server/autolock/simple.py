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

from linien_common.common import (
    SpectrumUncorrelatedException,
    determine_shift_by_correlation,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class SimpleAutolock:
    """
    简单自动锁频算法类

    基于相关性的光谱自动锁频实现，适用于信号抖动较小的系统。
    通过计算当前光谱与参考光谱之间的相关性来确定偏移量，
    然后直接计算锁频点并启动锁频。
    """

    def __init__(
        self,
        control,
        parameters,
        first_error_signal,
        first_error_signal_rolled,
        x0,
        x1,
        additional_spectra=None,
    ) -> None:
        """
        初始化简单锁频算法

        参数:
        - control: 控制接口，用于与硬件通信
        - parameters: 系统参数对象
        - first_error_signal: 第一个误差信号，作为参考光谱
        - first_error_signal_rolled: 滚动后的误差信号
        - x0, x1: 锁频区域的起始和结束索引
        - additional_spectra: 额外的光谱数据（此算法未使用）
        """
        self.control = control
        self.parameters = parameters

        self.first_error_signal_rolled = first_error_signal_rolled

        self._done = False  # 是否完成锁频
        self._error_counter = 0  # 错误计数器，用于处理不相关光谱

    def handle_new_spectrum(self, spectrum) -> None:
        """
        处理新的光谱数据，执行简单锁频逻辑

        通过相关性计算确定锁频点，然后启动锁频。

        参数:
        - spectrum: 新采集的光谱数据
        """
        if self._done:  # 已经完成锁频，直接返回
            return

        try:
            # 计算当前光谱与参考光谱之间的偏移量
            shift, zoomed_ref, zoomed_err = determine_shift_by_correlation(
                1, self.first_error_signal_rolled, spectrum
            )
        except SpectrumUncorrelatedException:
            # 处理光谱不相关的情况，可能是信号丢失或噪声过大
            self._error_counter += 1
            logger.warning("skipping spectrum because it is not correlated")

            if self._error_counter > 10:  # 连续不相关超过10次，抛出异常
                raise

            return

        # 计算锁频点位置
        lock_point = int(
            round((shift * (-1)) * self.parameters.sweep_amplitude.value * 8191)
        )

        logger.debug(f"lock point is {lock_point}, shift is {shift}")

        # 设置锁频目标位置并启动锁频
        self.parameters.autolock_target_position.value = int(lock_point)
        self.parameters.autolock_preparing.value = False
        self.control.exposed_write_registers()  # 写入寄存器
        self.control.exposed_start_lock()  # 启动锁频

        self._done = True  # 标记为已完成

    def after_lock(self):
        """
        锁频完成后的回调函数

        简单锁频算法在锁频后不需要特殊处理，此方法为空。
        """
        pass
