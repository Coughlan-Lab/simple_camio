from typing import Callable, Optional
import cv2
import numpy as np
import wx


class Timer(wx.Timer):
    def __init__(self, camera: "Camera") -> None:
        wx.Timer.__init__(self)
        self.camera = camera

    def Notify(self) -> None:
        self.camera.camera_loop()


class Camera:
    def __init__(self) -> None:
        self.capture: Optional[cv2.VideoCapture] = None
        self.fps: float

        self.on_error_listener: Optional[Callable[[], None]] = None
        self.frame_listener: Optional[Callable[[np.ndarray], None]] = None

        self.timer = Timer(self)

    def set_on_error_listener(self, listener: Callable[[], None]) -> None:
        self.on_error_listener = listener

    def set_frame_listener(self, listener: Callable[[np.ndarray], None]) -> None:
        self.frame_listener = listener

    @property
    def running(self) -> bool:
        return self.capture is not None and self.capture.isOpened()

    def start_by_index(self, camera_index: int) -> None:
        if self.running:
            return

        self.capture = cv2.VideoCapture(camera_index)
        self.capture.set(cv2.CAP_PROP_FOCUS, 0)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        
        self.fps = self.capture.get(cv2.CAP_PROP_FPS)

        wx.CallAfter(lambda: self.timer.Start(int(1000 / self.fps)))

    def start_by_capture(self, capture: cv2.VideoCapture) -> None:
        if self.running:
            return

        self.capture = capture
        self.capture.set(cv2.CAP_PROP_FOCUS, 0)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        
        self.fps = self.capture.get(cv2.CAP_PROP_FPS)

        wx.CallAfter(lambda: self.timer.Start(int(1000 / self.fps)))

    def camera_loop(self) -> None:
        if self.capture is None or not self.capture.isOpened():
            return
        ret, image = self.capture.read()
        if not ret:
            self.__on_error()
        else:
            self.__on_frame(image)

    def __on_error(self) -> None:
        self.__release_camera()
        if self.on_error_listener is not None:
            self.on_error_listener()

    def __on_frame(self, img: np.ndarray) -> None:
        if self.frame_listener is not None:
            self.frame_listener(img)

    def stop(self) -> None:
        self.__release_camera()

    def acquire_capture(self) -> cv2.VideoCapture:
        """Release ownership of the camera capture object."""
        self.timer.Stop()
        capture = self.capture
        self.capture = None
        return capture

    def __release_camera(self) -> None:
        self.timer.Stop()
        if self.capture is None:
            return
        if self.capture.isOpened():
            self.capture.release()
        self.capture = None
