import os
import sys
import threading as th
import time
from typing import Any, Dict, Optional

os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
import cv2
import keyboard

from src.audio import (STT, TTS, AmbientSoundPlayer, Announcement,
                       AnnouncementType)
from src.frame_processing import HandStatus, PoseDetector, SIFTModelDetector
from src.graph import Coords, Graph, PositionData, PositionHandler
from src.llm import LLM
from src.utils import *


class CamIO:

    def __init__(self, model: Dict[str, Any], debug: bool = False) -> None:
        self.description = model["context"].get("description", None)

        # Model graph
        self.graph = Graph(model["graph"])
        self.position_handler = PositionHandler(self.graph, model["meters_per_pixel"])
        self.last_position_announcement = PositionData.none_announcement()

        # Frame processing
        self.model_detector = SIFTModelDetector(model["template_image"])
        self.pose_detector = PoseDetector()
        self.template = cv2.imread(model["template_image"], cv2.IMREAD_COLOR)

        # TTS and STT
        self.tts = TTS("res/strings.json")
        self.stt = STT(
            start_filename="res/start_stt.wav", end_filename="res/end_stt.wav"
        )

        # LLM
        self.llm = LLM(self.graph, model["context"])
        self.user_input_thread: Optional[CamIO.UserInputThread] = None

        self.fps_manager = FPSManager()

        self.debug = debug
        self.running = False

    def main_loop(self) -> None:
        cap = self.__get_capture()
        if cap is None:
            print("No camera found.")
            return

        ok, frame = cap.read()
        if not ok:
            print("No camera image returned.")
            return

        self.stt.calibrate()
        self.tts.start()

        self.__init_shortcuts()

        self.tts.welcome()
        self.tts.instructions()
        if self.description is not None:
            self.tts.say(
                f"Map description:\n {self.description}",
                announcement_type=AnnouncementType.MAP_DESCRIPTION,
            )

        ambient_sound_player = AmbientSoundPlayer(
            "res/white_noise.mp3", "res/crickets.mp3"
        )

        self.running = True
        while self.running and cap.isOpened():
            self.fps_manager.update()

            if self.debug:
                self.__draw_debug_info()

            cv2.imshow("CamIO", frame)
            cv2.waitKey(1)  # Necessary for the window to show

            ret, frame = cap.read()
            if not ret:
                print("No camera image returned.")
                break

            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            ok, rotation = self.model_detector.detect(frame_gray)

            if not ok or rotation is None:
                continue

            gesture_status, gesture_position, frame = self.pose_detector.detect(
                frame, rotation
            )

            ambient_sound_player.update(gesture_status)
            if gesture_status != HandStatus.POINTING or gesture_position is None:
                continue

            self.position_handler.process_position(Coords(*gesture_position))
            self.__announce_position()

        ambient_sound_player.stop()
        cap.release()

        self.__disable_shortcuts()
        cv2.destroyAllWindows()

        self.stop_interaction()
        self.position_handler.clear()

        self.tts.goodbye()
        time.sleep(1)
        self.tts.stop()

    def stop(self) -> None:
        self.running = False

    def save_chat(self, filename: str) -> None:
        self.llm.save_chat(filename)

    def is_busy(self) -> bool:
        return (
            self.tts.is_speaking()
            or self.stt.is_processing()
            or self.llm.is_waiting_for_response()
        )

    def stop_interaction(self) -> None:
        self.tts.stop_speaking()
        self.stt.stop_processing()

        if self.user_input_thread is not None:
            self.user_input_thread.stop()

    def say_map_description(self, _: Any = None) -> None:
        self.stop_interaction()

        if self.description is not None:
            self.tts.say(
                self.description,
                priority=Announcement.Priority.HIGH,
                stop_current=True,
                announcement_type=AnnouncementType.MAP_DESCRIPTION,
            )
        else:
            self.tts.no_description()

    def __init_shortcuts(self) -> None:
        keyboard.add_hotkey("space", self.__on_spacebar_pressed)
        keyboard.add_hotkey("enter", self.stop_interaction)
        keyboard.add_hotkey("esc", self.stop)
        keyboard.on_press_key("cmd", self.say_map_description)

    def __disable_shortcuts(self) -> None:
        keyboard.unhook_all()

    def __get_capture(self) -> Optional[cv2.VideoCapture]:
        cam_port = 1  # select_camera_port()
        if cam_port is None:
            return None

        cap = cv2.VideoCapture(cam_port)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FOCUS, 0)

        return cap

    def __draw_debug_info(self) -> None:
        template = self.template.copy()
        pos = self.position_handler.get_current_position()

        if pos is not None:
            pos /= self.position_handler.meters_per_pixel
            x, y = int(pos.x), int(pos.y)
            cv2.circle(template, (x, y), 10, (255, 0, 0), -1)

        cv2.putText(
            template,
            f"FPS: {self.fps_manager.fps:.2f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 0),
            2,
        )

        cv2.imshow("CamIO - Debug", template)

    def __announce_position(self) -> None:
        announcement = self.position_handler.get_next_announcement()

        if (
            len(announcement) == 0
            or announcement.description == self.last_position_announcement.description
        ):
            return

        stop_current_announcement = (
            self.last_position_announcement.graph_nearest_element
            != announcement.graph_nearest_element
        )

        self.tts.say(
            announcement.description,
            announcement_type=AnnouncementType.POSITION_UPDATE,
            priority=Announcement.Priority.LOW,
            stop_current=stop_current_announcement,
        )
        self.last_position_announcement = announcement

    def __on_spacebar_pressed(self) -> None:
        if self.stt.is_processing():
            self.stt.on_question_ended()
        else:
            self.user_input_thread = self.UserInputThread(self)
            self.user_input_thread.start()

    class UserInputThread(th.Thread):
        def __init__(self, camio: "CamIO"):
            super().__init__()
            self.camio = camio

            self.stop_event = th.Event()

        def run(self) -> None:
            self.camio.tts.stop_speaking()

            if self.camio.llm.is_waiting_for_response():
                self.camio.tts.waiting_llm()
                return

            print("Listening...")
            question = self.camio.stt.process_input()
            if question is None or self.stop_event.is_set():
                print("Stopping user input handler.")
                return
            print(f"Question: {question}")

            position = self.camio.position_handler.get_current_position()

            self.camio.tts.start_waiting_loop()
            answer = self.camio.llm.ask(question, position)
            if self.stop_event.is_set():
                return
            self.camio.tts.stop_waiting_loop()

            self.process_answer(answer)
            self.camio.user_input_thread = None

        def process_answer(self, answer: Optional[str]) -> None:
            self.camio.tts.stop_speaking()

            if not self.camio.stt.processing_input:
                if answer is None or answer == "":
                    print("No answer received.")
                    self.camio.tts.llm_error()
                else:
                    print(f"Answer: {answer}")
                    self.camio.tts.say(
                        answer,
                        stop_current=True,
                        priority=Announcement.Priority.HIGH,
                        announcement_type=AnnouncementType.LLM_RESPONSE,
                    )

        def stop(self) -> None:
            self.stop_event.set()
            self.camio.llm.stop()
            self.camio.tts.stop_waiting_loop()
            self.camio.user_input_thread = None


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

    camio = CamIO(model, debug=args.debug)

    try:
        camio.main_loop()
    except KeyboardInterrupt:
        camio.stop()

    camio.save_chat(args.out)
    print(f"Chat saved to {args.out}")
