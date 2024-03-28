# mypy: ignore-errors
from ..content import Content
from .frame_processor import FrameProcessor


class Stylus3DFrameProcessor(FrameProcessor):
    def __init__(self, content: Content, calibration_file: str) -> None:
        FrameProcessor.__init__(self, content, calibration_file)
