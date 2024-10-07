import os

from dotenv import load_dotenv

load_dotenv()
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"

import sys
import threading as th
import time
from typing import Any, Dict, List, Optional, Callable

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
    ignore_action_end,
)
from src.view.audio import STT, Announcement, AudioManager, CamIOTTS

repository = ModulesRepository()


class CamIOController:

    def __init__(self, model: Dict[str, Any]) -> None:
        self.description = model["context"].get("description", None)

        # Model
        self.graph = Graph(model["graph"])
        self.graph.on_new_route = self.enable_navigation_mode
        self.position_handler = PositionHandler()
        self.llm = LLM(
            f"res/prompt_{config.lang}.yaml",
            model["context"],
            temperature=config.temperature,
        )

        self.model_detector = MapDetector()
        self.gesture_recognizer = GestureRecognizer()
        self.hand_status = GestureResult.Status.NOT_FOUND

        # View
        self.view = ViewManager(self.graph.pois)
        self.tts = CamIOTTS(f"res/strings_{config.lang}.json", rate=config.tts_rate)
        self.stt = STT()
        self.audio_manager = AudioManager("res/sounds.json")

        # User interaction
        self.navigation_controller = NavigationController(
            repository, self.__on_navigation_action
        )
        self.__action_listeners = self.__get_action_listeners()
        self.command_controller = CommandController(
            repository, "res/voice_commands.json", self.__on_user_action
        )
        self.keyboard = KeyboardManager("res/shortcuts.json", self.__on_user_action)

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

            if self.navigation_controller.is_running():
                self.navigation_controller.update(
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
        return self.command_controller.is_handling_command()

    def stop(self) -> None:
        self.running = False

    def save_chat(self, filename: str) -> None:
        self.llm.save_chat(filename)

    def stop_interaction(self) -> None:
        self.tts.stop_speaking()

        if self.is_handling_user_input():
            self.command_controller.stop_handling_command()

        if self.stt.is_recording():
            self.stt.on_question_ended()

    def say_map_description(self) -> None:
        self.stop_interaction()

        if self.description is not None:
            self.tts.map_description(self.description)
        else:
            self.tts.no_map_description()

    def enable_navigation_mode(
        self, start: Coords, street_by_street: bool, waypoints: List[WayPoint]
    ) -> None:
        self.view.clear_waypoints()

        self.view.add_waypoint(start)
        for waypoint in waypoints:
            self.view.add_waypoint(waypoint.coords)

        if street_by_street:
            self.navigation_controller.navigate_street_by_street(
                waypoints, self.position_handler.last_info
            )
        else:
            self.navigation_controller.navigate(waypoints[0])

    def __on_command(self, ended: bool) -> None:
        if ended:
            if self.stt.is_recording():
                self.stt.on_question_ended(add_final_silence=True)

        elif self.llm.is_waiting_for_response() or self.stt.is_processing_audio():
            self.tts.waiting()

        else:
            self.stop_interaction()
            self.command_controller.handle_command()

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

    def __get_action_listeners(self) -> Dict[UserAction, Callable[[bool], None]]:
        listeners = {
            UserAction.STOP_INTERACTION: ignore_action_end(self.stop_interaction),
            UserAction.SAY_MAP_DESCRIPTION: ignore_action_end(self.say_map_description),
            UserAction.TOGGLE_TTS: ignore_action_end(self.tts.toggle_pause),
            UserAction.STOP: ignore_action_end(self.stop),
            UserAction.COMMAND: self.__on_command,
            UserAction.STOP_NAVIGATION: ignore_action_end(
                self.navigation_controller.clear
            ),
            UserAction.DISABLE_POSITION_TTS: ignore_action_end(
                self.__disable_position_tts
            ),
            UserAction.ENABLE_POSITION_TTS: ignore_action_end(
                self.__enable_position_tts
            ),
        }

        if not config.llm_enabled:
            del listeners[UserAction.COMMAND]

        return listeners

    def __on_user_action(self, action: UserAction, started: bool = True) -> None:
        if action in self.__action_listeners:
            self.__action_listeners[action](not started)

    def __disable_position_tts(self) -> None:
        self.tts.disable_category(Announcement.Category.GRAPH)
        self.tts.position_paused()

    def __enable_position_tts(self) -> None:
        self.tts.enable_category(Announcement.Category.GRAPH)
        self.tts.position_resumed()


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
