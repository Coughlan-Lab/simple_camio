import pyglet

from src.frame_processing import HandStatus


class AmbientSoundPlayer:
    def __init__(self, sound_path: str) -> None:
        self.sound = pyglet.media.load(sound_path, streaming=False)

        self.player = pyglet.media.Player()
        self.player.loop = True
        self.player.queue(self.sound)

        self.player.play()

    def update(self, gesture: HandStatus) -> None:
        if gesture == HandStatus.POINTING:
            self.play()
        else:
            self.stop()

    def play(self) -> None:
        self.player.play()

    def stop(self) -> None:
        self.player.pause()
