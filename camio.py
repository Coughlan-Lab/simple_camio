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
from src.graph import Coords, Graph
from src.llm import LLM
from src.utils import *


class CamIO:
    def __init__(self, model: Dict[str, Any]) -> None:

        # Model graph
        self.graph = Graph(model["graph"])
        self.buffer = Buffer(5)

        # Frame processing
        self.model_detector = SIFTModelDetector(model["template_image"])
        self.pose_detector = PoseDetector()

        # Audio players
        self.tts = TTS(model, rate=200)
        self.crickets_player = AmbientSoundPlayer(model["crickets"])
        self.heartbeat_player = AmbientSoundPlayer(model["heartbeat"])
        self.heartbeat_player.set_volume(0.05)

        self.stt = STT()

        # LLM
        self.llm = LLM(self.graph)

        self.running = False
        self.listening = False

    def main_loop(self) -> None:
        min_corner, max_corner = self.graph.bounds
        self.buffer.clear()

        cam_port = 1  # select_cam_port()
        cap = cv2.VideoCapture(cam_port)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FOCUS, 0)
        ok, frame = cap.read()
        if not ok:
            print("No camera image returned.")
            return

        self.stt.calibrate()
        self.tts.start()

        keyboard.add_hotkey("space", self.handle_user_input)
        keyboard.add_hotkey("enter", self.stop_interaction)

        timer = time.time() - 1

        self.tts.welcome()
        self.tts.description()

        self.running = True
        while self.running and cap.isOpened():

            cv2.imshow("CamIO", cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

            ret, frame = cap.read()
            if not ret:
                print("No camera image returned.")
                break
            frame = frame.copy()

            waitkey = cv2.waitKey(1)
            if waitkey == 27 or waitkey == ord("q"):
                break

            # prev_time = timer
            # timer = time.time()
            # elapsed_time = timer - prev_time
            # print("current fps: " + str(1/elapsed_time))

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
                self.buffer.add(Coords(x, y))
                # print(f"Gesture detected at {self.buffer.average(start=Coords(0, 0))}")
                # print(f"Nearest edge: {self.graph.get_nearest_edge(self.buffer.average(start=Coords(0, 0)))}")

        cap.release()
        cv2.destroyAllWindows()

        self.stop_interaction()
        self.tts.goodbye()
        time.sleep(1)

        self.heartbeat_player.pause_sound()
        self.crickets_player.pause_sound()
        self.tts.stop()

    def stop(self) -> None:
        self.running = False
        self.listening = False

    def stop_interaction(self) -> None:
        self.tts.stop_speaking()
        self.listening = False

    def save_chat(self, filename: str) -> None:
        self.llm.save_chat(filename)

    def handle_user_input(self) -> None:
        if self.listening:
            return
        self.stop_interaction()

        self.listening = True
        question = self.stt.get_input()
        self.listening = False

        if question is None:
            print("No question detected.")
            return
        print(f"Question: {question}")

        position: Optional[Coords] = None
        if self.buffer.time_from_last_update < 1:
            position = self.buffer.average(start=Coords(0, 0))

        answer = self.llm.ask(question, position)
        if not self.listening and answer is not None:
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
