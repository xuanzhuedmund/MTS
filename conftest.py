"""Pytest configuration shared by the whole monorepo.

注入本地 ``linien-common`` 源码路径到 ``sys.path``，使测试在未安装该包时
也能直接 ``from linien_common...`` 进行导入。
"""

import os
import sys

_COMMON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "linien-common"))
if _COMMON_ROOT not in sys.path:
    sys.path.insert(0, _COMMON_ROOT)
