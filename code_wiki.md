# Linien 项目 Code Wiki 文档

## 1. 项目概述

Linien 是一个基于 RedPitaya (STEMlab 125-14) 的激光锁定工具，采用 Python 和 Migen 构建。项目遵循 UNIX 哲学，专注于使用智能算法实现高精度光谱信号锁定。

### 核心功能
- **FPGA 实现**：正弦调制（最高 50 MHz）、解调（1f 到 5f）、滤波和伺服控制均在 FPGA 上实现
- **客户端-服务器架构**：服务器在 RedPitaya 上自主运行，支持多个客户端同时连接
- **自动锁定**：支持鲁棒模式（FPGA）和简单模式（CPU）两种算法
- **IQ 解调**：即时优化解调相位
- **噪声分析**：记录误差信号的功率谱密度（PSD）
- **机器学习优化**：自动调节光谱参数以优化信号

## 2. 项目架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        客户端层 (Client Layer)                       │
│  ┌─────────────────┐    ┌─────────────────┐                        │
│  │   linien-gui    │    │  linien-client  │                        │
│  │  (GUI 界面)     │    │  (Python API)   │                        │
│  └────────┬────────┘    └────────┬────────┘                        │
│           │                      │                                  │
│           └──────────┬───────────┘                                  │
│                      │  RPyC 通信                                   │
│                      ▼                                              │
├─────────────────────────────────────────────────────────────────────┤
│                        服务端层 (Server Layer)                       │
│                        ┌─────────────────┐                          │
│                        │  linien-server  │                          │
│                        │  (控制服务)      │                          │
│                        └────────┬────────┘                          │
│                                 │                                   │
│                                 ▼                                   │
├─────────────────────────────────────────────────────────────────────┤
│                        硬件层 (Hardware Layer)                       │
│                        ┌─────────────────┐                          │
│                        │   gateware      │                          │
│                        │  (FPGA 固件)     │                          │
│                        └─────────────────┘                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 模块划分

| 模块 | 职责 | 技术栈 |
|------|------|--------|
| **linien-common** | 共享组件，包含通信协议、参数定义、工具函数 | Python |
| **linien-server** | 服务端核心逻辑，运行在 RedPitaya 上 | Python + FPGA |
| **linien-client** | 客户端连接库，提供 Python API | Python |
| **linien-gui** | 图形用户界面 | PyQt5 + pyqtgraph |
| **gateware** | FPGA 固件实现 | Migen + Verilog |

## 3. 核心模块详解

### 3.1 linien-common - 共享组件

#### 3.1.1 通信协议

`linien_common/communication.py` 定义了客户端-服务端通信接口：

```python
class LinienControlService(Protocol):
    def exposed_get_server_version(self) -> str: ...
    def exposed_get_param(self, param_name: str) -> bytes: ...
    def exposed_set_param(self, param_name: str, value: bytes) -> None: ...
    def exposed_write_registers(self) -> None: ...
    def exposed_start_autolock(self, x0, x1, spectrum) -> None: ...
    # ... 其他方法
```

关键函数：
- `pack(value)`: 序列化参数值（pickle）
- `unpack(value)`: 反序列化参数值
- `hash_username_and_password()`: 生成认证哈希

#### 3.1.2 公共常量

`linien_common/common.py` 定义了全局常量：
- `N_POINTS`: 数据采集点数（8192）
- `MAX_N_POINTS`: 最大采集点数（16384）
- `DECIMATION`: 抽取因子（16）
- `MHz`, `Vpp`: 单位转换常量
- `AutolockMode`: 自动锁定模式枚举
- `PSDAlgorithm`: PSD 算法枚举

### 3.2 linien-server - 服务端核心

#### 3.2.1 核心服务类

**RedPitayaControlService** (`linien_server/server.py`)
- 继承 `BaseService` 和 `LinienControlService`
- 管理参数同步、数据采集、自动锁定等核心功能

关键方法：
| 方法 | 功能 |
|------|------|
| `exposed_write_registers()` | 将参数同步到 FPGA 寄存器 |
| `exposed_start_autolock()` | 启动自动锁定 |
| `exposed_start_optimization()` | 启动光谱优化 |
| `exposed_start_sweep()` | 启动扫描模式 |
| `exposed_start_lock()` | 启动手动锁定 |

#### 3.2.2 参数管理

`Parameters` 类 (`linien_server/parameters.py`) 定义了所有可配置参数：

**参数分类**：
- **通用参数**：通道配置、GPIO、模拟输出
- **扫描参数**：振幅、中心、速度、暂停
- **调制参数**：振幅、频率
- **解调与滤波参数**：相位、乘法器、IIR 滤波器
- **PID 参数**：比例、积分、微分系数
- **自动锁定参数**：模式、目标位置、指令
- **优化参数**：优化状态、进度

#### 3.2.3 FPGA 寄存器控制

`Registers` 类 (`linien_server/registers.py`) 负责：
- 将高级参数转换为 FPGA 寄存器值
- 管理 IIR 滤波器配置
- 处理 PID 参数设置

关键方法：
- `write_registers()`: 将参数写入 FPGA
- `set_pid(kp, ki, kd, slope)`: 设置 PID 参数
- `set_iir(name, b, a)`: 设置 IIR 滤波器系数

#### 3.2.4 数据采集

`AcquisitionService` (`linien_server/acquisition.py`)：
- 负责从 RedPitaya 采集数据
- 管理 FPGA 固件加载
- 处理数据抽取和格式化

#### 3.2.5 自动锁定算法

**Autolock** (`linien_server/autolock/autolock.py`) 是自动锁定的核心类：

```python
class Autolock:
    def run(self, x0, x1, spectrum, should_watch_lock, auto_offset):
        # 1. 记录参考光谱
        # 2. 选择锁频算法
        # 3. 执行锁定流程
        # 4. 监控锁定状态
```

支持两种算法：
| 算法 | 运行位置 | 特点 |
|------|----------|------|
| **RobustAutolock** | FPGA | 抗抖动能力强，无通信延迟 |
| **SimpleAutolock** | CPU | 算法简单，适用于低抖动场景 |

### 3.3 linien-client - 客户端库

#### 3.3.1 连接管理

`LinienClient` (`linien_client/connection.py`)：
- 处理与服务器的连接
- 管理参数缓存
- 处理版本兼容性检查

```python
client = LinienClient(device)
client.connect(autostart_server=True, use_parameter_cache=True)
```

#### 3.3.2 设备管理

`Device` (`linien_client/device.py`) 封装 RedPitaya 设备信息：
- host: 主机地址（如 `rp-xxxxxx.local`）
- port: 端口（默认 8888）
- username/password: 认证凭证

### 3.4 linien-gui - 图形界面

#### 3.4.1 主应用

`LinienApp` (`linien_gui/app.py`) 是 Qt 应用入口：
- 管理设备管理器和主窗口
- 处理连接状态
- 定期检查参数变化

#### 3.4.2 UI 组件

| 组件 | 功能 |
|------|------|
| `DeviceManager` | 设备列表管理、连接配置 |
| `MainWindow` | 主界面，包含光谱显示和控制面板 |
| `LockingPanel` | 锁定控制（自动/手动） |
| `OptimizationPanel` | 光谱优化控制 |
| `ModulationSweepPanel` | 调制和扫描参数配置 |
| `PSDWindow` | 噪声分析窗口 |

### 3.5 gateware - FPGA 固件

#### 3.5.1 逻辑模块

| 文件 | 功能 |
|------|------|
| `autolock.py` | 自动锁定 FPGA 逻辑 |
| `chains.py` | 信号处理链（解调、滤波） |
| `cordic.py` | CORDIC 算法实现 |
| `decimation.py` | 数据抽取 |
| `delta_sigma.py` | ΔΣ 调制器 |
| `filter.py` | 滤波器 |
| `iir.py` | IIR 滤波器 |
| `pid.py` | PID 控制器 |
| `sweep.py` | 扫描生成器 |

#### 3.5.2 底层模块

| 文件 | 功能 |
|------|------|
| `analog.py` | 模拟接口控制 |
| `gpio.py` | GPIO 控制 |
| `scopegen.py` | 示波器数据生成 |
| `xadc.py` | XADC 接口 |

## 4. 数据流分析

### 4.1 数据采集流程

```
FPGA ADC → AcquisitionService → Registers → Parameters.to_plot → 客户端
     │              │              │
     ▼              ▼              ▼
  原始数据      格式化数据      参数同步
```

### 4.2 控制信号流程

```
客户端参数 → Parameters → Registers.write_registers() → FPGA 寄存器
     │              │                    │
     ▼              ▼                    ▼
  用户输入      参数验证              硬件控制
```

### 4.3 自动锁定流程

```
1. 用户选择锁频区域 (x0, x1)
2. 记录参考光谱并提取特征
3. 算法选择器选择合适算法
4. 执行锁定（FPGA/CPU）
5. 监控锁定状态
6. 锁定成功/失败处理
```

## 5. 依赖关系

### 5.1 模块依赖图

```
linien-gui ───────────────────────────────────────────────────────┐
    │                                                            │
    ├─> linien-client (2.1.0)                                    │
    │       │                                                     │
    │       └─> linien-common (2.1.0)                            │
    │                                                             │
    └─> PyQt5, pyqtgraph, click, requests, superqt               │
                                                                  │
linien-server ────────────────────────────────────────────────────┤
    │                                                             │
    ├─> linien-common (2.1.0)                                    │
    │                                                             │
    └─> cma, fire, influxdb-client, pylpsd, pyrp3 (ARM only)     │
                                                                  │
linien-common ────────────────────────────────────────────────────┤
    │                                                             │
    └─> appdirs, numpy, rpyc, scipy                              │
                                                                  │
gateware ─────────────────────────────────────────────────────────┘
    │
    └─> migen, litex (构建依赖)
```

### 5.2 核心依赖说明

| 依赖 | 用途 | 版本 |
|------|------|------|
| **rpyc** | 客户端-服务器通信 | 6.x |
| **numpy** | 数值计算 | 1.x |
| **scipy** | 科学计算 | 1.x |
| **cma** | 协方差矩阵自适应进化策略（优化算法） | 3.x |
| **pyrp3** | RedPitaya 硬件接口（仅 ARM） | 2.x |
| **PyQt5** | GUI 框架 | 5.x |
| **pyqtgraph** | 实时绘图 | 0.10+ |

## 6. 项目运行方式

### 6.1 安装

#### 客户端安装（PC）

```bash
# 安装 GUI 客户端
pip install linien-gui

# 或仅安装 Python API
pip install linien-client
```

#### 服务端安装（RedPitaya）

通过 GUI 自动安装或手动安装：

```bash
pip install linien-server
linien-server start
```

### 6.2 启动 GUI

```bash
linien
```

### 6.3 Python API 使用示例

```python
from linien_client.device import Device
from linien_client.connection import LinienClient
from linien_common.common import MHz, Vpp

# 创建设备连接
device = Device(
    host="rp-xxxxxx.local",
    username="root",
    password="root"
)

# 连接服务器
client = LinienClient(device)
client.connect(autostart_server=True, use_parameter_cache=True)

# 读取参数
print(client.parameters.modulation_frequency.value / MHz)

# 设置参数
client.parameters.modulation_amplitude.value = 1 * Vpp
client.connection.root.write_registers()
```

### 6.4 开发环境

```bash
# 克隆仓库
git clone https://github.com/linien-org/linien.git
cd linien

# 安装依赖（开发模式）
pip install -e ./linien-common
pip install -e ./linien-client
pip install -e ./linien-server
pip install -e ./linien-gui
```

### 6.5 测试

```bash
# 运行所有测试
pytest tests/

# 排除慢速测试
pytest tests/ -m "not slow"
```

## 7. 关键 API 参考

### 7.1 服务端 API

| 方法 | 说明 |
|------|------|
| `exposed_start_autolock(x0, x1, spectrum)` | 启动自动锁定 |
| `exposed_start_sweep()` | 启动扫描模式 |
| `exposed_start_lock()` | 启动手动锁定 |
| `exposed_write_registers()` | 写入寄存器 |
| `exposed_start_optimization(x0, x1, spectrum)` | 启动光谱优化 |
| `exposed_start_psd_acquisition()` | 启动 PSD 采集 |

### 7.2 参数访问

```python
# 读取参数
value = client.parameters.p.value

# 设置参数
client.parameters.p.value = 100

# 添加参数变化回调
def callback(value):
    print(f"参数变化: {value}")

client.parameters.p.add_callback(callback)
```

### 7.3 常用参数

**调制参数**：
- `modulation_frequency`: 调制频率（Hz）
- `modulation_amplitude`: 调制幅度

**扫描参数**：
- `sweep_amplitude`: 扫描幅度
- `sweep_center`: 扫描中心
- `sweep_speed`: 扫描速度

**PID 参数**：
- `p`: 比例系数
- `i`: 积分系数
- `d`: 微分系数

**滤波参数**：
- `filter_automatic_a/b`: 自动滤波模式
- `filter_1_frequency_a/b`: 滤波器频率

## 8. 项目结构总结

```
linien/
├── gateware/                    # FPGA 固件
│   ├── logic/                   # 逻辑模块
│   ├── lowlevel/                # 底层模块
│   └── verilog/                 # Verilog 文件
├── linien-client/               # 客户端库
│   └── linien_client/
│       ├── connection.py        # 连接管理
│       ├── device.py            # 设备管理
│       └── remote_parameters.py # 远程参数
├── linien-common/               # 共享组件
│   └── linien_common/
│       ├── common.py            # 常量定义
│       ├── communication.py     # 通信协议
│       └── config.py            # 配置
├── linien-gui/                  # 图形界面
│   └── linien_gui/
│       ├── ui/                  # UI 组件
│       ├── app.py               # 应用入口
│       └── threads.py           # 线程管理
├── linien-server/               # 服务端
│   └── linien_server/
│       ├── autolock/            # 自动锁定算法
│       ├── optimization/        # 优化算法
│       ├── acquisition.py       # 数据采集
│       ├── parameters.py        # 参数定义
│       ├── registers.py         # 寄存器控制
│       └── server.py            # 服务端核心
└── tests/                       # 测试用例
```

## 9. 技术亮点

1. **FPGA 加速**：调制、解调、滤波、PID 全部在 FPGA 实现，延迟低至 125-320 ns
2. **双算法支持**：根据抖动情况自动选择鲁棒模式或简单模式
3. **远程控制**：完整的 Python API 支持自动化控制
4. **参数同步**：基于 RPyC 的实时参数同步机制
5. **噪声分析**：内置 PSD 采集和 PID 优化工具

## 10. 版本说明

当前版本：**2.1.0**

| 版本 | 关键变化 |
|------|----------|
| 2.x | 支持 RedPitaya OS 2.x，改进自动锁定算法 |
| 1.x | 旧版，支持 RedPitaya OS 1.x（不再维护） |

---

**文档版本**: v2.1.0  
**生成日期**: 2024年  
**项目地址**: https://github.com/linien-org/linien