# `get_lock_point` 函数调用路线

> 文件位置：`linien-common/linien_common/common.py:212`

---

## 调用关系总览

```
                    ┌─ plot_widget.py:324 (GUI 本地预览)
                    │
get_lock_point ─────┼─ autolock.py:264 (服务器锁频参数计算)
                    │
                    ├─ optimization.py:76 (优化模式)
                    │
                    └─ tests (测试验证)
```

共有 **3 条调用路线** + 1 条测试路线。

---

## `get_lock_point` 与锁频模式的关系

> **关键结论**：`get_lock_point` **不属于简单模式或鲁棒模式**，它是两种模式**共用的前置处理步骤**。

```
Autolock.run(x0, x1, spectrum)
    │
    ├─ record_first_error_signal()
    │      │
    │      └─► get_lock_point()    ← 在这里调用，先于模式选择
    │           返回：mean_signal / target_slope_rising / target_zoom
    │                 rolled_error_signal / line_width / peak_idxs
    │
    ├─ AutolockAlgorithmSelector    ← 利用 line_width 决定后续用哪种模式
    │
    └─ start_autolock(mode)
           │
           ├─ mode=1 → RobustAutolock   (鲁棒模式)
           └─ mode=2 → SimpleAutolock   (简单模式)
```

| 项目 | 说明 |
|------|------|
| **`get_lock_point`** | **共享的前置处理**，不属于简单或鲁棒模式 |
| **调用时机** | 在选择模式**之前**（`autolock.py:111`） |
| **作用** | 提取锁定点特征参数，供后续两种模式使用 |
| **输出 `line_width`** | 直接影响模式选择——`AutolockAlgorithmSelector` 用它判断抖动程度 |

### 两种模式的真正区别

| | SimpleAutolock (简单) | RobustAutolock (鲁棒) |
|--|------|------|
| **运行位置** | CPU | FPGA（预编程指令） |
| **核心方法** | 自相关匹配 | 多光谱峰值检测指令序列 |
| **输入** | `get_lock_point` 的输出 | `get_lock_point` 的输出 |
| **适用场景** | 抖动小 | 抖动大 |

两者都依赖 `get_lock_point` 提供的 `first_error_signal_rolled`（参考光谱）和 `line_width`（线宽），只是后续的**锁定执行策略**不同。

---

## 路线 1：GUI 自动锁频（主流程）

这是最核心的调用路线，`get_lock_point` 被调用两次：GUI 端一次用于预览，服务器端一次用于实际锁频。

```
用户在 GUI 选定锁频区域 (鼠标拖选)
        │
        ▼
PlotWidget.mouseReleaseEvent()
        │  [linien-gui/linien_gui/ui/plot_widget.py:287-326]
        │
        ├──► get_lock_point(combined_error_signal, x0, x)   ← 第1次调用（GUI端预览）
        │    [plot_widget.py:324]
        │    用途：生成 autolock_ref_spectrum，用于实时显示锁定目标线
        │
        ▼
self.control.start_autolock(x0, x1, spectrum)
        │  [plot_widget.py:309]
        │  （通过 rpyc RPC 发送到服务器）
        ▼
Server.exposed_start_autolock(x0, x1, spectrum)
        │  [linien-server/linien_server/server.py:258]
        ▼
Autolock.__init__() → Autolock.run()
        │  [linien-server/linien_server/autolock/autolock.py:36]
        ▼
Autolock.record_first_error_signal(error_signal, auto_offset)
        │  [autolock.py:242]
        │
        ├──► get_lock_point(error_signal, self.x0, self.x1)   ← 第2次调用（服务器端）
        │    [autolock.py:264]
        │    用途：计算真正的锁频参数
        │
        │    返回：
        │      • mean_signal        → 用于自动偏移调整
        │      • target_slope_rising→ 写入参数寄存器
        │      • target_zoom        → 缩放控制
        │      • error_signal_rolled→ 作为参考光谱
        │      • line_width         → 线宽信息
        │      • peak_idxs          → 峰值索引
        ▼
SimpleAutolock 或 RobustAutolock 使用这些参数执行锁频
```

### 关键代码位置

| 步骤 | 文件 | 行号 |
|------|------|------|
| GUI 调用 | `linien-gui/linien_gui/ui/plot_widget.py` | 324 |
| RPC 入口 | `linien-server/linien_server/server.py` | 258 |
| 服务器调用 | `linien-server/linien_server/autolock/autolock.py` | 264 |

---

## 路线 2：GUI 优化模式

用于 spectroscopy 优化，通过逐步逼近提升信号质量。

```
用户在优化面板选择目标区域
        │
        ▼
PlotWidget.mouseReleaseEvent()
        │  [linien-gui/linien_gui/ui/plot_widget.py:303-339]
        │
        ▼
self.control.start_optimization(points, spectrum)
        │  [plot_widget.py:339]
        │  （通过 rpyc RPC 发送到服务器）
        ▼
Server.exposed_start_optimization(x0, x1, spectrum)
        │  [linien-server/linien_server/server.py:280]
        ▼
OptimizeSpectroscopy.__init__()
        │  [linien-server/linien_server/optimization/optimization.py:32]
        ▼
OptimizeSpectroscopy.record_first_error_signal(error_signal)
        │  [optimization.py:68]
        │
        ├──► get_lock_point(error_signal, x0, x1, final_zoom_factor=FINAL_ZOOM_FACTOR)
        │    [optimization.py:76]
        │    用途：计算目标缩放和参考光谱
        │
        │    返回关键参数：
        │      • target_zoom         → 优化目标
        │      • rolled_error_signal → 参考光谱
        │      • mean_signal         → 传给 Approacher
        ▼
Approacher 使用参数执行优化逼近
```

### 关键代码位置

| 步骤 | 文件 | 行号 |
|------|------|------|
| GUI 触发 | `linien-gui/linien_gui/ui/plot_widget.py` | 339 |
| RPC 入口 | `linien-server/linien_server/server.py` | 280 |
| 服务器调用 | `linien-server/linien_server/optimization/optimization.py` | 76 |

---

## 路线 3：测试调用

```
test_approacher.py
        │  [tests/test_approacher.py:87]
        │
        └──► get_lock_point(reference_signal, 0, len(reference_signal))
             用途：在测试中生成参考光谱

test_peak_valley_pairing.py
        │  [tests/test_peak_valley_pairing.py:82]
        │
        └──► get_lock_point(signal, x0, x1)
             用途：与新算法 get_lock_point_by_peak_valley_pairing 做结果对比
```

---

## 数据流详解

### `get_lock_point` 返回值的使用去向

```
get_lock_point 返回 6 元组
        │
        ├── mean_signal (float)
        │     │
        │     ├─► autolock.py:266  → self.central_y（偏移调整）
        │     └─► optimization.py:90 → Approacher 参数
        │
        ├── target_slope_rising (bool)
        │     │
        │     └─► autolock.py:280 → parameters.target_slope_rising（写入寄存器）
        │
        ├── target_zoom (float)
        │     │
        │     ├─► autolock: 用于缩放控制
        │     └─► optimization.py:82 → self.target_zoom
        │
        ├── rolled_error_signal (np.ndarray)
        │     │
        │     ├─► autolock.py:261 → error_signal_rolled（作为参考光谱）
        │     ├─► optimization.py:83 → self.first_error_signal
        │     └─► plot_widget.py:327 → self.autolock_ref_spectrum（GUI预览）
        │
        ├── line_width (int)
        │     │
        │     └─► autolock.py:262 → 线宽信息
        │
        └── peak_idxs (Tuple[int, int])
              │
              └─► autolock.py:263 → 峰值索引
```

### `autolock_ref_spectrum` 的来源与用途

`autolock_ref_spectrum` 就是 `get_lock_point` 返回的 `rolled_error_signal`（误差信号经平移使锁定点居中后的版本）。

```
用户拖选区域
    ↓
get_lock_point(error_signal, x0, x1)
    ↓
返回 rolled_error_signal（锁定点居中 + NaN 填充）
    ↓
存为 self.autolock_ref_spectrum  [plot_widget.py:327]
    ↓
锁频准备阶段（autolock_preparing=True）：
    determine_shift_by_correlation(ref_spectrum, current_signal)
    ↓
plot_autolock_target_line() 显示锁定目标竖线  [plot_widget.py:670-697]
```

---

## 替换为新算法的指引

如需用 `get_lock_point_by_peak_valley_pairing` 替换原算法，修改以下位置：

| 优先级 | 位置 | 说明 |
|--------|------|------|
| **高** | `autolock.py:264` | 服务器端实际锁频参数计算 |
| 中 | `optimization.py:76` | 优化模式 |
| 中 | `plot_widget.py:324` | GUI 预览（可选） |

> 注：新算法在退化情况下会自动调用原 `get_lock_point`，因此无需完全替换也可安全使用。
