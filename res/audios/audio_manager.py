import os


class AudioManager:
    AUDIOS_DIR = os.path.dirname(__file__)

    def __init__(self) -> None:
        self.crickets = os.path.join(AudioManager.AUDIOS_DIR, "crickets.mp3")
        self.heartbeat = os.path.join(AudioManager.AUDIOS_DIR, "white_noise.mp3")
        self.welcome = os.path.join(AudioManager.AUDIOS_DIR, "welcome.mp3")
        self.goodbye = os.path.join(AudioManager.AUDIOS_DIR, "goodbye.mp3")
        self.blip = os.path.join(AudioManager.AUDIOS_DIR, "quick_blip.wav")


singleton: AudioManager = AudioManager()
