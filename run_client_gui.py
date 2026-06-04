import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, os.path.join(PROJECT_ROOT, "linien-common"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "linien-client"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "linien-gui"))

from linien_gui.app import main

if __name__ == "__main__":
    main()