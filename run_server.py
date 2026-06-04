import sys
import logging

PROJECT_ROOT = "/root/MTS"
sys.path.insert(0, f"{PROJECT_ROOT}/linien-common")
sys.path.insert(0, f"{PROJECT_ROOT}/linien-server")

logging.basicConfig(level=logging.DEBUG)

from linien_server.cli import LinienServerCLI

if __name__ == "__main__":
    cli = LinienServerCLI()
    cli.run()