import sys

from gui import ScreenName, create_gui

if __name__ == "__main__":
    screen = None
    if len(sys.argv) > 1 and sys.argv[1] in ScreenName.__members__:
        screen = ScreenName[sys.argv[1]]
    gui = create_gui()
    try:
        gui.start(screen)
    except KeyboardInterrupt as e:
        pass
    except Exception as e:
        print(e)
        gui.destroy()
