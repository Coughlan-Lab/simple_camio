import os
import sys
import threading as th
import time
from typing import Any, Dict, Optional, Union

os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
import cv2
from pynput.keyboard import Key, KeyCode
from pynput.keyboard import Listener as KeyboardListener

from src.audio import STT, TTS, Announcement, AudioManager
from src.frame_processing import HandStatus, PoseDetector, SIFTModelDetector
from src.graph import Coords, Graph, PositionHandler, PositionInfo
from src.llm import LLM
from src.utils import *


class CamIO:
    POSITION_ANNOUNCEMENT_INTERVAL = 0.75

    def __init__(self, model: Dict[str, Any], debug: bool = False) -> None:
        self.description = model["context"].get("description", None)

        # Model graph
        self.graph = Graph(model["graph"])
        self.position_handler = PositionHandler(self.graph, model["meters_per_pixel"])
        self.last_pos_info = PositionInfo.none_info()

        # Frame processing
        self.template = cv2.imread(model["template_image"], cv2.IMREAD_COLOR)
        self.model_detector = SIFTModelDetector(model["template_image"])
        self.pose_detector = PoseDetector(self.template.shape[:2])

        # Audio
        self.tts = TTS("res/strings.json")
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
            self.tts.map_description(self.description)

        self.audio_manager.start()

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
                self.audio_manager.update(HandStatus.NOT_FOUND)
                continue

            gesture_status, gesture_position, frame = self.pose_detector.detect(
                frame, rotation
            )

            if not self.is_handling_user_input():
                self.audio_manager.update(gesture_status)

            if gesture_status != HandStatus.POINTING or gesture_position is None:
                if gesture_status == HandStatus.MORE_THAN_ONE_HAND:
                    self.stop_interaction()
                    self.tts.more_than_one_hand()
                continue

            self.position_handler.process_position(Coords(*gesture_position))

            if not self.is_handling_user_input():
                self.__announce_position()

        self.audio_manager.stop()
        cap.release()

        self.__disable_shortcuts()
        cv2.destroyAllWindows()

        self.stop_interaction()
        self.position_handler.clear()

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

    def __init_shortcuts(self) -> None:
        def on_press(key: Optional[Union[Key, KeyCode]]) -> None:
            if key == Key.space:
                self.__on_spacebar_pressed()
            elif key == Key.enter:
                self.tts.toggle_pause()
            elif key == Key.esc:
                self.stop_interaction()
            elif key == KeyCode.from_char("d"):
                self.say_map_description()
            elif key == KeyCode.from_char("q"):
                self.stop()

        self.keyboard = KeyboardListener(on_press=on_press)
        self.keyboard.start()

    def __disable_shortcuts(self) -> None:
        self.keyboard.stop()

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
        pos = self.position_handler.current_position

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

        for poi in self.graph.pois:
            if poi["enabled"]:
                x, y = poi["coords"] / self.position_handler.meters_per_pixel
                x, y = int(x), int(y)
                cv2.circle(template, (x, y), 10, (0, 0, 255), -1)

        cv2.imshow("CamIO - Debug", template)

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

        stop_current = self.last_pos_info.graph_element != pos_info.graph_element

        if self.tts.position_info(pos_info, stop_current=stop_current):
            self.last_pos_info = pos_info

    def __on_spacebar_pressed(self) -> None:
        if self.stt.is_recording:
            self.stt.on_question_ended()
        elif self.user_input_thread is not None:
            self.tts.waiting_llm()
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

            print("Listening...")
            recording = self.camio.stt.get_audio()
            if recording is None or self.stop_event.is_set():
                print("Stopping user input handler.")
                return

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
                self.camio.tts.say(
                    answer,
                    category=Announcement.Category.LLM,
                    priority=Announcement.Priority.HIGH,
                )
            self.camio.tts.pause(2.0)

        def stop(self) -> None:
            self.stop_event.set()
            self.camio.llm.stop()
            self.camio.tts.stop_waiting_loop()
            self.camio.user_input_thread = None

    def on_announcement_ended(self, category: Announcement.Category) -> None:
        if (
            category == Announcement.Category.LLM
            and self.audio_manager.last_hand_status == HandStatus.POINTING
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
        camio = CamIO(model, debug=args.debug)
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
