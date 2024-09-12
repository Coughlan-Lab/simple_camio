import threading as th
from typing import Optional

from src.audio import STT, Announcement, AudioManager, CamIOTTS
from src.config import config
from src.frame_processing import GestureResult
from src.input import KeyboardManager
from src.llm import LLM
from src.modules_repository import ModulesRepository
from src.position import PositionHandler


class QuestionHandler(th.Thread):
    def __init__(self, repository: ModulesRepository) -> None:
        super().__init__()

        self.repository = repository

        self.stop_event = th.Event()
        self.announcement_id: Optional[str] = None
        self.tts.on_announcement_ended = self.on_announcement_ended

        self.waiting_tts = th.Condition()

    def handle_question(self) -> None:
        if self.running:
            return

        self.stop_event.clear()
        self.start()

    @property
    def running(self) -> bool:
        return not self.stop_event.is_set() and self.is_alive()

    def run(self) -> None:
        self.tts.stop_speaking()
        position = self.position_handler.last_info

        if config.stt_enabled:
            question = self.get_question_from_stt()
        else:
            question = self.get_question_from_keyboard()

        if self.stop_event.is_set():
            print("Stopping user input handler.")
            self.tts.stop_waiting_llm_loop()
            return

        if len(question) == 0:
            print("No question recognized.")
            self.tts.stop_waiting_llm_loop()
            self.tts.question_error()
            return

        print(f"Question: {question}")

        if self.position_handler.last_info.is_still_valid():
            position = self.position_handler.last_info

        answer = self.llm.ask(question, position) or ""
        self.tts.stop_waiting_llm_loop()

        if self.stop_event.is_set():
            print("Stopping user input handler.")
            return

        self.process_answer(answer)

    def get_question_from_stt(self) -> str:
        print("Listening...")

        self.audio_manager.play_start_recording()
        recording = self.stt.get_audio()
        self.audio_manager.play_end_recording()

        if recording is None or self.stop_event.is_set():
            return ""

        self.tts.start_waiting_llm_loop()
        return self.stt.audio_to_text(recording) or ""

    def get_question_from_keyboard(self) -> str:
        self.keyboard.pause()

        self.audio_manager.play_start_recording()
        question = input("Input: ")
        self.audio_manager.play_end_recording()

        self.keyboard.resume()
        return question

    def process_answer(self, answer: str) -> None:
        self.tts.stop_speaking()

        if len(answer) == 0:
            print("No answer received.")
            announcement = self.tts.llm_error()
        else:
            print(f"Answer: {answer}")
            announcement = self.tts.llm_response(answer)

        if announcement is not None:
            self.announcement_id = announcement.id

        self.tts.pause(2.0)
        self.wait_tts()

    def wait_tts(self) -> None:
        if self.announcement_id is None:
            return

        with self.waiting_tts:
            while not self.stop_event.is_set():
                self.waiting_tts.wait()

    def stop(self) -> None:
        if self.stop_event.is_set():
            return

        self.stop_event.set()
        self.tts.on_announcement_ended = None
        self.llm.stop()
        self.tts.stop_waiting_llm_loop()

    def on_announcement_ended(
        self, announcement: Announcement, announced: bool
    ) -> None:
        if self.announcement_id != announcement.id:
            return

        if self.hand_status == GestureResult.Status.POINTING:
            self.audio_manager.play_pointing()

        self.stop_event.set()
        with self.waiting_tts:
            self.waiting_tts.notify_all()

        self.tts.on_announcement_ended = None

    @property
    def tts(self) -> CamIOTTS:
        return self.repository[CamIOTTS]

    @property
    def stt(self) -> STT:
        return self.repository[STT]

    @property
    def hand_status(self) -> GestureResult.Status:
        return self.audio_manager.hand_status

    @property
    def position_handler(self) -> PositionHandler:
        return self.repository[PositionHandler]

    @property
    def llm(self) -> LLM:
        return self.repository[LLM]

    @property
    def audio_manager(self) -> AudioManager:
        return self.repository[AudioManager]

    @property
    def keyboard(self) -> KeyboardManager:
        return self.repository[KeyboardManager]
