import os
import sys
import time
from typing import Any, Dict, Optional

import cv2
import keyboard
import pyglet.media
import speech_recognition as sr

from src.audio import STT, TTS, AmbientSoundPlayer
from src.frame_processing import PoseDetector, SIFTModelDetector
from src.graph import Coords, Edge, Graph
from src.llm import LLM
from src.utils import *


class CamIO:
    def __init__(self, model: Dict[str, Any]) -> None:

        # Model graph
        self.graph = Graph(model["graph"])
        self.finger_buffer = Buffer(5)

        # Frame processing
        self.model_detector = SIFTModelDetector(model["template_image"])
        self.pose_detector = PoseDetector()

        # Audio players
        self.tts = TTS(model, rate=200)
        self.stt = STT()

        self.crickets_player = AmbientSoundPlayer(model["crickets"])
        self.heartbeat_player = AmbientSoundPlayer(model["heartbeat"])
        self.heartbeat_player.set_volume(0.05)

        # LLM
        self.llm = LLM(self.graph)

        self.running = False

    def main_loop(self) -> None:
        min_corner, max_corner = self.graph.bounds

        cap = self.get_capture()
        ok, frame = cap.read()
        if not ok:
            print("No camera image returned.")
            return

        self.stt.calibrate()
        self.tts.start()

        self.init_shortcuts()

        self.tts.welcome()
        self.tts.description()

        self.running = True
        last_edge: Optional[Edge] = None
        edge_buffer = Buffer(5)
        while self.running and cap.isOpened():

            cv2.imshow("CamIO", frame)
            cv2.waitKey(1)  # Necessary for the window to show

            ret, frame = cap.read()
            if not ret:
                print("No camera image returned.")
                break
            frame = frame.copy()

            pyglet.clock.tick()
            pyglet.app.platform_event_loop.dispatch_posted_events()

            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            ok, rotation = self.model_detector.detect(frame_gray)

            if not ok or rotation is None:
                self.heartbeat_player.pause_sound()
                self.crickets_player.play_sound()
                continue
            self.crickets_player.pause_sound()

            gesture_position, gesture_status, frame = self.pose_detector.detect(
                frame, rotation
            )
            if gesture_position is None:
                self.heartbeat_player.pause_sound()
                continue
            self.heartbeat_player.play_sound()

            if gesture_status != "pointing":
                continue

            x = int(gesture_position[0])
            y = int(gesture_position[1])

            if (
                min_corner[0] <= x < max_corner[0]
                and min_corner[1] <= y < max_corner[1]
            ):
                self.finger_buffer.add(Coords(x, y))
                pos = self.finger_buffer.average(Coords(0, 0))
                # print(f"Gesture detected at {self.buffer.average(start=Coords(0, 0))}")

                edge = self.graph.get_nearest_edge(pos)
                edge_buffer.add(edge)
                edge = edge_buffer.mode()

                if (
                    edge != last_edge
                    and not self.tts.is_speaking()
                    and edge.distance_from(pos) < 40
                ):
                    last_edge = edge
                    self.tts.say(edge.street)

        keyboard.remove_all_hotkeys()
        cap.release()
        cv2.destroyAllWindows()
        self.finger_buffer.clear()

        self.tts.stop_speaking()
        self.tts.goodbye()
        time.sleep(1)

        self.heartbeat_player.pause_sound()
        self.crickets_player.pause_sound()
        self.tts.stop()

    def stop(self) -> None:
        self.running = False

    def save_chat(self, filename: str) -> None:
        self.llm.save_chat(filename)

    def init_shortcuts(self) -> None:
        keyboard.add_hotkey("space", self.handle_user_input)
        keyboard.add_hotkey("enter", self.tts.stop_speaking)
        keyboard.add_hotkey("esc", self.stop)

    def get_capture(self) -> cv2.VideoCapture:
        cam_port = 1  # select_cam_port()

        cap = cv2.VideoCapture(cam_port)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FOCUS, 0)

        return cap

    def handle_user_input(self) -> None:
        if self.stt.is_listening():
            return
        self.tts.stop_speaking()

        question = self.stt.get_input()

        if question is None:
            print("No question detected.")
            return
        print(f"Question: {question}")

        position: Optional[Coords] = None
        if self.finger_buffer.time_from_last_update < 1:
            position = self.finger_buffer.average(start=Coords(0, 0))

        answer = self.llm.ask(question, position)
        if not self.stt.listening:
            if answer is None:
                print("No answer received.")
                self.tts.error()
            else:
                print(f"Answer: {answer}")
                self.tts.say(answer)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    args = camio_parser.parse_args()

    out_dir = os.path.dirname(args.out)
    if not os.path.exists(out_dir):
        print(f"Directory {out_dir} does not exist.")
        sys.exit(0)

    model = load_map_parameters(args.model)

    camio = CamIO(model)

    try:
        camio.main_loop()
    except KeyboardInterrupt:
        camio.stop()

    camio.save_chat(args.out)
    print(f"Chat saved to {args.out}")
