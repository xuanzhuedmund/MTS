#!/bin/bash

PROJECT_ROOT="/root/MTS"
export PYTHONPATH="${PROJECT_ROOT}/linien-common:${PROJECT_ROOT}/linien-server"

echo "PYTHONPATH: $PYTHONPATH"

python3 -c "
import sys
import logging

logging.basicConfig(level=logging.DEBUG)

from linien_server.cli import LinienServerCLI

cli = LinienServerCLI()
cli.run()
"