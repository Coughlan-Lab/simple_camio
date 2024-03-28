from .frame_processor import FrameProcessor


class Finger3DFrameProcessor(FrameProcessor):
    def __init__(self, content):
        super().__init__(content)
        self.content = content
