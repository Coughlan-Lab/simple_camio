import os
import sys
import threading as th
import time
from functools import partial
from typing import Any, Dict, Optional

from src.frame_processing import VideoCapture, WindowManager
from src.input_handler import InputHandler, InputListener

os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
import cv2

from src.audio import STT, Announcement, AudioManager, CamIOTTS
from src.frame_processing import HandStatus, PoseDetector, SIFTModelDetector
from src.graph import Coords, Graph, PositionHandler, PositionInfo
from src.llm import LLM
from src.utils import *


class CamIO:

    def __init__(
        self, model: Dict[str, Any], tts_rate: int = 200, debug: bool = False
    ) -> None:
        self.description = model["context"].get("description", None)

        # Model graph
        self.graph = Graph(model["graph"], meters_per_cm=model["meters_per_cm"])
        self.position_handler = PositionHandler(
            self.graph,
            meters_per_pixel=model["meters_per_pixel"],
            meters_per_cm=model["meters_per_cm"],
        )
        self.last_pos_info = PositionInfo.none_info()

        # Frame processing
        self.window_manager = WindowManager(
            "CamIO", debug, model["template_image"], self.position_handler
        )
        self.model_detector = SIFTModelDetector(model["template_image"])
        template = cv2.imread(model["template_image"], cv2.IMREAD_GRAYSCALE)
        self.pose_detector = PoseDetector(template.shape[:2])
        self.hand_status_buffer = Buffer[HandStatus](max_size=5, max_life=5)

        # Audio
        self.tts = CamIOTTS("res/strings.json", rate=tts_rate)
        self.tts.on_announcement_ended = self.on_announcement_ended
        self.stt = STT(
            start_filename="res/start_stt.wav", end_filename="res/end_stt.wav"
        )
        self.audio_manager = AudioManager("res/crickets.wav", "res/pointing.mp3")

        # LLM
        self.llm = LLM(self.graph, model["context"])
        self.user_input_thread: Optional[UserInputThread] = None

        self.debug = debug
        self.running = False

        self.input_listeners = {
            InputListener.STOP_INTERACTION: partial(self.stop_interaction),
            InputListener.SAY_MAP_DESCRIPTION: partial(self.say_map_description),
            InputListener.TOGGLE_TTS: partial(self.tts.toggle_pause),
            InputListener.STOP: partial(self.stop),
            InputListener.QUESTION: partial(self.__on_spacebar_pressed),
        }

    def main_loop(self) -> None:
        video_capture = VideoCapture.get_capture()
        if video_capture is None:
            print("No camera found.")
            return

        frame = video_capture.read()
        if frame is None:
            print("No camera image returned.")
            return

        self.stt.calibrate()
        self.tts.start()

        input_handler = InputHandler(self.input_listeners)
        input_handler.init_shortcuts()

        self.tts.welcome()
        self.tts.instructions()
        if self.description is not None:
            self.tts.map_description(self.description)

        self.audio_manager.start()

        self.running = True
        while self.running and video_capture.is_opened():
            self.window_manager.update(frame)

            frame = video_capture.read()
            if frame is None:
                print("No camera image returned.")
                break

            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            homography = self.model_detector.detect(frame_gray)

            if homography is None:
                self.audio_manager.update(HandStatus.NOT_FOUND)
                continue

            hand_status, finger_pos, frame = self.pose_detector.detect(
                frame, homography
            )

            hand_status = self.__process_hand_status(hand_status, finger_pos)
            if finger_pos is None:
                continue

            self.position_handler.process_position(finger_pos)
            if hand_status == HandStatus.POINTING and not self.is_handling_user_input():
                self.tts.announce_position(self.position_handler.get_position_info())

        self.audio_manager.stop()
        video_capture.stop()

        input_handler.disable_shortcuts()
        self.window_manager.close()

        self.stop_interaction()
        self.position_handler.clear()
        self.hand_status_buffer.clear()

        self.tts.goodbye()
        time.sleep(1)
        self.tts.stop()

    def is_handling_user_input(self) -> bool:
        return self.user_input_thread is not None and self.user_input_thread.is_alive()

    def stop(self) -> None:
        self.running = False

    def save_chat(self, filename: str) -> None:
        self.llm.save_chat(filename)

    def stop_interaction(self) -> None:
        self.tts.stop_speaking()

        if self.user_input_thread is not None:
            self.user_input_thread.stop()

        self.stt.on_question_ended()

    def say_map_description(self, _: Any = None) -> None:
        self.stop_interaction()

        if self.description is not None:
            self.tts.map_description(self.description)
        else:
            self.tts.no_map_description()

    def __process_hand_status(
        self, hand_status: HandStatus, finger_pos: Optional[Coords]
    ) -> HandStatus:

        if (
            hand_status == HandStatus.POINTING
            and finger_pos is not None
            and not self.position_handler.is_valid_position(
                finger_pos * self.position_handler.meters_per_pixel
            )
        ):
            hand_status = HandStatus.NOT_FOUND

        self.hand_status_buffer.add(hand_status)
        hand_status = self.hand_status_buffer.mode() or HandStatus.NOT_FOUND

        if hand_status == HandStatus.MORE_THAN_ONE_HAND:
            self.tts.more_than_one_hand()

        self.audio_manager.update(hand_status)

        return hand_status

    def __on_spacebar_pressed(self) -> None:
        if self.stt.is_recording:
            self.stt.on_question_ended()
        elif self.tts.current_announcement.category == Announcement.Category.LLM:
            pass
        elif self.is_handling_user_input():
            self.tts.start_waiting_llm()
        elif self.hand_status_buffer.mode() == HandStatus.POINTING:
            self.user_input_thread = UserInputThread(self)
            self.user_input_thread.start()
        else:
            self.tts.no_pointing()

    def on_announcement_ended(self, category: Announcement.Category) -> None:
        if (
            category == Announcement.Category.LLM
            and self.hand_status_buffer.mode() == HandStatus.POINTING
        ):
            self.audio_manager.play_pointing()


class UserInputThread(th.Thread):
    def __init__(self, camio: "CamIO"):
        super().__init__()

        self.camio = camio
        self.stop_event = th.Event()

    def run(self) -> None:
        self.tts.stop_speaking()
        position = self.position_handler.current_position

        print("Listening...")
        self.audio_manager.play_start_signal()
        recording = self.stt.get_audio()
        if recording is None or self.stop_event.is_set():
            print("Stopping user input handler.")
            return

        if self.hand_status == HandStatus.POINTING:
            position = self.position_handler.current_position

        self.tts.start_waiting_llm()

        question = self.stt.audio_to_text(recording) or ""
        if self.stop_event.is_set():
            self.tts.stop_waiting_llm()
            return

        if len(question) == 0:
            print("No question recognized.")
            self.tts.stop_waiting_llm()
            self.tts.question_error()
            return

        print(f"Question: {question}")

        answer = self.camio.llm.ask(question, position) or ""
        self.tts.stop_waiting_llm()
        if self.stop_event.is_set():
            return

        self.process_answer(answer)

    def process_answer(self, answer: str) -> None:
        self.tts.stop_speaking()

        if len(answer) == 0:
            print("No answer received.")
            self.tts.llm_error()
        else:
            print(f"Answer: {answer}")
            self.tts.llm_response(answer)

        self.tts.pause(2.0)

    def stop(self) -> None:
        if self.stop_event.is_set():
            return

        self.stop_event.set()
        self.llm.stop()
        self.tts.stop_waiting_llm()

    @property
    def stt(self) -> STT:
        return self.camio.stt

    @property
    def tts(self) -> CamIOTTS:
        return self.camio.tts

    @property
    def hand_status(self) -> HandStatus:
        return self.camio.hand_status_buffer.mode() or HandStatus.NOT_FOUND

    @property
    def position_handler(self) -> PositionHandler:
        return self.camio.position_handler

    @property
    def llm(self) -> LLM:
        return self.camio.llm

    @property
    def audio_manager(self) -> AudioManager:
        return self.camio.audio_manager


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    args = camio_parser.parse_args()

    out_dir = os.path.dirname(args.out)
    if not os.path.exists(out_dir):
        print(f"Directory {out_dir} does not exist.")
        sys.exit(0)

    model = load_map_parameters(args.model)
    if model is None:
        print(f"Model file {args.model} not found.")
        sys.exit(0)

    camio: Optional[CamIO] = None
    try:
        camio = CamIO(model, tts_rate=args.tts_rate, debug=args.debug)
        camio.main_loop()

    except KeyboardInterrupt:
        pass

    # except Exception as e:
    #    print(f"An error occurred:")
    #    print(e)

    finally:
        if camio is not None:
            camio.stop()
            camio.save_chat(args.out)
            print(f"Chat saved to {args.out}")
