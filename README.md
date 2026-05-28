![GitHub release (latest by date)](https://img.shields.io/github/v/release/linien-org/linien)
[![PyPI](https://img.shields.io/pypi/v/linien-gui?color=blue)](https://pypi.org/project/linien-gui/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Linien ‒ 使用 RedPitaya (STEMlab 125-14) 进行激光锁定的用户友好工具，开箱即用
=========================================================================================

<img align="right" src="https://raw.githubusercontent.com/linien-org/linien/master/docs/icon.png" width="20%">

使用 RedPitaya (STEMlab 125-14) 进行激光锁定的用户友好工具，开箱即用。
Linien 遵循 UNIX 哲学，即把一件事（使用智能算法进行锁定）做到极致。
它主要用于光谱信号的锁定，但也适用于 Pound-Drever-Hall 或其他锁相技术，以及简单的 PID 控制。
Linien 使用 Python 和 [Migen](https://github.com/m-labs/migen) 构建，基于 [red pid](https://github.com/quartiq/redpid) 开发。

功能特性
--------

-   **功能齐全**：正弦调制（最高 50 MHz）、解调（1f 到 5f）、滤波和伺服控制均在 FPGA 上实现。
-   **客户端-服务器架构**：在 RedPitaya 上自主运行。一个或多个 GUI 客户端或 Python 客户端可同时连接到服务器。
-   **自动锁定**：点击并拖动选择一条谱线，Linien 将自动锁定到该谱线。该算法具有抗噪声和抗抖动能力。
-   **IQ 解调**：即时优化解调相位
-   **噪声分析**：记录误差信号的功率谱密度（PSD），用于分析锁定激光的噪声并优化 PID 参数
-   **锁定检测**：Linien 能够检测锁定丢失（暂时禁用，如需此功能请使用 [v0.3.2](https://github.com/linien-org/linien/releases/tag/v0.3.2)）
-   **自动重新锁定**：如果锁定丢失，将自动重新锁定（暂时禁用，如需此功能请使用 [v0.3.2](https://github.com/linien-org/linien/releases/tag/v0.3.2)）
-   **机器学习**用于调节光谱参数以优化信号
-   **远程控制**：客户端库可通过 Python 控制或监控光谱锁定。
-   **FMS+MTS 组合**：Linien 支持双通道光谱，可用于实现 [组合 FMS+MTS](https://arxiv.org/pdf/1701.01918.pdf)
-   **日志记录**：锁定状态和参数可记录到 InfluxDB v2。
-   **第二积分器**用于 ECDL 中压电陶瓷的慢速控制
-   **额外模拟输出**可通过 GUI 或 Python 客户端使用（ANALOG_OUT 1、2 和 3）
-   **16 个 GPIO 输出**可编程（例如用于控制其他设备）

![image](https://raw.githubusercontent.com/linien-org/linien/master/docs/screencast.gif)

## 快速入门：安装 Linien

Linien 可在 Windows 和 Linux 上运行。对于 Windows 用户，推荐使用包含图形用户界面的[独立可执行文件](#standalone-binary)。
这些可执行文件运行在实验室 PC 上，包含了让 Linien 在 RedPitaya 上运行所需的一切。

从 Linien 2.0 开始，仅支持 RedPitaya OS 2.x。Linien 1.x 可在 RedPitaya OS 上运行，但不再积极维护。

### 独立可执行文件

您可以在[发布页面](https://github.com/linien-org/linien/releases)下载 Windows 的独立可执行文件（下载最新版本 assets 部分中的可执行文件）。对于 Linux 用户，我们推荐通过 pip 安装 `linien-gui`。

### 使用 pip 安装

Linien 使用 Python 3 编写，可通过 Python 的包管理器 pip 安装：

```bash
pip install linien-gui
```

通过在终端中运行以下命令启动 GUI：

```bash
linien
```

（Linux 和 Windows 均可）

如果您只需要 Python 客户端而不想安装图形应用程序，可以使用 `linien-client` 包：

```bash
pip install linien-client
```

### 在 RedPitaya 上安装服务器

在 RedPitaya 上安装 Linien 服务器组件最简单的方法是使用图形用户界面。首次连接到 RedPitaya 时，服务器会自动安装。

如果您使用的是 `linien-client`，可以通过以下方式安装服务器：

```python
from linien_client.device import Device
from linien_client.deploy import install_remote_server

device = Device(
    host="rp-xxxxxx.local",
    username="root",
    password="root"    
)
install_remote_server(device)
```

最后，您也可以通过 SSH 连接到 RedPitaya 手动安装服务器，然后运行

```bash
pip install linien-server
```

然后可以将服务器作为 systemd 服务启动，运行

```bash
linien-server start
```

在 RedPitaya 上运行。要检查服务器状态，运行


```bash
linien-server status
```

 欲了解更多选项，运行

```bash
linien-server --help
```

物理设置
--------------

默认设置如下所示：

![image](https://raw.githubusercontent.com/linien-org/linien/master/docs/setup.png)

您也可以为不同的设置配置 Linien，例如，如果您希望调制频率和控制信号使用同一输出。此外，还可以在 ANALOG OUT 0（0 V 至 1.8 V）上设置慢速积分器。

![image](https://raw.githubusercontent.com/linien-org/linien/master/docs/explain-pins.png)

使用应用程序
-------------

### 首次运行：连接到 RedPitaya

启动 Linien 后，您需要提供 RedPitaya 的连接信息。其主机地址通常为 <pre>rp-<b>XXXXXX.local</b></pre>，其中 **XXXXXX** 是设备 MAC 地址的最后 6 位数字。您可以在以太网端口上的贴纸上找到这些数字：

![image](https://raw.githubusercontent.com/linien-org/linien/master/docs/mac.jpg)

| :exclamation: 如果使用主机名连接失败，请尝试使用 RP 的 IP 地址 |
|--------------------------------------------------------------------------------------|


用户名和密码的默认值为 `root`（但您可能需要更改密码...）。

首次连接到 RedPitaya 时，Linien 会提示您安装服务器组件。请注意，这需要 RedPitaya 具有互联网访问权限（仅局域网访问不够）。

服务器库安装完成后，Linien 将自动运行服务器并连接。您无需在服务器上手动启动或停止任何操作，客户端会自动处理这些。

服务器将自主运行：关闭客户端应用程序不会影响锁定状态。您还可以启动多个客户端连接到同一服务器。

### 初始设置

首先需要设置的是输入和输出信号的配置：

将交流光谱信号连接到 FAST IN 1。如果您还想监测直流光谱信号，请将其连接到 FAST IN 2。

然后，根据您的需要调整输出信号：

![image](https://raw.githubusercontent.com/linien-org/linien/master/docs/explain-pins.png)

完成后，进入*调制、扫描与光谱*（Modulation, Sweep & Spectroscopy）配置调制频率和幅度。当您的设置正常工作时，您应该会看到类似如下的画面：

![image](https://raw.githubusercontent.com/linien-org/linien/master/docs/spectrum.jpg)

亮红色线条是解调后的光谱信号。深红色区域是通过 [IQ 解调](https://en.wikipedia.org/wiki/In-phase_and_quadrature_components)获得的信号强度，即在该点进行同相解调时获得的解调信号。

### 纯 PID 模式

纯 PID 模式用于基本的 PID 操作（无解调或滤波），绕过大部分 FPGA 功能。启用后，信号流为 FAST IN 1 → PID → FAST OUT 2。这在需要高控制带宽时非常有用：纯 PID 模式将传播延迟从 320 ns 降低到 125 ns，这在激光锁相时可能会有明显差异。

### 使用机器学习优化光谱参数

Linien 可以使用机器学习来最大化谱线的斜率。与自动锁定类似，点击并拖动选择您要优化的谱线。然后，该谱线将被居中，优化过程随即开始。请注意，这仅在初始时能清晰看到零交叉点的情况下有效。

![image](https://raw.githubusercontent.com/linien-org/linien/master/docs/optimization.gif)

### 使用自动锁定

使用自动锁定前，请先设置一些 PID 参数。注意，参数的符号会自动确定。点击绿色按钮后，通过点击并拖动来选择要锁定的谱线：您的选择应包含谱线的两个极值。自动锁定将使该谱线居中，缩小扫描范围，并尝试锁定到您选择区域内最小值和最大值之间的中点。

![image](https://raw.githubusercontent.com/linien-org/linien/master/docs/screencast.gif)

以下选项可用：
 * **确定信号偏移**：如果勾选此复选框，自动锁定将调整信号的 Y 轴偏移，使最小值和最大值之间的中点位于零交叉处。这在存在较大背景信号时（例如 FMS 光谱中的多普勒背景）特别有用。
 * **检查锁定**：开启锁定后立即检查控制信号。如果控制信号偏移过大，则认为锁定失败。
 * **监控锁定**：此选项让 Linien 在激光锁定后持续监控控制信号。如果检测到剧烈变化，将发起重新锁定。

如果您在使用自动锁定时遇到问题，最可能的原因是信噪比较差或激光抖动较强。

#### 自动锁定算法

Linien 实现了两种不同的自动锁定算法：

 * **鲁棒模式**：该算法运行在 FPGA 上，分析峰值形状以在正确的扫描位置开启锁定。它能够应对大量抖动，因为完全在 FPGA 上运行，即 CPU 和 FPGA 之间没有通信延迟。
 * **简单模式**：该算法在 CPU 上使用简单的自相关计算来确定锁定应从扫描的哪个点开始。该算法比第一种简单，适用于在抖动容忍模式下遇到问题时使用。由于需要 CPU 和 FPGA 之间的一些通信（会产生延迟），如果谱线抖动较大，可能会出现问题。

 默认使用**自动检测模式**：该模式根据抖动量自动选择算法。


### 使用手动锁定

如果您在使用自动锁定时遇到问题，也可以手动锁定。激活*手动*（Manual）选项卡，使用顶部的控制（*缩放*和*位置*）将目标谱线居中。选择目标斜率是上升还是下降，然后点击绿色按钮。

### 日志记录

Linien 可以选择将锁定状态和参数记录到 InfluxDB。目前仅支持 InfluxDB 2.x。日志记录可通过 Linien GUI 中的日志菜单进行配置，但即使客户端关闭，日志记录也会继续。数据点的时间戳由 InfluxDB 确定，而非 RedPitaya。如果更新/检查 InfluxDB 凭据失败，失败指示器 ❌ 的工具提示中有额外的信息。

参数名称记录在 [`parameters.py`](https://github.com/linien-org/linien/blob/master/linien-server/linien_server/parameters.py) 中。`signal_stats` 参数包含输入和输出信号的统计信息，例如 `control_signal_mean` 或 `monitor_signal_max`。

传递函数
---------

PID 的传递函数为
```
L(f) = kp + ki / f + kd * f
```
其中 `kp=P/4096`，`ki=I/0.1s`，`kd=D / (2**6 * 125e6)`。
注意，此方程未考虑 PID 之前的滤波（参见*调制、扫描与光谱*选项卡）。

![image](https://raw.githubusercontent.com/linien-org/linien/master/docs/transfer.png)

脚本接口
--------

除了 GUI，Linien 还可以使用 Python 进行控制。为此，需要通过 pip 安装（见上文）。

然后，您需要在 RedPitaya 上启动 Linien 服务器。可以通过运行 GUI 客户端并连接到设备来完成（见上文）。另外，`LinienClient` 的 `connect` 方法提供了 `autostart_server` 选项。

服务器启动运行后，您可以使用 Python 连接：
```python
from linien_client.device import Device
from linien_client.connection import LinienClient
from linien_common.common import  MHz, Vpp, ANALOG_OUT_V

dev = Device(
    host="rp-xxxxxx.local",
    username="root",
    password="root"    
)
c = LinienClient(dev)
c.connect(autostart_server=True, use_parameter_cache=True)

# 读取调制频率
print(c.parameters.modulation_frequency.value / MHz)

# 请查看 https://github.com/linien-org/linien/blob/master/linien/server/parameters.py
# 了解所有可访问和修改的参数文档

# 设置调制幅度
c.parameters.modulation_amplitude.value = 1 * Vpp
# 在上面的代码行中，我们设置了一个参数。但它不会直接写入
# FPGA。为此，我们需要调用 write_registers()：
c.connection.root.write_registers()

# 额外将 ANALOG_OUT_1 设置为 1.2 伏直流（可用于控制实验中的其他设备）
c.parameters.analog_out_1.value = 1.2 / ANALOG_OUT_V

# GPIO 输出也可以设置
# 每个位对应一个引脚
# 示例：启用所有 N 引脚并禁用所有 P 引脚
c.parameters.gpio_n_out.value = 0b11111111
c.parameters.gpio_p_out.value = 0b00000000
# 示例：启用 N 引脚 1-4 并禁用 N 引脚 5-8
c.parameters.gpio_n_out.value = 0b11110000 # 4 个开，4 个关
# 示例：每隔一个启用 P 引脚
c.parameters.gpio_p_out.value = 0b01010101 # 4 个开，4 个关

# 同样，我们需要调用 write_registers 以将数据写入 FPGA
c.connection.root.write_registers()

# 还可以设置一个回调函数，当参数发生变化时被调用
# （记得定期调用 `check_for_changed_parameters()`）
def callback(value):
    # 当服务器上的 `my_param` 发生变化时调用此函数。
    # 注意，这仅在定期调用 `check_for_changed_parameters` 时有效，
    # 因为该函数负责检查参数是否发生变化。
    print('parameter arrived!', value)

c.parameters.modulation_amplitude.add_callback(callback)

from time import sleep
for i in range(10):
    c.parameters.check_for_changed_parameters()
    if i == 2:
        c.parameters.modulation_amplitude.value = 0.1 * Vpp
    sleep(.1)

# 绘制控制信号和误差信号
import pickle
from matplotlib import pyplot as plt
plot_data = pickle.loads(c.parameters.to_plot.value)

# 根据状态（锁定/未锁定），可用的信号不同
print(plot_data.keys())

# 如果未锁定，signal1 和 signal2 包含通道 1 和通道 2 的误差信号
# 如果激光已锁定，它们包含误差信号和控制信号。
if c.parameters.lock.value:
    plt.title('laser is locked!')
    plt.plot(plot_data['control_signal'], label='control signal')
    plt.plot(plot_data['error_signal'], label='error signal')
else:
    plt.title('laser is sweeping!')
    plt.plot(plot_data['error_signal_1'], label='error signal channel 1')
    plt.plot(plot_data['error_signal_2'], label='error signal channel 2')

plt.legend()
plt.show()
```

有关可控制或访问的参数完整列表，请查看
[parameters.py](https://github.com/linien-org/linien/blob/master/linien/server/parameters.py)。请注意，更改的参数不会写入 FPGA，除非调用 `c.connection.root.write_registers()`。

### 运行自动锁定

下面的脚本展示了如何使用脚本接口运行自动锁定的示例：

```python
import pickle
import numpy as np

from linien_client.connection import LinienClient
from linien_common.common import FAST_AUTOLOCK

from matplotlib import pyplot as plt
from time import sleep

c = LinienClient(
    host="rp-xxxxxx.local",
    username="root",
    password="root"
)
c.connect(autostart_server=True, use_parameter_cache=True)

c.parameters.autolock_mode_preference.value = FAST_AUTOLOCK


def wait_for_lock_status(should_be_locked):
    """等待激光锁定或解锁的辅助函数。"""
    counter = 0
    while True:
        to_plot = pickle.loads(c.parameters.to_plot.value)
        is_locked = "error_signal" in to_plot

        if is_locked == should_be_locked:
            break

        counter += 1
        if counter > 10:
            raise Exception("waited too long")

        sleep(1)


# 关闭锁定（如果正在运行）
c.connection.root.start_sweep()
# 等待激光解锁（如果需要）
wait_for_lock_status(False)


# 记录参考光谱
to_plot = pickle.loads(c.parameters.to_plot.value)
error_signal = to_plot["error_signal_1"]


# 绘制参考光谱并询问用户目标谱线的位置
plt.plot(error_signal)
plt.plot(to_plot["monitor_signal"])
plt.show()

print("Please specify the position of the target line. ")
x0 = int(input("enter index of a point that is on the left side of the target line: "))
x1 = int(input("enter index of a point that is on the right side of the target line: "))


# 再次显示锁定点
plt.axvline(x0, color="r")
plt.axvline(x1, color="r")
plt.plot(error_signal)
plt.show()


# 开启锁定
c.connection.root.start_autolock(x0, x1, pickle.dumps(error_signal))


# 等待激光实际锁定
try:
    wait_for_lock_status(True)
    print("locking the laser worked \o/")
except Exception:
    print("locking the laser failed :(")


```

更新 Linien
-----------

安装新版本的 Linien 之前，请打开之前安装的客户端并点击"关闭服务器"（Shutdown server）按钮。不用担心，您的设置和参数会被保存。然后按照上文[快速入门](#快速入门安装-linien)部分所述在本地 PC 上安装最新版客户端。下次连接到 RedPitaya 时，Linien 将安装匹配的服务器版本。


开发
----

有关开发的信息，请参阅 [wiki](https://github.com/linien-org/linien/wiki/Development)。

常见问题
--------

### 如何更新到新版本？

无需在 RedPitaya 上手动安装任何东西。
在您的电脑上运行新版本的 Linien 并连接到 RedPitaya。您将看到一个对话框，允许您安装相应的服务器组件。

### 我可以同时运行 Linien 和 RedPitaya 的 Web 应用/SCPI 接口吗？

不可以，因为 Linien 依赖于定制的 FPGA 比特流。

### Linien 可以实现多大的控制带宽？

传播延迟在普通模式下约为 320 ns，在纯 PID 模式下约为 125 ns。

### 为什么 Linien 运行时 RedPitaya 的以太网 LED 停止闪烁？

以太网 LED 闪烁[被发现会影响 RedPitaya 的模拟输出](https://github.com/RedPitaya/RedPitaya/issues/205)。由于这可能影响锁定稳定性，Linien 启动时会禁用以太网 LED 闪烁。

如果您想重新启用 LED，只需停止 Linien 服务器或重启 RedPitaya 即可。

故障排除
--------

### 连接问题

如果客户端无法连接到 RedPitaya，首先检查是否可以 ping 通它，运行

```bash
ping rp-f0xxxx.local
```

在命令行中运行。如果成功，检查是否可以通过 SSH 连接：

```bash
ssh rp-f0xxxx.local
```

在命令行中运行。如果成功，要检查 `linien-server` 是否正在运行，请检查 systemd 服务是否在运行。可以通过执行 `linien-server status` 来完成。错误信息也会显示出来。如果您要报告与连接问题相关的[issue](https://github.com/linien-org/linien/issues)，请提供此输出。调试信息也会存储在 `/root/.local/share/linien/linien.log` 中。

### 可能与 openSSH 冲突

请注意，如果客户端运行了 openSSH 服务器，可能会出现问题，参见[此处](https://github.com/orgs/linien-org/discussions/286)。

### 更新或安装失败

- 确保 RedPitaya 已连接到互联网
- 如果橙色 LED 停止闪烁且 RedPitaya 变得无响应，可能是 SD 卡出现了故障

引用
----

如果您在科学工作中使用了 Linien，请按以下方式引用我们：

```
@article{Wiegand2022,
   author = {B. Wiegand and B. Leykauf and R. Jördens and M. Krutzik},
   doi = {10.1063/5.0090384},
   issn = {10897623},
   issue = {6},
   journal = {Review of Scientific Instruments},
   month = {6},
   pmid = {35778046},
   title = {Linien: A versatile, user-friendly, open-source FPGA-based tool for frequency stabilization and spectroscopy parameter optimization},
   volume = {93},
   year = {2022},
}
```

许可证
-------
Linien ‒ 使用 RedPitaya (STEMlab 125-14) 进行激光锁定的用户友好工具，开箱即用。

Copyright © 2014-2015 Robert Jördens\
Copyright © 2018-2022 Benjamin Wiegand\
Copyright © 2021-2024 Bastian Leykauf\
Copyright © 2022 Christian Freier\
Copyright © 2023-2024 Doron Behar\


Linien 是自由软件：您可以根据自由软件基金会发布的 GNU 通用公共许可证的条款重新分发和/或修改它，许可证版本为第 3 版或（根据您的选择）任何更新版本。

Linien 的分发是希望它能够有用，但不提供任何保证；甚至没有适销性或特定用途适用性的暗示保证。有关更多详情，请参见 GNU 通用公共许可证。

您应该已经随 Linien 收到了 GNU 通用公共许可证的副本。如果没有，请参见 <https://www.gnu.org/licenses/>。

致谢
----

开发主要在柏林洪堡大学进行。

本工作由德国航天局（DLR）提供支持，资金由德国联邦经济和技术部（BMWi）在资助编号 DLR50WM2066 下提供。

另请参阅
--------

-   [RedPID](https://github.com/quartiq/redpid)：Linien 的基础
