import os

from dotenv import load_dotenv

load_dotenv()
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"

import sys
import threading as th
import time
from functools import partial
from typing import Any, Dict, List, Optional

import cv2

from src.audio import STT, Announcement, AudioManager, CamIOTTS
from src.config import config, get_args
from src.frame_processing import (GestureRecognizer, GestureResult, HandStatus,
                                  ModelDetector, VideoCapture, WindowManager)
from src.graph import Graph, WayPoint
from src.input import InputListener, KeyboardManager, QuestionHandler
from src.llm import LLM
from src.navigation import NavigationAction, NavigationManager
from src.position import PositionHandler
from src.utils import Buffer, Coords, load_map_parameters


class CamIO:

    def __init__(self, model: Dict[str, Any]) -> None:
        self.description = model["context"].get("description", None)

        # Model graph
        self.graph = Graph(model["graph"])
        self.graph.on_new_route = self.enable_navigation_mode
        self.position_handler = PositionHandler()

        # Frame processing
        self.window_manager = WindowManager()
        self.model_detector = ModelDetector()
        self.gesture_recognizer = GestureRecognizer()
        self.hand_status_buffer = Buffer[HandStatus](max_size=5, max_life=5)

        # Audio
        self.tts = CamIOTTS(f"res/strings_{config.lang}.json", rate=config.tts_rate)
        self.stt = STT()
        self.audio_manager = AudioManager("res/sounds.json")

        # User iteraction
        self.navigation_manager = NavigationManager()
        self.navigation_manager.on_action = self.__on_navigation_action
        self.llm = LLM(
            f"res/prompt_{config.lang}.yaml",
            model["context"],
            temperature=config.temperature,
        )
        self.question_handler: Optional[QuestionHandler] = None

        # Input handling
        input_listeners = {
            InputListener.STOP_INTERACTION: partial(self.stop_interaction),
            InputListener.SAY_MAP_DESCRIPTION: partial(self.say_map_description),
            InputListener.TOGGLE_TTS: partial(self.tts.toggle_pause),
            InputListener.STOP: partial(self.stop),
            InputListener.QUESTION: partial(self.__on_spacebar_pressed),
            InputListener.STOP_NAVIGATION: partial(self.navigation_manager.clear),
        }

        if not config.llm_enabled:
            input_listeners[InputListener.QUESTION] = partial(lambda: None)
            for poi in self.graph.pois:
                poi.enable()

        self.keyboard = KeyboardManager(input_listeners)

        self.running = False

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

        self.keyboard.init_shortcuts()

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
                self.audio_manager.hand_feedback(HandStatus.NOT_FOUND)
                continue

            hand, frame = self.gesture_recognizer.detect(frame, homography)
            hand_status = self.__process_hand_status(hand)

            if hand.new_hand or hand_status != HandStatus.POINTING:
                self.position_handler.clear()

            if hand.position is None:
                continue

            self.position_handler.process_position(hand.position)
            position = self.position_handler.get_position_info()
            if hand_status != HandStatus.POINTING or self.is_handling_user_input():
                continue

            if self.navigation_manager.running:
                self.navigation_manager.update(
                    position,
                    ignore_not_moving=self.is_handling_user_input()
                    or self.tts.is_speaking(),
                )

            else:
                self.tts.announce_position(position)
                self.audio_manager.position_feedback(position)

        self.audio_manager.stop()
        video_capture.stop()

        self.keyboard.disable_shortcuts()
        self.window_manager.close()

        self.stop_interaction()
        self.position_handler.clear()
        self.hand_status_buffer.clear()

        self.tts.goodbye()
        time.sleep(2)
        self.tts.stop()

    def is_handling_user_input(self) -> bool:
        return self.question_handler is not None and self.question_handler.running

    def stop(self) -> None:
        self.running = False

    def save_chat(self, filename: str) -> None:
        self.llm.save_chat(filename)

    def stop_interaction(self) -> None:
        self.tts.stop_speaking()

        if self.question_handler is not None:
            self.question_handler.stop()

        self.stt.on_question_ended()

    def say_map_description(self, _: Any = None) -> None:
        self.stop_interaction()

        if self.description is not None:
            self.tts.map_description(self.description)
        else:
            self.tts.no_map_description()

    def enable_navigation_mode(
        self, start: Coords, step_by_step: bool, waypoints: List[WayPoint]
    ) -> None:
        self.window_manager.clear_waypoints()

        self.window_manager.add_waypoint(start)
        for waypoint in waypoints:
            self.window_manager.add_waypoint(waypoint.coords)

        if step_by_step:
            self.navigation_manager.navigate_step_by_step(
                waypoints, self.position_handler.last_info
            )
        else:
            self.navigation_manager.navigate(waypoints[0])

    def __process_hand_status(self, hand: GestureResult) -> HandStatus:
        hand_status = hand.status

        if (
            hand.status == HandStatus.POINTING
            and hand.position is not None
            and not self.position_handler.is_valid_position(
                hand.position * config.feets_per_pixel
            )
        ):
            hand_status = HandStatus.NOT_FOUND

        self.hand_status_buffer.add(hand_status)
        hand_status = self.hand_status_buffer.mode() or HandStatus.NOT_FOUND

        if hand_status == HandStatus.MORE_THAN_ONE_HAND:
            self.tts.more_than_one_hand()

        self.audio_manager.hand_feedback(hand_status)

        return hand_status

    def __on_spacebar_pressed(self) -> None:
        if self.stt.is_recording:
            self.stt.on_question_ended()

        elif self.llm.is_waiting_for_response():
            self.tts.waiting_llm()

        elif self.hand_status_buffer.mode() == HandStatus.POINTING:
            self.stop_interaction()
            self.question_handler = QuestionHandler()
            self.question_handler.handle_question()

        else:
            self.tts.no_pointing()

    def __on_navigation_action(self, action: NavigationAction, **kwargs) -> None:
        if self.is_handling_user_input():
            return

        if action == NavigationAction.NEW_ROUTE:
            th.Thread(
                target=self.graph.guide_to_destination,
                args=(kwargs["start"], kwargs["destination"], True),
            ).start()

        elif action == NavigationAction.WAYPOINT_REACHED:
            self.audio_manager.play_waypoint_reached()

        elif action == NavigationAction.WRONG_DIRECTION:
            self.tts.wrong_direction()

        elif action == NavigationAction.DESTINATION_REACHED:
            self.tts.destination_reached()
            self.tts.pause(2.0)
            self.audio_manager.play_destination_reached()
            self.window_manager.clear_waypoints()

        elif action == NavigationAction.ANNOUNCE_DIRECTION:
            instructions: str = kwargs["instructions"]
            self.tts.stop_and_say(
                instructions,
                category=Announcement.Category.GRAPH,
                priority=Announcement.Priority.MEDIUM,
            )


if __name__ == "__main__":
    args = get_args()
    config.load_args(args)

    out_dir = os.path.dirname(args.out)
    if not os.path.exists(out_dir):
        print(f"\nDirectory {out_dir} does not exist.")
        sys.exit(0)

    model = load_map_parameters(args.model)
    if model is None:
        print(f"\nModel file {args.model} not found.")
        sys.exit(0)

    config.load_model(model)
    print(f"\nLoaded map: {model.get('name', 'Unknown')}\n")

    camio: Optional[CamIO] = None
    try:
        camio = CamIO(model)
        camio.main_loop()

    except KeyboardInterrupt:
        pass

    except Exception as e:
        print(f"\nAn error occurred:\n{e}")

    finally:
        if camio is not None:
            camio.stop()
            camio.save_chat(args.out)
            print(f"\nChat saved to {args.out}")
