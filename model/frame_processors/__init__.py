from .finger_2d import Finger2DFrameProcessor
from .finger_3d import Finger3DFrameProcessor
from .stylus_2d import Stylus2DFrameProcessor
from .stylus_3d import Stylus3DFrameProcessor
from .frame_processor import FrameProcessor
from ..content import Content
from ..state import State


def get_frame_processor(
    content: Content, pointer: State.Pointer, calibration_file: str
) -> FrameProcessor:

    if content.is_2D():
        if pointer == State.Pointer.FINGER:
            return Finger2DFrameProcessor(content)
        else:
            return Stylus2DFrameProcessor(content, calibration_file)
    else:
        if pointer == State.Pointer.FINGER:
            return Finger3DFrameProcessor(content, calibration_file)
        else:
            return Stylus3DFrameProcessor(content, calibration_file)


__all__ = ["get_frame_processor"]
