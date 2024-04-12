import sys
import os

from gui import ScreenName, create_gui
from model import utils

if utils.SYSTEM == utils.OS.MACOS and utils.is_executable():
    os.chdir(utils.getcwd())

if __name__ == "__main__":
    screen = None
    if len(sys.argv) > 1 and sys.argv[1] in ScreenName.__members__:
        screen = ScreenName[sys.argv[1]]

    try:
        gui = create_gui()
        gui.start(screen)
    except KeyboardInterrupt as e:
        sys.exit(0)
    except Exception as e:
        print(e)
        gui.destroy()
