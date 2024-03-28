import os


class VideoManager:
    VIDEOS_DIR = os.path.dirname(__file__)

    def __init__(self) -> None:
        self.calibration_tutorial = os.path.join(
            VideoManager.VIDEOS_DIR, "calibration_tutorial.mp4"
        )

        self.content_tutorial = os.path.join(
            VideoManager.VIDEOS_DIR, "content_tutorial.mp4"
        )


singleton: VideoManager = VideoManager()
