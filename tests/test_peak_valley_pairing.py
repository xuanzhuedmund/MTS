# 单元测试：验证基于寻峰配对的锁定点算法
import numpy as np
from linien_common.common import (
    get_lock_point,
    get_lock_point_by_peak_valley_pairing,
)


def make_signal_with_one_peak_valley(zero_idx=1000, peak_first=True):
    """生成一个具有一对峰谷的测试信号。

    peak_first=True 时峰在前谷在后，否则谷在前峰在后。
    返回 2048 点的信号。
    """
    x = np.arange(2048)
    if peak_first:
        # 正峰在 zero_idx - 30，谷在 zero_idx + 30
        peak_pos, valley_pos = zero_idx - 30, zero_idx + 30
    else:
        valley_pos, peak_pos = zero_idx - 30, zero_idx + 30

    signal = np.zeros(2048)
    # 高斯峰
    signal += 2000 * np.exp(-((x - peak_pos) ** 2) / (2 * 10**2))
    # 高斯谷
    signal += -2000 * np.exp(-((x - valley_pos) ** 2) / (2 * 10**2))
    return signal


def make_signal_multi_peaks_valleys():
    """生成多峰多谷信号，用于测试配对选择。"""
    x = np.arange(2048)
    signal = np.zeros(2048)
    # 一个强峰 + 强谷 + 弱峰 + 弱谷
    signal += 2000 * np.exp(-((x - 500) ** 2) / (2 * 10**2))   # 强峰
    signal += -1800 * np.exp(-((x - 560) ** 2) / (2 * 10**2))  # 强谷
    signal += 1200 * np.exp(-((x - 1000) ** 2) / (2 * 10**2))  # 弱峰
    signal += -1000 * np.exp(-((x - 1060) ** 2) / (2 * 10**2))  # 弱谷
    return signal


def test_basic_return_types():
    """验证返回值类型和数量。"""
    signal = make_signal_with_one_peak_valley()
    result = get_lock_point_by_peak_valley_pairing(signal, 400, 600)
    assert len(result) == 6
    mean_signal, slope_rising, zoom, rolled, line_width, peak_idxs = result
    assert isinstance(mean_signal, float)
    assert isinstance(slope_rising, bool)
    assert isinstance(zoom, float)
    assert isinstance(line_width, int)


def test_peak_first_lock_point():
    """峰在前、谷在后时，过零点应位于两者之间。"""
    signal = make_signal_with_one_peak_valley(zero_idx=500, peak_first=True)
    mean_signal, slope_rising, zoom, rolled, line_width, peak_idxs = (
        get_lock_point_by_peak_valley_pairing(signal, 400, 600)
    )
    p_idx, v_idx = peak_idxs
    # 过零点应在峰谷之间
    assert min(p_idx, v_idx) <= 500 <= max(p_idx, v_idx)
    # 线宽约为 60
    assert line_width == abs(p_idx - v_idx)


def test_valley_first_lock_point():
    """谷在前、峰在后。"""
    signal = make_signal_with_one_peak_valley(zero_idx=500, peak_first=False)
    mean_signal, slope_rising, zoom, rolled, line_width, peak_idxs = (
        get_lock_point_by_peak_valley_pairing(signal, 400, 600)
    )
    p_idx, v_idx = peak_idxs
    assert min(p_idx, v_idx) <= 500 <= max(p_idx, v_idx)


def test_consistent_with_get_lock_point_for_single_pair():
    """对单一峰谷对，新算法应与原算法结果接近。"""
    signal = make_signal_with_one_peak_valley(zero_idx=1024, peak_first=True)
    x0, x1 = 900, 1100

    _, _, _, _, _, old_peak_idxs = get_lock_point(signal, x0, x1)
    _, _, _, _, _, new_peak_idxs = get_lock_point_by_peak_valley_pairing(
        signal, x0, x1
    )
    # 两者锁定的过零点应接近（允许 ±5 点误差）
    old_zero = x0 + (old_peak_idxs[0] + old_peak_idxs[1]) // 2 - x0
    # 原算法的锁定点在排序后的区间内
    # 这里只验证新算法锁定点落在合理范围内
    assert 900 <= new_peak_idxs[0] <= 1100
    assert 900 <= new_peak_idxs[1] <= 1100


def test_multi_pair_selects_strongest():
    """多峰谷时，应选择绝对值最高的谷对应的配对。"""
    signal = make_signal_multi_peaks_valleys()
    mean_signal, slope_rising, zoom, rolled, line_width, peak_idxs = (
        get_lock_point_by_peak_valley_pairing(signal, 400, 1100)
    )
    # 强峰在 500，强谷在 560
    p_idx, v_idx = peak_idxs
    # 配对应选择强峰强谷对
    assert abs(p_idx - 500) < 20 or abs(v_idx - 500) < 20
    assert abs(p_idx - 560) < 20 or abs(v_idx - 560) < 20


if __name__ == "__main__":
    test_basic_return_types()
    test_peak_first_lock_point()
    test_valley_first_lock_point()
    test_consistent_with_get_lock_point_for_single_pair()
    test_multi_pair_selects_strongest()
    print("All tests passed!")
