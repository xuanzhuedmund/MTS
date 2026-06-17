# 上位机锁频面板 UI 结构

> 文件位置：`linien-gui/linien_gui/ui/locking_panel.ui` + `locking_panel.py`

---

## 整体布局

`LockingPanel` 是一个垂直布局（`QVBoxLayout`）的面板，从上到下依次包含以下区块：

```
LockingPanel (QWidget, QVBoxLayout)
│
├── 1. 快速控制 PID 参数 (groupBox_5)
│       P / I / D 三个 SpinBox（0-8191）
│
├── 2. 慢速控制强度 (slow_pid_group)
│       一个 SpinBox（0-8191），动态显示
│
├── 3. 锁定控制选项卡 (lock_control_container: QTabWidget)
│       ├── Tab "自动" (auto_mode)
│       └── Tab "手动" (manual_mode)
│
├── 4. 锁相状态区 (lock_status_container: LockStatusPanel)
│       状态文字 + 停止按钮 + 历史长度
│
└── 5. 锁定失败提示 (lock_failed)
        失败提示 + 重试按钮
```

---

## 核心区块详解

### 3. 锁定控制选项卡（QTabWidget）

这是用户操作的核心区域，包含两个标签页：

#### Tab 1：自动模式 (`auto_mode`)

```
auto_mode (QWidget)
├── auto_mode_not_activated (未激活选择时显示)
│       │
│       ├── selectLineToLock [选择目标谱线] 按钮（绿色）
│       │
│       ├── groupBox "自动锁相算法"
│       │       └── autolock_mode_preference (QComboBox)
│       │           ├── 自动检测
│       │           ├── 稳健模式
│       │           └── 简单模式
│       │
│       ├── lock_point_algorithm_group "锁定点算法"  ← 【新增】
│       │       └── lock_point_algorithm_combo (QComboBox)
│       │           ├── 极值法（默认）
│       │           └── 峰谷配对法
│       │
│       ├── autoOffsetCheckbox [确定信号偏移] 复选框
│       │       └── 说明文字："调整偏移使锁相点位于..."
│       │
│       └── verticalSpacer (弹性空间)
│
└── auto_mode_activated (激活选择时显示，互斥)
        ├── 提示文字 "点击并拖动选择要锁定的谱线"
        └── abortLineSelection [取消] 按钮（红色）
```

**切换逻辑**：`auto_mode_activated` 和 `auto_mode_not_activated` 互斥显示，由 `autolock_selection` 参数控制。

#### Tab 2：手动模式 (`manual_mode`)

```
manual_mode (QWidget)
├── 提示文字 "在按下按钮前，请将谱线居中并放大"
├── button_slope_rising [上升沿] 单选按钮
├── button_slope_falling [下降沿] 单选按钮
└── manualLockButton [锁定！] 按钮（绿色）
```

---

### 4. 锁相状态区 (`LockStatusPanel`)

```
lock_status_container (LockStatusPanel)
├── lock_status (QLabel, 20pt粗体)
│       显示锁相状态文字
├── stopLockPushButton [停止锁相] 按钮（红色）
└── groupBox_8 "控制信号历史长度"
        └── controlSignalHistoryLengthSpinBox (10-100000s, 默认120)
```

**动态显示逻辑**（`lock_status_changed` 回调）：
- 当 `locked=True` 或 `task_running=True` 或 `autolock_failed=True` 时，隐藏 `lock_control_container`（选项卡）
- 否则显示选项卡让用户操作

---

### 5. 锁定失败提示 (`lock_failed`)

```
lock_failed (QWidget, 默认隐藏)
├── 提示文字 "自动锁相失败！"（红色14pt粗体）
└── reset_lock_failed_state [重试] 按钮（绿色）
```

---

## 控件与参数绑定关系

| UI 控件 | 绑定参数 | 类型 | 说明 |
|---------|----------|------|------|
| `kpSpinBox` | `parameters.p` | int | PID 的 P |
| `kiSpinBox` | `parameters.i` | int | PID 的 I |
| `kdSpinBox` | `parameters.d` | int | PID 的 D |
| `pid_on_slow_strength` | `parameters.pid_on_slow_strength` | int | 慢速控制强度 |
| `lock_control_container` | `parameters.automatic_mode` | bool | Tab 索引（0=自动, 1=手动）|
| `autolock_mode_preference` | `parameters.autolock_mode_preference` | int | 锁相算法模式 |
| `lock_point_algorithm_combo` | `parameters.lock_point_algorithm` | int | **新增**：锁定点算法 |
| `autoOffsetCheckbox` | `parameters.autolock_determine_offset` | int | 自动偏移 |
| `button_slope_rising` | `parameters.target_slope_rising` | bool | 上升沿（手动） |
| `button_slope_falling` | `parameters.target_slope_rising`（取反）| bool | 下降沿（手动） |
| `controlSignalHistoryLengthSpinBox` | `parameters.control_signal_history_length` | int | 历史长度 |

---

## 用户操作流程

### 自动锁频流程

```
1. 用户在"自动"Tab 中选择：
   ├── 锁相算法模式（自动检测/稳健/简单）
   ├── 锁定点算法（极值法/峰谷配对法）  ← 【新增选择】
   └── 是否自动确定偏移
        │
2. 点击 [选择目标谱线]
        │  → parameters.autolock_selection = True
        │  → auto_mode_activated 显示（"点击并拖动选择"）
        │
3. 在绘图画布上拖选区域
        │  → PlotWidget.mouseReleaseEvent()
        │     → control.start_autolock(x0, x1, spectrum)
        │     → 同时根据 lock_point_algorithm 调用对应算法生成预览
        │
4. 锁频过程中：
   ├── lock_control_container 隐藏
   ├── lock_status 显示状态
   └── autolock_failed 时显示重试按钮
```

### 手动锁频流程

```
1. 用户切换到"手动"Tab
2. 选择上升沿/下降沿
3. 点击 [锁定！]
     → start_manual_lock()
     → parameters.autolock_mode = SIMPLE
     → control.start_lock()
```

---

## 锁定点算法下拉框（新增功能）

### 位置

位于"自动锁相算法"groupBox 正下方，在"确定信号偏移"复选框上方。

### 选项

| 索引 | 显示文本 | 对应函数 | 说明 |
|------|----------|----------|------|
| 0 | 极值法（默认） | `get_lock_point` | 原算法，用 argmin/argmax 找单一峰谷对 |
| 1 | 峰谷配对法 | `get_lock_point_by_peak_valley_pairing` | 新算法，scipy 寻峰 + 贪心配对 |

### 数据流

```
用户选择下拉框
    │
    ▼
lock_point_algorithm_changed(idx)
    │  [locking_panel.py]
    ▼
parameters.lock_point_algorithm.value = idx
    │  （通过 rpyc 同步到服务器）
    ▼
执行锁频时：
    ├── autolock.py:record_first_error_signal()
    │     └─ if lock_point_algorithm == 1:
    │            get_lock_point_by_peak_valley_pairing(...)
    │       else:
    │            get_lock_point(...)
    │
    ├── plot_widget.py:mouseReleaseEvent()
    │     └─ 同样根据参数选择算法（GUI 预览）
    │
    └── optimization.py:record_first_error_signal()
          └─ 同样根据参数选择算法（优化模式）
```

### 参数特性

- **可持久化**：`restorable=True`，设备重启后保留用户选择
- **默认值**：0（极值法），保持向后兼容
- **实时同步**：通过 rpyc 参数系统，GUI 修改立即生效到服务器
