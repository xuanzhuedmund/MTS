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

from linien_common.common import N_POINTS, AutolockMode, determine_shift_by_correlation

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class AutolockAlgorithmSelector:
    """
    自动锁频算法选择器类

    根据信号抖动特性自动选择合适的锁频算法。
    如果抖动较小（小于线宽的一半），选择简单锁频算法；
    否则选择健壮锁频算法。
    """

    def __init__(
        self,
        mode_preference,
        spectrum,
        additional_spectra,
        line_width,
        N_spectra_required=3,
    ):
        """
        初始化算法选择器

        参数:
        - mode_preference: 模式偏好，可以是AutolockMode中的值或AUTO_DETECT
        - spectrum: 初始光谱数据
        - additional_spectra: 额外的光谱数据列表
        - line_width: 光谱线宽
        - N_spectra_required: 需要的光谱数量，默认为3
        """
        self.done = False  # 是否完成算法选择
        self.mode = None  # 选择的锁频模式
        # 合并初始光谱和额外光谱
        self.spectra = [spectrum] + (additional_spectra or [])
        self.N_spectra_required = N_spectra_required  # 需要的光谱数量
        self.line_width = line_width  # 线宽

        # 如果用户指定了模式偏好，直接使用指定模式
        if mode_preference != AutolockMode.AUTO_DETECT:
            self.mode = mode_preference
            self.done = True
            return

        # 自动检测模式：分析光谱特性选择合适的算法
        self.check()

    def handle_new_spectrum(self, spectrum):
        """
        处理新的光谱数据

        参数:
        - spectrum: 新采集的光谱数据
        """
        self.spectra.append(spectrum)  # 添加新光谱到列表
        self.check()  # 重新检查是否可以选择算法

    def check(self):
        """
        检查是否可以确定锁频模式

        通过分析多个光谱之间的相关性来判断信号抖动程度，
        从而选择合适的锁频算法。
        """
        if self.done:  # 已经完成选择，直接返回
            return True

        # 如果光谱数量不足，无法做出判断
        if len(self.spectra) < self.N_spectra_required:
            return
        else:
            # 以第一个光谱为参考，计算其他光谱与参考的偏移量
            ref = self.spectra[0]
            additional = self.spectra[1:]
            abs_shifts = [
                abs(determine_shift_by_correlation(1, ref, spectrum)[0] * N_POINTS)
                for spectrum in additional
            ]
            max_shift = max(abs_shifts)  # 取最大偏移量
            logger.debug(
                f"jitter / line width ratio: {max_shift / (self.line_width / 2)}"
            )

            # 根据最大偏移与线宽的比例选择算法
            if max_shift <= self.line_width / 2:
                # 抖动较小，选择简单锁频算法
                self.mode = AutolockMode.SIMPLE
            else:
                # 抖动较大，选择健壮锁频算法
                self.mode = AutolockMode.ROBUST

            self.done = True  # 标记为已完成
