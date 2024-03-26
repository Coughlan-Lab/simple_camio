import customtkinter as tk
from typing import Callable, Optional
import cv2
import numpy as np
from typing import Union


class Camera(tk.CTkFrame):
    def __init__(self, parent: Union[tk.CTkFrame, tk.CTk]):
        tk.CTkFrame.__init__(self, parent)

        self.capture: Optional[cv2.VideoCapture] = None
        self.fps: float

        self.on_error_listener: Optional[Callable[[], None]] = None
        self.frame_listener: Optional[Callable[[np.ndarray], None]] = None

    def set_on_error_listener(self, listener: Callable[[], None]) -> None:
        self.on_error_listener = listener

    def set_frame_listener(self, listener: Callable[[np.ndarray], None]) -> None:
        self.frame_listener = listener

    @property
    def running(self) -> bool:
        return self.capture is not None and self.capture.isOpened()

    def start(self, camera_index: int) -> None:
        if self.running:
            return
        self.capture = cv2.VideoCapture(camera_index)
        self.capture.set(cv2.CAP_PROP_FOCUS, 0)
        self.fps = self.capture.get(cv2.CAP_PROP_FPS)
        self.__camera_loop()

    def __camera_loop(self) -> None:
        if not self.running:
            return
        ret, image = self.capture.read()
        if not ret:
            self.__on_error()
        else:
            self.__on_frame(image)
            self.after(int(1000 / self.fps), self.__camera_loop)

    def __on_error(self) -> None:
        self.__release_camera()
        if self.on_error_listener is not None:
            self.on_error_listener()

    def __on_frame(self, img: np.ndarray) -> None:
        if self.frame_listener is not None:
            self.frame_listener(img)

    def stop(self) -> None:
        self.__release_camera()

    def __release_camera(self) -> None:
        if not self.running:
            return
        self.capture.release()
        self.capture = None
