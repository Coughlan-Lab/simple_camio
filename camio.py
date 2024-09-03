import os
import sys
import threading as th
import time
from typing import Any, Dict, Optional

from src.frame_processing import VideoCapture, WindowManager
from src.input_handler import InputHandler, InputListener

os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
import cv2

from src.audio import STT, TTS, Announcement, AudioManager
from src.frame_processing import HandStatus, PoseDetector, SIFTModelDetector
from src.graph import Coords, Graph, PositionHandler, PositionInfo
from src.llm import LLM
from src.utils import *


class CamIO:
    POSITION_ANNOUNCEMENT_INTERVAL = 0.25

    def __init__(
        self, model: Dict[str, Any], tts_rate: int = 200, debug: bool = False
    ) -> None:
        self.description = model["context"].get("description", None)

        # Model graph
        self.graph = Graph(model["graph"])
        self.position_handler = PositionHandler(self.graph, model["meters_per_pixel"])
        self.last_pos_info = PositionInfo.none_info()

        # Frame processing
        self.window_manager = WindowManager(
            "CamIO", debug, model["template_image"], self.position_handler
        )
        self.model_detector = SIFTModelDetector(model["template_image"])
        self.pose_detector = PoseDetector(self.window_manager.template.shape[:2])
        self.hand_status_buffer = Buffer[HandStatus](3)

        # Audio
        self.tts = TTS("res/strings.json", rate=tts_rate)
        self.tts.on_announcement_ended = self.on_announcement_ended
        self.stt = STT(
            start_filename="res/start_stt.wav", end_filename="res/end_stt.wav"
        )
        self.audio_manager = AudioManager("res/crickets.wav", "res/pointing.mp3")

        # LLM
        self.llm = LLM(self.graph, model["context"])
        self.user_input_thread: Optional[CamIO.UserInputThread] = None

        self.fps_manager = FPSManager()

        self.debug = debug
        self.running = False

        self.input_listeners = {
            InputListener.STOP_INTERACTION: self.stop_interaction,
            InputListener.SAY_MAP_DESCRIPTION: self.say_map_description,
            InputListener.TOGGLE_TTS: self.tts.toggle_pause,
            InputListener.STOP: self.stop,
            InputListener.QUESTION: self.__on_spacebar_pressed,
        }

    def main_loop(self) -> None:
        cap = VideoCapture.get_capture()
        if cap is None:
            print("No camera found.")
            return

        frame = cap.read()
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
        while self.running and cap.is_opened():
            self.window_manager.update(frame)

            frame = cap.read()
            if frame is None:
                print("No camera image returned.")
                break

            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            ok, rotation = self.model_detector.detect(frame_gray)

            if not ok or rotation is None:
                self.audio_manager.update(HandStatus.NOT_FOUND)
                continue

            hand_status, finger_pos, frame = self.pose_detector.detect(frame, rotation)
            self.hand_status_buffer.add(hand_status)
            hand_status = self.hand_status_buffer.mode() or HandStatus.NOT_FOUND

            if not self.is_handling_user_input():
                self.audio_manager.update(hand_status)

            if hand_status != HandStatus.POINTING or finger_pos is None:
                if hand_status == HandStatus.MORE_THAN_ONE_HAND:
                    self.tts.more_than_one_hand()
                continue

            self.position_handler.process_position(Coords(*finger_pos))

            if not self.is_handling_user_input():
                self.__announce_position()

        self.audio_manager.stop()
        cap.stop()

        input_handler.disable_shortcuts()
        self.window_manager.close()

        self.stop_interaction()
        self.position_handler.clear()
        self.hand_status_buffer.clear()

        self.tts.goodbye()
        time.sleep(1)
        self.tts.stop()

    def is_handling_user_input(self) -> bool:
        return self.user_input_thread is not None

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

    def __announce_position(self) -> None:
        if (
            time.time() - self.last_pos_info.timestamp
            < CamIO.POSITION_ANNOUNCEMENT_INTERVAL
        ):
            return

        pos_info = self.position_handler.get_position_info()

        if len(pos_info.description) == 0 or (
            self.last_pos_info.is_still_valid()
            and pos_info.graph_element == self.last_pos_info.graph_element
            and pos_info.description == self.last_pos_info.description
        ):
            return

        if self.tts.position_info(pos_info):
            self.last_pos_info = pos_info

    def __on_spacebar_pressed(self) -> None:
        if self.stt.is_recording:
            self.stt.on_question_ended()
        elif self.is_handling_user_input():
            self.tts.waiting_llm()
        elif self.hand_status_buffer.mode() == HandStatus.POINTING:
            self.user_input_thread = self.UserInputThread(self)
            self.user_input_thread.start()

    class UserInputThread(th.Thread):
        def __init__(self, camio: "CamIO"):
            super().__init__()

            self.camio = camio
            self.stop_event = th.Event()

        def run(self) -> None:
            self.camio.tts.stop_speaking()
            position = self.camio.position_handler.current_position

            print("Listening...")
            recording = self.camio.stt.get_audio()
            if recording is None or self.stop_event.is_set():
                print("Stopping user input handler.")
                return

            if self.camio.hand_status_buffer.mode() == HandStatus.POINTING:
                position = self.camio.position_handler.current_position

            self.camio.tts.start_waiting_loop()

            question = self.camio.stt.audio_to_text(recording) or ""
            if self.stop_event.is_set():
                self.camio.tts.stop_waiting_loop()
                return

            if len(question) == 0:
                print("No question recognized.")
                self.camio.tts.stop_waiting_loop()
                self.camio.tts.error()
                return

            print(f"Question: {question}")

            answer = self.camio.llm.ask(question, position) or ""
            self.camio.tts.stop_waiting_loop()
            if self.stop_event.is_set():
                return

            self.process_answer(answer)
            self.camio.user_input_thread = None

        def process_answer(self, answer: str) -> None:
            self.camio.tts.stop_speaking()

            if len(answer) == 0:
                print("No answer received.")
                self.camio.tts.error()
            else:
                print(f"Answer: {answer}")
                self.camio.tts.llm_response(answer)
            self.camio.tts.pause(2.0)

        def stop(self) -> None:
            self.stop_event.set()
            self.camio.llm.stop()
            self.camio.tts.stop_waiting_loop()
            self.camio.user_input_thread = None

    def on_announcement_ended(self, category: Announcement.Category) -> None:
        if (
            category == Announcement.Category.LLM
            and self.hand_status_buffer.mode() == HandStatus.POINTING
        ):
            self.audio_manager.play_pointing()


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

    except Exception as e:
        print(f"An error occurred")
        print(e)

    finally:
        if camio is not None:
            camio.stop()
            camio.save_chat(args.out)
            print(f"Chat saved to {args.out}")
