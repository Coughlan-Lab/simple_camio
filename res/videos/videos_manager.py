import os


class VideosManager:
    VIDEOS_DIR = os.path.dirname(__file__)

    def __init__(self):
        self.calibration_tutorial = os.path.join(
            VideosManager.VIDEOS_DIR, "calibration_tutorial.mp4"
        )

        self.content_tutorial = os.path.join(
            VideosManager.VIDEOS_DIR, "content_tutorial.mp4"
        )


VideosManager = VideosManager()
