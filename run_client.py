import sys
sys.path.insert(0, r'%PROJECT_ROOT%linien-common')
sys.path.insert(0, r'%PROJECT_ROOT%linien-client')

from linien_client.device import Device
from linien_client.connection import LinienClient
from linien_common.common import MHz, Vpp

dev = Device(
    host='rp-f0cb9a.local',
    username='root',
    password='root'
)

c = LinienClient(dev)
c.connect(autostart_server=True, use_parameter_cache=True)

print('连接成功！')
print(f'服务器版本: {c.connection.root.exposed_get_server_version()}')
print(f'调制频率: {c.parameters.modulation_frequency.value / MHz} MHz')
print(f'扫描幅度: {c.parameters.sweep_amplitude.value}')

try:
    import time
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print('断开连接...')
    c.disconnect()