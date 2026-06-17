# This file is part of Linien and based on redpid.
#
# Copyright (C) 2016-2024 Linien Authors (https://github.com/linien-org/linien#license)
#
# Linien is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Linien is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Linien.  If not, see <http://www.gnu.org/licenses/>.

import logging
from logging.handlers import RotatingFileHandler

import importlib_metadata

# 通过相对路径直接导入 linien-common 包，避免依赖该包的安装
import os as _os
import sys as _sys

_COMMON_ROOT = _os.path.abspath(
    _os.path.join(_os.path.dirname(__file__), _os.pardir, _os.pardir, "linien-common")
)
if _COMMON_ROOT not in _sys.path:
    _sys.path.insert(0, _COMMON_ROOT)

from linien_common.config import LOG_FILE_PATH

# __version__ = importlib_metadata.version("linien-server")  # noqa: F401
__version__ = "2.1.0"

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

file_handler = RotatingFileHandler(str(LOG_FILE_PATH), maxBytes=1000000, backupCount=10)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter("%(name)-30s %(levelname)-8s %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)
