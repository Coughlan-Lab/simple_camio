import json
import os
import time

from src.graph import Graph, PositionInfo

from .tts import TTS, Announcement


class CamIOTTS(TTS):
    NODE_ANNOUNCEMENT_DELAY = 1.0

    ANNOUNCEMENT_INTERVAL = 0.25
    ERROR_INTERVAL = 5

    def __init__(self, res_file: str, rate: int) -> None:
        super().__init__(rate)

        if not os.path.exists(res_file):
            raise FileNotFoundError("Resource file not found.")

        with open(res_file, "r") as f:
            self.res = json.load(f)

        self.last_pos_info = PositionInfo.none_info()

    def llm_response(self, response: str) -> bool:
        return self.stop_and_say(
            response,
            category=Announcement.Category.LLM,
            priority=Announcement.Priority.HIGH,
        )

    def welcome(self) -> bool:
        return self.say(
            self.res["welcome"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.MEDIUM,
        )

    def instructions(self) -> bool:
        return self.say(
            self.res["instructions"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.MEDIUM,
        )

    def goodbye(self) -> bool:
        return self.stop_and_say(
            self.res["goodbye"],
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.HIGH,
        )

    def start_waiting_llm(self) -> None:
        def msg_fn() -> bool:
            return self.stop_and_say(
                self.res["waiting_llm"],
                category=Announcement.Category.SYSTEM,
                priority=Announcement.Priority.MEDIUM,
            )

        return self._start_one_msg_loop(msg_fn)

    def stop_waiting_llm(self) -> None:
        return self._stop_one_msg_loop()

    def llm_error(self) -> bool:
        return self.stop_and_say(
            self.res["llm_error"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.HIGH,
        )

    def question_error(self) -> bool:
        return self.stop_and_say(
            self.res["no_question_error"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.HIGH,
        )

    def no_map_description(self) -> bool:
        return self.stop_and_say(
            self.res["no_map_description"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.HIGH,
        )

    def map_description(self, description: str) -> bool:
        return self.say(
            f"Map description:\n{description}",
            category=Announcement.Category.SYSTEM,
            priority=Announcement.Priority.HIGH,
        )

    def no_pointing(self) -> bool:
        return self.stop_and_say(
            self.res["no_pointing"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.HIGH,
        )

    def more_than_one_hand(self) -> bool:
        if (
            time.time() - self._timestamps[Announcement.Category.ERROR]
            < CamIOTTS.ERROR_INTERVAL
        ):
            return False

        return self.stop_and_say(
            self.res["more_than_one_hand"],
            category=Announcement.Category.ERROR,
            priority=Announcement.Priority.MEDIUM,
        )

    def announce_position(self, info: PositionInfo) -> bool:
        if (
            time.time() - self._timestamps[Announcement.Category.GRAPH]
            < CamIOTTS.ANNOUNCEMENT_INTERVAL
        ):
            return False

        if len(info.description) == 0 or (
            self.last_pos_info.is_still_valid()
            and info.description == self.last_pos_info.description
        ):
            return False

        if info.is_node():
            if self.last_pos_info.graph_element == info.graph_element:
                if (
                    info.timestamp - self.last_pos_info.timestamp
                    > CamIOTTS.NODE_ANNOUNCEMENT_DELAY
                ):
                    if self.__say(info):
                        self.last_pos_info = info
                        return True
            else:
                self.last_pos_info = info
                self.last_pos_info.invalidate()

        else:
            if self.__stop_and_say(info):
                self.last_pos_info = info
                return True

        return False

    def __say(self, info: PositionInfo) -> bool:
        return self.say(
            info.description,
            category=Announcement.Category.GRAPH,
            priority=Announcement.Priority.LOW,
        )

    def __stop_and_say(self, info: PositionInfo) -> bool:
        return self.stop_and_say(
            info.description,
            category=Announcement.Category.GRAPH,
            priority=Announcement.Priority.LOW,
        )
