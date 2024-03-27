import os
import platform
import subprocess

system = platform.system()

if system == "Darwin":
    def open_file(path: str) -> None:
        if not os.path.exists(path):
            return
        subprocess.call(['open', path])
elif system == "Windows":
    def open_file(path: str) -> None:
        os.startfile(path)
else:
    def open_file(path: str) -> None:
        raise NotImplementedError(f"Unknown os: {system}")