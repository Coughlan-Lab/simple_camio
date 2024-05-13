from .finger_aruco_2d import FingerAruco2DFP
from .finger_aruco_3d import FingerAruco3DFP
from .finger_sift_3d import FingerSift3DFP
from .finger_sift_2d import FingerSift2DFP
from .stylus_aruco_2d import StylusAruco2DFP
from .stylus_aruco_3d import StylusAruco3DFP
from .stylus_sift_3d import StylusSift3DFP
from .frame_processor import FrameProcessor
from ..content import Content
from ..state import State


def get_frame_processor(
    content: Content, pointer: State.Pointer, calibration_file: str
) -> FrameProcessor:

    if content.is_2D():
        if content.use_aruco():
            if pointer == State.Pointer.FINGER:
                return FingerAruco2DFP(content)
            else:
                return StylusAruco2DFP(content, calibration_file)
        else:
            return FingerSift2DFP(content, calibration_file)
    else:
        if content.use_aruco():
            if pointer == State.Pointer.FINGER:
                return FingerAruco3DFP(content, calibration_file)
            else:
                return StylusAruco3DFP(content, calibration_file)
        else:
            if pointer == State.Pointer.FINGER:
                return FingerSift3DFP(content, calibration_file)
            else:
                return StylusSift3DFP(content, calibration_file)


__all__ = ["get_frame_processor", "FrameProcessor"]
