# Linien 自动锁频系统

## 系统概述
Linien 自动锁频系统是一个用于激光稳频的完整解决方案，包含软件和硬件两个部分。本文件将详细介绍所有与自动锁频相关的代码，包括其功能、逻辑和实现细节。

## 相关代码文件

### 1. 服务器端自动锁频实现

#### 1.1 `linien-server/linien_server/autolock/autolock.py`
**功能**：自动锁频的核心实现，包含主要逻辑和状态管理。

**主要组件**：
- `Autolock` 类：管理自动锁频的整个流程，包括初始化、运行、监控等
- 支持两种锁频算法：简单锁频和健壮锁频
- 提供锁频状态管理和错误处理

**核心流程**：
1. 记录初始误差信号
2. 选择合适的锁频算法
3. 执行锁频操作
4. 监控锁频状态
5. 支持自动重锁功能

#### 1.2 `linien-server/linien_server/autolock/algorithm_selection.py`
**功能**：根据信号特性自动选择合适的锁频算法。

**主要组件**：
- `AutolockAlgorithmSelector` 类：分析信号抖动程度，选择合适的算法

**核心逻辑**：
1. 分析多个光谱的相关性
2. 计算信号抖动与线宽的比例
3. 根据抖动程度选择算法：抖动小选择简单算法，抖动大选择健壮算法

#### 1.3 `linien-server/linien_server/autolock/simple.py`
**功能**：实现简单锁频算法，适用于抖动较小的系统。

**主要组件**：
- `SimpleAutolock` 类：基于相关性的简单锁频实现

**核心逻辑**：
1. 通过相关性计算信号偏移
2. 确定锁频点位置
3. 启动锁频

#### 1.4 `linien-server/linien_server/autolock/robust.py`
**功能**：实现健壮锁频算法，适用于抖动较大的系统。

**主要组件**：
- `RobustAutolock` 类：更复杂的锁频实现，适应更大的抖动
- `calculate_autolock_instructions` 函数：计算锁频指令
- `get_lock_position_from_autolock_instructions` 函数：根据指令确定锁频位置

**核心逻辑**：
1. 收集多个光谱数据
2. 计算时间尺度和峰值信息
3. 生成锁频指令序列
4. 基于指令序列实现锁频

### 2. 硬件逻辑层自动锁频实现

#### 2.1 `gateware/logic/autolock.py`
**功能**：FPGA硬件逻辑层的自动锁频实现。

**主要组件**：
- `FPGAAutolock` 类：管理FPGA上的自动锁频逻辑
- `SimpleAutolock` 类：FPGA上的简单锁频实现
- `RobustAutolock` 类：FPGA上的健壮锁频实现

**核心逻辑**：
1. 接收锁频请求
2. 根据选择的模式执行相应的锁频逻辑
3. 监控锁频状态并输出结果

#### 2.2 `gateware/logic/autolock_utils.py`
**功能**：自动锁频相关的辅助函数和工具类。

**主要组件**：
- `SumDiffCalculator` 类：计算信号的和差，用于健壮锁频算法

## 工作原理

### 自动锁频流程
1. **初始化**：设置锁频参数，准备锁频环境
2. **记录参考光谱**：采集初始误差信号作为参考
3. **算法选择**：根据信号特性选择合适的锁频算法
4. **执行锁频**：
   - 简单算法：通过相关性计算直接确定锁频点
   - 健壮算法：生成锁频指令序列，逐步逼近锁频点
5. **监控锁频状态**：持续监控锁频效果，必要时重新锁频

### 算法比较

| 算法 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| 简单锁频 | 信号抖动小，线宽稳定 | 速度快，实现简单 | 对抖动敏感 |
| 健壮锁频 | 信号抖动大，线宽不稳定 | 适应能力强 | 计算复杂，速度较慢 |

## 如何加入新的自动锁频算法

要在Linien自动锁频系统中添加新的自动锁频算法，需要在以下几个关键位置进行修改：

### 1. 定义新的算法模式
首先，需要在 `linien-common/linien_common/common.py` 中添加新的算法模式枚举值：
```python
class AutolockMode:
    DISABLED = 0
    ROBUST = 1
    SIMPLE = 2
    NEW_ALGORITHM = 3  # 添加新算法模式
```

### 2. 实现新的算法类
在 `linien-server/linien_server/autolock/` 目录下创建新的算法文件，例如 `new_algorithm.py`，实现新的算法类：
```python
class NewAutolock:
    def __init__(self, control, parameters, first_error_signal, first_error_signal_rolled, x0, x1, additional_spectra=None):
        self.control = control
        self.parameters = parameters
        # 初始化其他必要参数

    def handle_new_spectrum(self, spectrum):
        # 实现新算法的核心逻辑
        # 处理光谱数据，计算锁频点
        # 启动锁频
        pass

    def after_lock(self):
        # 锁频后的处理
        pass
```

### 3. 更新算法选择器
修改 `linien-server/linien_server/autolock/algorithm_selection.py`，使其能够识别并选择新的算法：
```python
def check(self):
    if self.done:
        return True

    if len(self.spectra) < self.N_spectra_required:
        return
    else:
        # 现有逻辑...

        # 添加新算法的选择条件
        if 条件1:
            self.mode = AutolockMode.NEW_ALGORITHM
        elif max_shift <= self.line_width / 2:
            self.mode = AutolockMode.SIMPLE
        else:
            self.mode = AutolockMode.ROBUST

        self.done = True
```

### 4. 更新核心自动锁频类
在 `linien-server/linien_server/autolock/autolock.py` 的 `start_autolock` 方法中添加对新算法的引用：
```python
def start_autolock(self, mode):
    logger.debug(f"Start autolock with mode {mode}")
    self.parameters.autolock_mode.value = mode

    self.algorithm = [
        None,
        RobustAutolock,
        SimpleAutolock,
        NewAutolock  # 添加新算法
    ][mode](
        self.control,
        self.parameters,
        self.first_error_signal,
        self.first_error_signal_rolled,
        self.peak_idxs[0],
        self.peak_idxs[1],
        additional_spectra=self.additional_spectra,
    )
```

### 5. 更新FPGA逻辑（如果需要）
如果新算法需要在FPGA上实现，需要修改 `gateware/logic/autolock.py`：
1. 添加新的算法模块类，类似于 `SimpleAutolock` 和 `RobustAutolock`
2. 在 `FPGAAutolock` 类中添加对新算法的引用
3. 更新同步逻辑，处理新算法的锁频请求

### 6. 更新文档
在 `README自动锁频.md` 中添加新算法的说明，包括：
- 算法原理
- 适用场景
- 优点和缺点
- 实现细节

### 7. 测试
添加新算法后，需要进行充分的测试，确保其能够正确工作：
- 测试算法选择逻辑
- 测试锁频性能
- 测试在不同条件下的稳定性

## 代码注释文件列表

以下文件已添加完整中文注释：
1. `linien-server/linien_server/autolock/autolock.py`
2. `linien-server/linien_server/autolock/algorithm_selection.py`
3. `linien-server/linien_server/autolock/simple.py`
4. `linien-server/linien_server/autolock/robust.py`
5. `gateware/logic/autolock.py`

## 总结

Linien 自动锁频系统是一个功能完整、设计灵活的激光稳频解决方案，具有以下特点：

1. **双算法支持**：提供简单锁频和健壮锁频两种算法，适应不同的系统条件
2. **自动算法选择**：根据信号特性自动选择合适的锁频算法
3. **硬件加速**：在FPGA上实现锁频逻辑，提高性能和可靠性
4. **错误处理**：完善的错误处理机制，确保系统稳定运行
5. **状态监控**：实时监控锁频状态，支持自动重锁

该系统不仅适用于实验室环境中的激光稳频，也可以扩展到其他需要高精度控制的领域。通过软件和硬件的紧密配合，实现了高效、可靠的自动锁频功能。