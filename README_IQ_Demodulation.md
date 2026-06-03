# IQ 解调算法逻辑与相关代码分析报告

本项目是基于 **Linien** 的激光频率锁定系统（MTS — 调制转移光谱学），运行在 Red Pitaya FPGA 平台上。IQ 解调是系统的核心信号处理功能，分布在 **FPGA 硬件层**、**服务器层**、**通用工具层** 三个层次。

---

## 一、算法原理总览

IQ 解调的本质是**锁相放大**（Lock-in Amplifier），用于从含噪信号中提取特定频率分量的幅度和相位信息。数学表达为：

```
输入信号: x(t) = A·cos(ωt + φ) + noise

解调参考相位: θ = ωt × multiplier + delay

I 分量（同相）: I = x(t) × cos(θ)
Q 分量（正交）: Q = x(t) × sin(θ)

信号幅度: R = √(I² + Q²)
信号相位: φ = arctan(Q / I)
```

本项目用 **CORDIC 算法** 在 FPGA 上高效实现这一乘法旋转操作，避免了使用硬件乘法器。

---

## 二、FPGA 硬件层 — 核心解调实现

### 1. `Demodulate` 类 — IQ 解调器主体

**文件**：`gateware/logic/modulate.py`（第 25-55 行）

```python
class Demodulate(Module, AutoCSR):
    def __init__(self, freq_width=32, width=14):
        self.x = Signal((width, True))       # 输入信号（来自 ADC）
        self.i = Signal((width, True))       # 同相分量 I 输出
        self.q = Signal((width, True))       # 正交分量 Q 输出
        self.delay = CSRStorage(freq_width)  # 相位延迟控制（0~360°映射）
        self.multiplier = CSRStorage(4, reset=1)  # 谐波倍频系数（支持 1f~5f）
        self.phase = Signal(width)           # 来自调制器的相位参考

        # CORDIC 旋转器：以 rotate-circular 模式实现 IQ 分离
        self.submodules.cordic = Cordic(
            width=width + 1,
            stages=width + 1,
            guard=2,
            eval_mode="pipelined",    # 流水线模式，每时钟周期产出结果
            cordic_mode="rotate",     # 旋转模式
            func_mode="circular",     # 圆形函数（三角函数）
        )
        self.comb += [
            self.cordic.xi.eq(self.x),
            # 相位 = 调制相位 × 倍频系数 + 延迟偏移
            self.cordic.zi.eq(
                ((self.phase * self.multiplier.storage) + self.delay.storage) << 1
            ),
            # CORDIC 输出即为 IQ 分量
            self.i.eq(self.cordic.xo >> 1),  # I = x · cos(θ)
            self.q.eq(self.cordic.yo >> 1),  # Q = x · sin(θ)
        ]
```

**关键设计要点**：

- **CORDIC 替代乘法器**：用纯加法/移位运算实现三角函数乘法，非常适合 FPGA
- **流水线模式**（`pipelined`）：每个时钟周期都能产出结果，吞吐量最大
- **谐波解调**：`multiplier` 支持 1f, 2f, 3f, 4f, 5f 等倍频解调
- **相位延迟**：`delay` 寄存器用于精确调节解调参考的相位偏移

### 2. `Cordic` 类 — CORDIC 算法实现

**文件**：`gateware/logic/cordic.py`（第 23-370 行）

CORDIC（坐标旋转数字计算机）通过迭代移位-加法操作实现旋转变换。每个流水线阶段 `i` 执行：

```
x_{i+1} = x_i - d_i · y_i >> i
y_{i+1} = y_i + d_i · x_i >> i
z_{i+1} = z_i - d_i · arctan(2^{-i})
```

其中 `d_i` 由 `z_i` 的符号决定（旋转模式）。经过 N 级迭代后，CORDIC 在 **rotate-circular** 模式下实现：

```
xo = G · (xi·cos(zi) - yi·sin(zi))
yo = G · (xi·sin(zi) + yi·cos(zi))
```

`Cordic`（第 341 行）继承 `TwoQuadrantCordic` 并扩展为**四象限**支持，通过检测 `zi` 的高两位异或来判断是否需要象限重映射。

### 3. `FastChain` 类 — 完整 IQ 信号链

**文件**：`gateware/logic/chains.py`（第 27-111 行）

`FastChain` 将解调器嵌入完整的信号处理链，包含：

```
ADC → Demodulate(IQ分离) → Limit → IIR低通(一阶) → IIR低通(二阶) → Limit → 输出
```

核心逻辑：

- ADC 数据送入 `Demodulate` 模块进行 IQ 分离
- **I 通道和 Q 通道各自独立**经过两级 IIR 低通滤波器（`iir_c` 一阶 + `iir_d` 二阶）
- 滤波后分别输出到 `out_i`（同相）和 `out_q`（正交）
- 系统有 **A/B 两个独立解调通道**（`fast_a` 和 `fast_b`），支持双通道光谱学

### 4. `Modulate` 类 — 调制器（相位参考源）

**文件**：`gateware/logic/modulate.py`（第 58-89 行）

调制器同样使用 CORDIC 生成正弦调制信号，并通过累加器产生相位 `self.phase`，这个相位直接传递给解调器作为参考：

```python
z = Signal(freq_width)
self.sync += z.eq(z + self.freq.storage)  # 相位累加器（NCO）
self.phase.eq(z[-len(self.phase):])       # 截取高有效位作为相位
```

---

## 三、服务器层 — 参数配置与数据采集

### 1. 解调参数定义

**文件**：`linien-server/linien_server/parameters.py`

```python
self.demodulation_phase_a = Parameter(start=0)     # 通道 A 解调相位 (0~360°)
self.demodulation_phase_b = Parameter(start=0)     # 通道 B 解调相位 (0~360°)
self.demodulation_multiplier_a = Parameter(start=1) # 通道 A 倍频系数
self.demodulation_multiplier_b = Parameter(start=1) # 通道 B 倍频系数
```

### 2. 相位到延迟的转换

**文件**：`linien-server/linien_server/registers.py`

```python
def phase_to_delay(phase):
    return int(phase / 360 * (1 << 14))  # 将 0~360° 映射为 14-bit 整数延迟值
```

### 3. IQ 数据采集与分发

**文件**：`linien-server/linien_server/acquisition.py`

```python
# 两个通道 × 两个子通道(I/Q) = 4 路信号
for sub_channel_idx in (0, 1):  # 0=I, 1=Q
    signals.append(channel_data[sub_channel_idx])

signals_named["error_signal_1"] = signals[0]              # 通道A I分量
signals_named["error_signal_1_quadrature"] = signals[2]   # 通道A Q分量
signals_named["error_signal_2"] = signals[1]              # 通道B I分量
signals_named["error_signal_2_quadrature"] = signals[3]   # 通道B Q分量
```

---

## 四、软件层 — IQ 相位优化与信号强度计算

### 1. 从 IQ 重建任意相位的解调信号

**文件**：`linien-server/linien_server/optimization/utils.py`（第 48-64 行）

```python
def calculate_spectrum_from_iq(i, q, phase):
    return np.array(i) * np.cos(phase / 360 * 2 * np.pi) + \
           np.array(q) * np.sin(phase / 360 * 2 * np.pi)

def optimize_phase_from_iq(i, q, final_zoom_factor):
    def iq2slope(phase):
        calculated = calculate_spectrum_from_iq(i, q, phase)
        return get_max_slope(calculated, final_zoom_factor)

    min_result = optimize.minimize_scalar(
        lambda phase: -1 * iq2slope(phase), method="Bounded", bounds=(0, 360)
    )
    return min_result.x, abs(min_result.fun)  # 返回最优相位和对应斜率
```

**原理**：一旦获得了 I 和 Q 分量，就可以在软件中用 `I·cos(φ) + Q·sin(φ)` 重建**任意相位** φ 的解调结果，无需重新采集数据。通过标量优化搜索使**信号斜率最大**的相位值。

### 2. 信号强度计算

**文件**：`linien-common/linien_common/common.py`（第 310-316 行）

```python
def get_signal_strength_from_i_q(i, q):
    i = i.astype(np.int64)
    q = q.astype(np.int64)
    i_squared = i**2
    q_squared = q**2
    signal_strength = np.sqrt(i_squared + q_squared)  # R = √(I² + Q²)
    return signal_strength
```

---

## 五、完整数据流图

```
┌──────────────────────────────────────────────────────────────────┐
│                        FPGA 硬件层                                │
│                                                                  │
│  Modulate (NCO + CORDIC) ──phase──┐                              │
│       ↑                            │                              │
│    freq/amp 寄存器                 ▼                              │
│                          ┌─────────────────┐                     │
│    ADC ──x──────────────→│   Demodulate    │                     │
│                          │  (CORDIC 旋转)   │                     │
│                          │  θ = phase×mult  │                     │
│                          │    + delay       │                     │
│                          └───┬─────────┬───┘                     │
│                              │I        │Q                        │
│                              ▼         ▼                         │
│                         ┌────────┐ ┌────────┐                    │
│                         │IIR×2级 │ │IIR×2级 │  ← 低通滤波         │
│                         │(I通道) │ │(Q通道) │                    │
│                         └───┬────┘ └───┬────┘                    │
│                             │          │                          │
│                          out_i      out_q                        │
└─────────────────────────────┬──────────┬─────────────────────────┘
                              │          │
                              ▼          ▼
┌──────────────────────────────────────────────────────────────────┐
│                        服务器软件层                               │
│                                                                  │
│  acquisition.py:                                                 │
│    error_signal_1 = I_A    error_signal_1_quadrature = Q_A       │
│    error_signal_2 = I_B    error_signal_2_quadrature = Q_B       │
│                                                                  │
│  optimization/utils.py:                                          │
│    calculate_spectrum_from_iq(i, q, phase) → I·cos(φ)+Q·sin(φ)  │
│    optimize_phase_from_iq(i, q) → 最优相位 φ_opt                │
│                                                                  │
│  common.py:                                                      │
│    get_signal_strength_from_i_q(i, q) → √(I²+Q²)               │
│                                                                  │
│  registers.py:                                                   │
│    phase_to_delay(φ_opt) → 写回 FPGA delay 寄存器               │
└──────────────────────────────────────────────────────────────────┘
```

---

## 六、涉及文件汇总

| 层次 | 文件路径 | 核心功能 |
|------|---------|---------|
| **FPGA** | `gateware/logic/modulate.py` | `Demodulate` 类 — CORDIC IQ 解调硬件核心 |
| **FPGA** | `gateware/logic/cordic.py` | CORDIC 算法流水线实现 |
| **FPGA** | `gateware/logic/chains.py` | `FastChain` — IQ 信号链（解调+IIR滤波） |
| **Server** | `linien-server/linien_server/parameters.py` | 解调参数定义（相位、倍频系数） |
| **Server** | `linien-server/linien_server/registers.py` | 相位→延迟转换，FPGA 寄存器写入 |
| **Server** | `linien-server/linien_server/csrmap.py` | CSR 寄存器地址映射 |
| **Server** | `linien-server/linien_server/acquisition.py` | IQ 信号采集与分发 |
| **Server** | `linien-server/linien_server/optimization/utils.py` | IQ 相位重建与优化算法 |
| **Server** | `linien-server/linien_server/optimization/engine.py` | 优化引擎的 IQ 数据处理 |
| **Server** | `linien-server/linien_server/optimization/optimization.py` | 优化流程中 IQ 数据传递 |
| **Common** | `linien-common/linien_common/common.py` | `get_signal_strength_from_i_q()` |
| **GUI** | `linien-gui/linien_gui/ui/spectroscopy_panel.py` | 解调参数 UI 控制 |
| **GUI** | `linien-gui/linien_gui/ui/plot_widget.py` | IQ 信号强度可视化 |
| **GUI** | `linien-gui/linien_gui/ui/optimization_panel.py` | 优化参数显示 |
| **Test** | `tests/test_modulate.py` | 硬件解调仿真测试 |
| **Test** | `tests/test_optimizer_utils.py` | IQ 优化工具测试 |
| **Test** | `tests/test_optimizer_engines.py` | 优化引擎集成测试 |
