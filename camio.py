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

from src.config import config, get_args
from src.frame_processing import GestureRecognizer, GestureResult, Hand, MapDetector
from src.graph import Graph, WayPoint
from src.llm import LLM
from src.modules_repository import ModulesRepository
from src.navigation import NavigationAction, NavigationController
from src.position import PositionHandler
from src.command_controller import CommandController
from src.utils import Coords, load_map_parameters
from src.view import (
    UserAction,
    KeyboardManager,
    VideoCapture,
    ViewManager,
    ignore_unpress,
)
from src.view.audio import STT, Announcement, AudioManager, CamIOTTS

repository = ModulesRepository()


class CamIOController:

    def __init__(self, model: Dict[str, Any]) -> None:
        self.description = model["context"].get("description", None)

        self.question_handler: Optional[CommandController] = None
        self.running = False

        # Model
        self.graph = Graph(model["graph"])
        self.graph.on_new_route = self.enable_navigation_mode
        self.position_handler = PositionHandler()

        self.model_detector = MapDetector()
        self.gesture_recognizer = GestureRecognizer()
        self.hand_status = GestureResult.Status.NOT_FOUND

        # View
        self.view = ViewManager(self.graph.pois)
        self.tts = CamIOTTS(f"res/strings_{config.lang}.json", rate=config.tts_rate)
        self.stt = STT()
        self.audio_manager = AudioManager("res/sounds.json")

        self.navigation_manager = NavigationController(repository)
        self.navigation_manager.on_action = self.__on_navigation_action
        self.llm = LLM(
            f"res/prompt_{config.lang}.yaml",
            model["context"],
            temperature=config.temperature,
        )

        input_listeners = {
            UserAction.STOP_INTERACTION: ignore_unpress(partial(self.stop_interaction)),
            UserAction.SAY_MAP_DESCRIPTION: ignore_unpress(
                partial(self.say_map_description)
            ),
            UserAction.TOGGLE_TTS: ignore_unpress(partial(self.tts.toggle_pause)),
            UserAction.STOP: ignore_unpress(partial(self.stop)),
            UserAction.QUESTION: partial(self.__on_spacebar_pressed),
            UserAction.STOP_NAVIGATION: ignore_unpress(
                partial(self.navigation_manager.clear)
            ),
        }

        if not config.llm_enabled:
            input_listeners[UserAction.QUESTION] = partial(lambda: None)

        self.keyboard = KeyboardManager("res/shortcuts.json", input_listeners)

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
        last_hand_side: Optional[Hand.Side] = None

        self.running = True
        while self.running and video_capture.is_opened():
            self.view.update(frame, self.position_handler.last_info)

            frame = video_capture.read()
            if frame is None:
                print("No camera image returned.")
                break

            homography, frame = self.model_detector.detect(frame)

            if homography is None:
                self.audio_manager.hand_feedback(GestureResult.Status.NOT_FOUND)
                continue

            hand, frame = self.gesture_recognizer.detect(frame, homography)
            self.hand_status = hand.status

            self.audio_manager.hand_feedback(hand.status)

            if hand.status == GestureResult.Status.MORE_THAN_ONE_HAND:
                self.tts.more_than_one_hand()

            if hand.position is None or hand.status != GestureResult.Status.POINTING:
                self.position_handler.clear()
                continue

            if hand.side != last_hand_side:
                last_hand_side = hand.side
                self.position_handler.clear()
                if hand.side is not None:
                    self.tts.hand_side(str(hand.side))

            self.position_handler.process_position(hand.position)
            position = self.position_handler.get_position_info()

            if self.is_handling_user_input():
                continue

            if self.navigation_manager.is_running():
                self.navigation_manager.update(
                    position,
                    ignore_not_moving=self.is_handling_user_input()
                    or self.tts.is_speaking(),
                )
            else:
                self.tts.position(position)
                self.audio_manager.position_feedback(position)

        self.audio_manager.stop()
        video_capture.stop()

        self.keyboard.disable_shortcuts()
        self.view.close()

        self.stop_interaction()
        self.position_handler.clear()

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

    def say_map_description(self) -> None:
        self.stop_interaction()

        if self.description is not None:
            self.tts.map_description(self.description)
        else:
            self.tts.no_map_description()

    def enable_navigation_mode(
        self, start: Coords, step_by_step: bool, waypoints: List[WayPoint]
    ) -> None:
        self.view.clear_waypoints()

        self.view.add_waypoint(start)
        for waypoint in waypoints:
            self.view.add_waypoint(waypoint.coords)

        if step_by_step:
            self.navigation_manager.navigate_step_by_step(
                waypoints, self.position_handler.last_info
            )
        else:
            self.navigation_manager.navigate(waypoints[0])

    def __on_spacebar_pressed(self, pressed: bool) -> None:
        if not pressed:
            if self.stt.is_recording:
                self.stt.on_question_ended()

        elif self.llm.is_waiting_for_response():
            self.tts.waiting_llm()

        elif self.hand_status == GestureResult.Status.POINTING:
            self.stop_interaction()
            self.question_handler = CommandController(repository)
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
            self.tts.add_pause(2.0)
            self.audio_manager.play_destination_reached()
            self.view.clear_waypoints()

        elif action == NavigationAction.ANNOUNCE_DIRECTION:
            instructions: str = kwargs["instructions"]
            self.tts.stop_and_say(
                instructions,
                category=Announcement.Category.NAVIGATION,
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

    try:
        camio = CamIOController(model)
        camio.main_loop()

    except KeyboardInterrupt:
        pass

    except Exception as e:
        print(f"\nAn error occurred:\n{e}")

    else:
        camio.stop()
        camio.save_chat(args.out)
        print(f"\nChat saved to {args.out}")
