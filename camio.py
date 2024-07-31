import time

import cv2
import keyboard
import pyglet.media

from src.audio import AmbientSoundPlayer, CamIOPlayer
from src.frame_processing import PoseDetector, SIFTModelDetector
from src.graph import Coords, Graph
from src.llm import LLM
from src.utils import *


class CamIO:
    def __init__(self, model: Dict[str, Any]) -> None:
        self.model = model

        # Model graph
        self.graph = Graph(model["graph"])
        self.buffer = Buffer(5)

        # Frame processing
        self.model_detector = SIFTModelDetector(model["template_image"])
        self.pose_detector = PoseDetector()

        # Audio players
        self.camio_player = CamIOPlayer(model)
        self.crickets_player = AmbientSoundPlayer(model["crickets"])
        self.heartbeat_player = AmbientSoundPlayer(model["heartbeat"])
        self.heartbeat_player.set_volume(0.05)

        # LLM
        self.llm = LLM()

        self.running = False

    def main_loop(self) -> None:
        min_corner, max_corner = self.graph.bounds

        self.camio_player.play_welcome()
        self.camio_player.play_description()

        cam_port = select_cam_port()
        cap = cv2.VideoCapture(cam_port)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FOCUS, 0)
        ok, frame = cap.read()
        if not ok:
            print("No camera image returned.")
            return

        keyboard.add_hotkey("space", self.handle_user_input)

        timer = time.time() - 1

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
                print("Gesture detected at x: " + str(x) + " y: " + str(y))
                nearest_edge = self.graph.get_nearest_edge(Coords(x, y))
                self.buffer.add(nearest_edge)

        cap.release()
        cv2.destroyAllWindows()
        self.heartbeat_player.pause_sound()
        self.crickets_player.pause_sound()
        self.camio_player.play_goodbye()
        time.sleep(1)

    def stop(self) -> None:
        self.running = False

    def save_chat(self, filename: str) -> None:
        self.llm.save_chat(filename)

    def handle_user_input(self) -> None:
        question = input("Enter a question: ").strip()
        if question == "reset":
            self.llm.reset()
            print("LLM history reset")
            return

        print(f"Question: {question}")

        asnwer = self.llm.ask(question, self.buffer.mode())
        print(f"Answer: {asnwer}")


if __name__ == "__main__":
    import argparse

    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="CamIO, with LLM integration")
    parser.add_argument(
        "--model",
        help="Path to model json file.",
        default="models/UkraineMap/UkraineMap.json",
    )
    parser.add_argument(
        "--out",
        help="Path to chat save file.",
        default="last_chat.txt",
    )
    args = parser.parse_args()
    model = load_map_parameters(args.model)

    camio = CamIO(model)

    try:
        camio.main_loop()
    except KeyboardInterrupt:
        camio.stop()

    camio.save_chat(args.out)
    print(f"Chat saved to {args.out}")
