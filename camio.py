import os
import sys
import threading as th
import time
from typing import Any, Dict, Optional

import cv2
import keyboard
import pyglet.media

from src.audio import STT, TTS, AmbientSoundPlayer
from src.frame_processing import PoseDetector, SIFTModelDetector
from src.graph import Coords, Graph
from src.llm import LLM
from src.utils import *


class CamIO:
    NODE_DISTANCE_THRESHOLD = 20
    EDGE_DISTANCE_THRESHOLD = 40

    def __init__(self, model: Dict[str, Any]) -> None:
        self.description = model["context"].get("description", None)

        # Model graph
        self.graph = Graph(model["graph"])
        self.finger_buffer = Buffer(5)
        self.edge_buffer = Buffer(10)

        # Frame processing
        self.model_detector = SIFTModelDetector(model["template_image"])
        self.pose_detector = PoseDetector()

        # Audio players
        self.tts = TTS("res/strings.json", rate=200)
        self.stt = STT(
            start_filename="res/start_stt.wav", end_filename="res/end_stt.wav"
        )

        self.crickets_player = AmbientSoundPlayer("res/crickets.mp3")
        self.white_noise_player = AmbientSoundPlayer("res/white_noise.mp3")
        self.white_noise_player.set_volume(0.05)

        # LLM
        self.llm = LLM(self.graph, model["context"])

        self.running = False
        self.last_announced: Optional[str] = None

    def main_loop(self) -> None:
        min_corner, max_corner = self.graph.bounds

        cap = self.__get_capture()
        ok, frame = cap.read()
        if not ok:
            print("No camera image returned.")
            return

        self.__init_shortcuts()

        self.stt.calibrate()
        self.tts.start()

        self.tts.welcome()
        self.tts.instructions()
        if self.description is not None:
            self.tts.say(f"Map description:\n {self.description}")

        self.running = True
        while self.running and cap.isOpened():
            cv2.imshow("CamIO", frame)
            cv2.waitKey(1)  # Necessary for the window to show

            ret, frame = cap.read()
            if not ret:
                print("No camera image returned.")
                break

            pyglet.clock.tick()
            pyglet.app.platform_event_loop.dispatch_posted_events()

            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            ok, rotation = self.model_detector.detect(frame_gray)

            if not ok or rotation is None:
                self.white_noise_player.pause_sound()
                self.crickets_player.play_sound()
                continue
            self.crickets_player.pause_sound()

            gesture_position, gesture_status, frame = self.pose_detector.detect(
                frame, rotation
            )
            if gesture_position is None:
                self.white_noise_player.pause_sound()
                continue
            self.white_noise_player.play_sound()

            if gesture_status != "pointing":
                continue

            x = int(gesture_position[0])
            y = int(gesture_position[1])

            if (
                min_corner[0] <= x < max_corner[0]
                and min_corner[1] <= y < max_corner[1]
            ):
                self.__process_position(Coords(x, y))

        cap.release()
        self.__reset()

        self.tts.goodbye()
        time.sleep(1)
        self.tts.stop()

    def stop(self) -> None:
        self.running = False

    def save_chat(self, filename: str) -> None:
        self.llm.save_chat(filename)

    def __init_shortcuts(self) -> None:
        keyboard.add_hotkey("space", self.__on_spacebar_pressed)
        keyboard.add_hotkey("enter", self.stop_interaction)
        keyboard.add_hotkey("esc", self.stop)
        keyboard.on_press_key("cmd", self.__on_cmd_pressed)

    def __get_capture(self) -> cv2.VideoCapture:
        cam_port = 1  # select_cam_port()

        cap = cv2.VideoCapture(cam_port)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FOCUS, 0)

        return cap

    def __reset(self) -> None:
        keyboard.unhook_all()
        cv2.destroyAllWindows()

        self.stop_interaction()

        self.finger_buffer.clear()
        self.edge_buffer.clear()

        self.white_noise_player.pause_sound()
        self.crickets_player.pause_sound()

        self.last_announced = None

    def is_busy(self) -> bool:
        return (
            self.tts.is_speaking()
            or self.stt.is_processing()
            or self.llm.is_waiting_for_response()
        )

    def stop_interaction(self) -> None:
        self.tts.stop_speaking()
        self.stt.stop_processing()

    def __on_cmd_pressed(self, _: Any = None) -> None:
        threading = th.Thread(target=self.say_map_description)
        threading.start()

    def say_map_description(self) -> None:
        self.stop_interaction()
        if self.description is not None:
            self.tts.say(self.description)
        else:
            self.tts.no_description()

    def __on_spacebar_pressed(self) -> None:
        if self.stt.is_processing():
            self.stt.on_question_ended()
        else:
            threading = th.Thread(target=self.__handle_user_input)
            threading.start()

    def __handle_user_input(self) -> None:
        self.tts.stop_speaking()

        print("Listening...")
        question = self.stt.process_input()

        if question is None:
            print("No question detected.")
            return
        print(f"Question: {question}")

        position: Optional[Coords] = None
        if self.finger_buffer.time_from_last_update < 1:
            position = self.finger_buffer.average(start=Coords(0, 0))

        answer = self.llm.ask(question, position)
        if not self.stt.processing_input:
            if answer is None:
                print("No answer received.")
                self.tts.error()
            else:
                print(f"Answer: {answer}")
                self.tts.say(answer)

    def __process_position(self, pos: Coords) -> None:
        self.finger_buffer.add(pos)
        avg_pos = self.finger_buffer.average(start=Coords(0, 0))
        # print(f"Gesture detected at {avg_pos}")

        to_announce: Optional[str] = None

        nearest_node, distance = self.graph.get_nearest_node(avg_pos)
        to_announce = nearest_node.description

        if distance > CamIO.NODE_DISTANCE_THRESHOLD:
            edge, _ = self.graph.get_nearest_edge(pos)
            self.edge_buffer.add(edge)
            nearest_edge = self.edge_buffer.mode()

            if nearest_edge.distance_from(pos) <= CamIO.EDGE_DISTANCE_THRESHOLD:
                to_announce = nearest_edge.street
            else:
                to_announce = None

        if (
            to_announce is not None
            and to_announce != self.last_announced
            and not self.is_busy()
        ):
            self.last_announced = to_announce
            self.tts.say(to_announce)


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

    camio = CamIO(model)

    try:
        camio.main_loop()
    except KeyboardInterrupt:
        camio.stop()

    camio.save_chat(args.out)
    print(f"Chat saved to {args.out}")
