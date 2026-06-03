# Linien 手动运行指南（不使用 pip install）

> **版本**: Linien 2.1.0
> **适用场景**: 从源码直接运行 linien-client（PC端）和 linien-server（Red Pitaya端），不通过 pip 安装 linien 自身包

---

## 目录

1. [项目架构概览](#1-项目架构概览)
2. [核心难点分析](#2-核心难点分析)
3. [PC 端运行 linien-client](#3-pc-端运行-linien-client)
4. [Red Pitaya 端运行 linien-server](#4-red-pitaya-端运行-linien-server)
5. [版本号修改清单](#5-版本号修改清单)
6. [完整启动脚本示例](#6-完整启动脚本示例)
7. [常见问题排查](#7-常见问题排查)

---

## 1. 项目架构概览

Linien 采用 **Client-Server** 架构，通过 **RPyC** 协议通信：

```
┌─────────────────── PC 端 ───────────────────┐
│                                              │
│  linien-gui / linien-client                  │
│       │                                      │
│       │ rpyc.connect(host, 18862)            │
│       ▼                                      │
└──────────────┬───────────────────────────────┘
               │ 网络 (RPyC 协议)
               │ 端口 18862 (控制)
               │ 端口 19321 (采集数据)
┌──────────────▼───────────────────────────────┐
│          Red Pitaya 端                        │
│                                               │
│  linien-server                                │
│    ├── RedPitayaControlService               │
│    │     ├── Parameters (参数管理)            │
│    │     ├── Registers (FPGA 寄存器)         │
│    │     └── Autolock/Optimization (算法)     │
│    │                                          │
│    └── AcquisitionService                     │
│          ├── pyrp3 (硬件驱动)                 │
│          ├── PythonCSR (FPGA 寄存器操作)      │
│          └── flash_fpga() (烧录 bitstream)    │
│                                               │
│  FPGA gateware.bin (自定义 FPGA 固件)         │
└───────────────────────────────────────────────┘
```

### 子包说明

| 子包 | 运行位置 | 作用 |
|------|---------|------|
| `linien-common` | PC + RP | 共享代码（参数定义、通信协议、配置常量） |
| `linien-client` | PC 端 | 客户端连接、设备管理、远程参数代理 |
| `linien-gui` | PC 端 | PyQt5 图形界面（依赖 linien-client） |
| `linien-server` | Red Pitaya | 服务器：FPGA 控制、自动锁频、信号优化 |

---

## 2. 核心难点分析

### 2.1 `importlib.metadata.version()` 依赖

三个子包的 `__init__.py` 中使用 `importlib.metadata.version()` 获取版本号：

```python
# linien-common/linien_common/__init__.py 第8行
__version__ = importlib_metadata.version("linien-common")

# linien-client/linien_client/__init__.py 第24行
__version__ = importlib.metadata.version("linien-client")

# linien-server/linien_server/__init__.py 第24行
__version__ = importlib_metadata.version("linien-server")
```

**问题**: 如果未通过 pip 安装，这些调用会抛出 `PackageNotFoundError`。

**解决**: 将版本号硬编码为字符串 `"2.1.0"`。

### 2.2 包间相对导入

代码中使用绝对导入，如：

```python
from linien_common.communication import LinienControlService
from linien_server.parameters import Parameters
```

**解决**: 通过 `PYTHONPATH` 或 `sys.path.insert()` 将源码根目录加入 Python 路径。

### 2.3 版本匹配校验

`LinienClient.connect()` 会校验 client 和 server 版本是否一致：

```python
# linien_client/connection.py 第128-132行
remote_version = self.connection.root.exposed_get_server_version().split("+")[0]
local_version = __version__.split("+")[0]

if (remote_version != local_version) and not ("dev" in local_version):
    raise InvalidServerVersionException(local_version, remote_version)
```

**注意**: 修改版本号后，确保 PC 端和 RP 端的版本号一致。

---

## 3. PC 端运行 linien-client

### 3.1 前提条件

- Python >= 3.8
- 项目源码已下载到本地（例如 `D:\GitHub\MTS`）

### 3.2 安装第三方依赖

**不安装 linien 自身包**，仅安装其依赖的第三方库：

```bash
# 安装 linien-common 的依赖
pip install appdirs numpy rpyc scipy

# 安装 linien-client 的额外依赖
pip install fabric typing_extensions

# 如需运行 GUI，还需安装
pip install click pyqtgraph PyQt5 requests superqt
```

### 3.3 修改版本号

**文件 1**: `linien-common/linien_common/__init__.py`

**修改前**:
```python
import importlib_metadata

from .config import LOG_FILE_PATH

__version__ = importlib_metadata.version("linien-common")  # noqa: F401
```

**修改后**:
```python
import importlib_metadata

from .config import LOG_FILE_PATH

__version__ = "2.1.0"  # 硬编码版本号，替代 importlib_metadata.version("linien-common")
```

**文件 2**: `linien-client/linien_client/__init__.py`

**修改前**:
```python
import importlib.metadata
import logging
from logging.handlers import RotatingFileHandler

from linien_common.config import LOG_FILE_PATH

__version__ = importlib.metadata.version("linien-client")  # noqa: F401
```

**修改后**:
```python
import importlib.metadata
import logging
from logging.handlers import RotatingFileHandler

from linien_common.config import LOG_FILE_PATH

__version__ = "2.1.0"  # 硬编码版本号，替代 importlib.metadata.version("linien-client")
```

### 3.4 设置 PYTHONPATH

#### Windows (PowerShell)

```powershell
$env:PYTHONPATH = "D:\GitHub\MTS\linien-common;D:\GitHub\MTS\linien-client"
```

#### Windows (CMD)

```cmd
set PYTHONPATH=D:\GitHub\MTS\linien-common;D:\GitHub\MTS\linien-client
```

#### Linux/macOS

```bash
export PYTHONPATH=/path/to/MTS/linien-common:/path/to/MTS/linien-client
```

### 3.5 运行客户端代码

#### 方式一：Python 脚本连接

```python
# run_client.py
import sys

# 将源码路径加入 Python 路径（根据实际路径修改）
sys.path.insert(0, r"D:\GitHub\MTS\linien-common")
sys.path.insert(0, r"D:\GitHub\MTS\linien-client")

from linien_client.device import Device
from linien_client.connection import LinienClient
from linien_common.common import MHz, Vpp, ANALOG_OUT_V

# 创建设备对象
dev = Device(
    host="rp-xxxxxx.local",  # Red Pitaya 的 hostname 或 IP
    username="root",
    password="root"
)

# 创建客户端并连接
c = LinienClient(dev)
c.connect(autostart_server=True, use_parameter_cache=True)

print("连接成功！")
print(f"调制频率: {c.parameters.modulation_frequency.value / MHz} MHz")
print(f"调制幅度: {c.parameters.modulation_amplitude.value / Vpp} Vpp")

# 设置参数示例
c.parameters.modulation_amplitude.value = 1 * Vpp
c.connection.root.exposed_write_registers()

# 断开连接
c.disconnect()
```

运行:
```bash
python run_client.py
```

#### 方式二：交互式 Python

```python
import sys
sys.path.insert(0, r"D:\GitHub\MTS\linien-common")
sys.path.insert(0, r"D:\GitHub\MTS\linien-client")

from linien_client.device import Device
from linien_client.connection import LinienClient

dev = Device(host="rp-xxxxxx.local", username="root", password="root")
c = LinienClient(dev)
c.connect(autostart_server=True, use_parameter_cache=True)

# 读取参数
print(c.parameters.modulation_frequency.value)

# 设置参数
c.parameters.sweep_amplitude.value = 0.5
c.connection.root.exposed_write_registers()
```

#### 方式三：运行 GUI

```python
# run_gui.py
import sys

sys.path.insert(0, r"D:\GitHub\MTS\linien-common")
sys.path.insert(0, r"D:\GitHub\MTS\linien-client")
sys.path.insert(0, r"D:\GitHub\MTS\linien-gui")

from linien_gui.app import main

if __name__ == "__main__":
    main()
```

运行:
```bash
python run_gui.py
```

---

## 4. Red Pitaya 端运行 linien-server

### 4.1 前提条件

- Red Pitaya OS 2.x
- Python >= 3.10
- SSH 访问权限
- 项目源码已上传到 Red Pitaya（例如 `/root/linien/`）

### 4.2 安装第三方依赖

在 Red Pitaya 上通过 SSH 执行：

```bash
# 安装 linien-common 的依赖
pip3 install appdirs numpy rpyc scipy

# 安装 linien-server 的额外依赖
pip3 install cma fire influxdb-client pylpsd

# 安装 Red Pitaya 专用硬件驱动（仅限 ARM 平台）
pip3 install pyrp3
```

### 4.3 上传源码到 Red Pitaya

#### 方式一：通过 SCP

```bash
# 在 PC 端执行
scp -r /path/to/MTS/linien-common root@rp-xxxxxx.local:/root/linien/
scp -r /path/to/MTS/linien-server root@rp-xxxxxx.local:/root/linien/
```

#### 方式二：通过 Git Clone

```bash
# 在 Red Pitaya 上执行
cd /root
git clone https://github.com/linien-org/linien.git
```

### 4.4 修改版本号

**文件**: `linien-server/linien_server/__init__.py`

**修改前**:
```python
import importlib_metadata
from linien_common.config import LOG_FILE_PATH

__version__ = importlib_metadata.version("linien-server")  # noqa: F401
```

**修改后**:
```python
import importlib_metadata
from linien_common.config import LOG_FILE_PATH

__version__ = "2.1.0"  # 硬编码版本号，替代 importlib_metadata.version("linien-server")
```

### 4.5 运行 Server

#### 方式一：直接运行（前台）

```bash
# 设置 PYTHONPATH
export PYTHONPATH=/root/linien/linien-common:/root/linien/linien-server

# 运行 server（真实硬件模式）
python3 -c "
from linien_server.cli import LinienServerCLI
cli = LinienServerCLI()
cli.run()
"
```

#### 方式二：通过 CLI 入口运行

```bash
export PYTHONPATH=/root/linien/linien-common:/root/linien/linien-server

# 运行真实 server
python3 /root/linien/linien-server/linien_server/cli.py run

# 运行仿真 server（不操作硬件，生成随机数据）
python3 /root/linien/linien-server/linien_server/cli.py run --fake
```

#### 方式三：作为 systemd 服务运行

**Step 1**: 修改 service 文件

创建或修改 `/etc/systemd/system/linien-server.service`：

```ini
[Unit]
Description=Spectroscopy lock server for RedPitaya
Wants=network-online.target
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 -c "import sys; sys.path.insert(0, '/root/linien/linien-common'); sys.path.insert(0, '/root/linien/linien-server'); from linien_server.cli import LinienServerCLI; LinienServerCLI().run()"
WorkingDirectory=/root/linien
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Step 2**: 启用并启动服务

```bash
# 重新加载 systemd
systemctl daemon-reload

# 启用开机自启
systemctl enable linien-server

# 启动服务
systemctl start linien-server

# 查看状态
systemctl status linien-server

# 查看日志
journalctl -u linien-server -f
```

**Step 3**: 停止/重启服务

```bash
systemctl stop linien-server
systemctl restart linien-server
```

### 4.6 运行 AcquisitionService（独立数据采集服务）

在某些场景下，可能需要单独运行数据采集服务：

```bash
export PYTHONPATH=/root/linien/linien-common:/root/linien/linien-server

python3 -c "
from linien_server.acquisition import AcquisitionService
from rpyc.utils.server import ThreadedServer
from linien_common.config import ACQUISITION_PORT

server = ThreadedServer(AcquisitionService(), port=ACQUISITION_PORT)
print(f'Starting AcquisitionService on port {ACQUISITION_PORT}')
server.start()
"
```

---

## 5. 版本号修改清单

| 序号 | 文件路径 | 原代码 | 修改后 |
|------|---------|--------|--------|
| 1 | `linien-common/linien_common/__init__.py` 第8行 | `importlib_metadata.version("linien-common")` | `"2.1.0"` |
| 2 | `linien-client/linien_client/__init__.py` 第24行 | `importlib.metadata.version("linien-client")` | `"2.1.0"` |
| 3 | `linien-server/linien_server/__init__.py` 第24行 | `importlib_metadata.version("linien-server")` | `"2.1.0"` |

> **重要**: 三个包的版本号必须保持一致，否则 `LinienClient.connect()` 会抛出 `InvalidServerVersionException`。

---

## 6. 完整启动脚本示例

### 6.1 PC 端启动脚本 (Windows)

创建文件 `start_linien_client.ps1`：

```powershell
# start_linien_client.ps1
# Linien Client 启动脚本（不使用 pip install）

# 配置路径
$PROJECT_ROOT = "D:\GitHub\MTS"
$PYTHONPATH = "$PROJECT_ROOT\linien-common;$PROJECT_ROOT\linien-client"

# 设置环境变量
$env:PYTHONPATH = $PYTHONPATH

Write-Host "PYTHONPATH: $env:PYTHONPATH" -ForegroundColor Green

# 运行客户端
python -c "
import sys
sys.path.insert(0, r'$PROJECT_ROOT\linien-common')
sys.path.insert(0, r'$PROJECT_ROOT\linien-client')

from linien_client.device import Device
from linien_client.connection import LinienClient
from linien_common.common import MHz, Vpp

dev = Device(
    host='rp-xxxxxx.local',
    username='root',
    password='root'
)

c = LinienClient(dev)
c.connect(autostart_server=True, use_parameter_cache=True)

print('连接成功！')
print(f'服务器版本: {c.connection.root.exposed_get_server_version()}')
print(f'调制频率: {c.parameters.modulation_frequency.value / MHz} MHz')
print(f'扫描幅度: {c.parameters.sweep_amplitude.value}')

# 保持连接，按 Ctrl+C 退出
try:
    import time
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print('断开连接...')
    c.disconnect()
"
```

运行:
```powershell
.\start_linien_client.ps1
```

### 6.2 Red Pitaya 端启动脚本

创建文件 `/root/linien/start_server.sh`：

```bash
#!/bin/bash
# start_server.sh
# Linien Server 启动脚本（不使用 pip install）

PROJECT_ROOT="/root/linien"
export PYTHONPATH="${PROJECT_ROOT}/linien-common:${PROJECT_ROOT}/linien-server"

echo "PYTHONPATH: $PYTHONPATH"

# 运行 server
python3 -c "
import sys
import logging

# 设置日志级别
logging.basicConfig(level=logging.DEBUG)

from linien_server.cli import LinienServerCLI

cli = LinienServerCLI()
cli.run()
"
```

赋予执行权限并运行:
```bash
chmod +x /root/linien/start_server.sh
/root/linien/start_server.sh
```

### 6.3 自动锁频脚本示例

```python
# autolock_example.py
import sys
import pickle
import numpy as np
from time import sleep

sys.path.insert(0, r"D:\GitHub\MTS\linien-common")
sys.path.insert(0, r"D:\GitHub\MTS\linien-client")

from linien_client.device import Device
from linien_client.connection import LinienClient
from linien_common.common import MHz, Vpp

def wait_for_lock_status(client, should_be_locked, timeout=30):
    """等待锁频状态变化"""
    counter = 0
    while counter < timeout:
        to_plot = pickle.loads(client.parameters.to_plot.value)
        is_locked = "error_signal" in to_plot
        if is_locked == should_be_locked:
            return True
        sleep(1)
        counter += 1
    return False

# 连接
dev = Device(host="rp-xxxxxx.local", username="root", password="root")
c = LinienClient(dev)
c.connect(autostart_server=True, use_parameter_cache=True)

print("已连接，准备自动锁频...")

# 关闭锁频（如果已锁定）
c.connection.root.exposed_start_sweep()
sleep(2)

# 获取参考光谱
to_plot = pickle.loads(c.parameters.to_plot.value)
error_signal = to_plot["error_signal_1"]

# 设置自动锁频参数
c.parameters.autolock_mode_preference.value = 0  # AUTO_DETECT
c.parameters.autolock_determine_offset.value = True

# 启动自动锁频（假设锁频点在信号中间位置）
x0 = int(len(error_signal) * 0.4)
x1 = int(len(error_signal) * 0.6)
c.connection.root.exposed_start_autolock(x0, x1, pickle.dumps(error_signal))

# 等待锁频成功
if wait_for_lock_status(c, True):
    print("自动锁频成功！")
else:
    print("自动锁频失败或超时")

# 断开
c.disconnect()
```

---

## 7. 常见问题排查

### 问题 1: `PackageNotFoundError: No package metadata was found for linien-client`

**原因**: 未修改 `__init__.py` 中的版本号获取方式。

**解决**: 按照 [第5节](#5-版本号修改清单) 修改三个 `__init__.py` 文件。

### 问题 2: `ModuleNotFoundError: No module named 'linien_common'`

**原因**: `PYTHONPATH` 未正确设置。

**解决**: 确保 `linien-common` 和 `linien-client`（或 `linien-server`）的父目录在 `PYTHONPATH` 中。

```bash
# 正确示例
export PYTHONPATH=/root/linien/linien-common:/root/linien/linien-server

# 错误示例（指向了包的父目录而非包本身）
export PYTHONPATH=/root/linien  # 这样导入时需要用 from linien_server import xxx
```

### 问题 3: `InvalidServerVersionException`

**原因**: PC 端和 RP 端的版本号不一致。

**解决**: 确保三个 `__init__.py` 中的 `__version__` 值完全相同。

### 问题 4: `ServerNotRunningException`

**原因**: Red Pitaya 上的 server 未运行。

**解决**: 在 RP 上启动 server，或将 `autostart_server=True` 传给 `connect()`。

### 问题 5: Red Pitaya 上 `pyrp3` 安装失败

**原因**: `pyrp3` 有平台限制（`platform_machine=='armv7l'`）。

**解决**: 确保在 Red Pitaya（ARM 架构）上安装，而非 PC（x86/x64）。

```bash
# 在 Red Pitaya 上检查架构
uname -m  # 应输出 armv7l

# 手动安装 pyrp3
pip3 install pyrp3>=2.1.0
```

### 问题 6: FPGA 烧录失败

**原因**: `gateware.bin` 文件缺失或 `fpgautil` 工具不可用。

**解决**: 确保 `gateware.bin` 在 `linien_server/` 目录下，且 Red Pitaya OS 包含 `fpgautil`：

```bash
# 检查文件是否存在
ls /root/linien/linien-server/linien_server/gateware.bin

# 检查 fpgautil 是否存在
which fpgautil
/opt/redpitaya/bin/fpgautil --help
```

### 问题 7: 连接超时或认证失败

**原因**: 网络不通或 SSH 凭据错误。

**解决**:
```bash
# 测试网络连通性
ping rp-xxxxxx.local

# 测试 SSH 连接
ssh root@rp-xxxxxx.local

# 检查 server 是否在监听
ss -tlnp | grep 18862
```

---

## 附录：关键文件路径速查

| 文件 | 路径 | 说明 |
|------|------|------|
| Client 版本定义 | `linien-client/linien_client/__init__.py` | 需修改 `__version__` |
| Server 版本定义 | `linien-server/linien_server/__init__.py` | 需修改 `__version__` |
| Common 版本定义 | `linien-common/linien_common/__init__.py` | 需修改 `__version__` |
| Server CLI 入口 | `linien-server/linien_server/cli.py` | `LinienServerCLI.run()` |
| Server 核心服务 | `linien-server/linien_server/server.py` | `RedPitayaControlService` |
| 数据采集服务 | `linien-server/linien_server/acquisition.py` | `AcquisitionService` |
| 客户端连接 | `linien-client/linien_client/connection.py` | `LinienClient` |
| 通信协议 | `linien-common/linien_common/communication.py` | `LinienControlService` |
| 配置常量 | `linien-common/linien_common/config.py` | `SERVER_PORT`, `ACQUISITION_PORT` |
| FPGA bitstream | `linien-server/linien_server/gateware.bin` | 硬件固件 |
| systemd 服务 | `linien-server/linien_server/linien-server.service` | 系统服务配置 |
