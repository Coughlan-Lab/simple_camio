import pyglet

from src.frame_processing import HandStatus


class AmbientSoundPlayer:
    def __init__(self, white_noise_filename: str, crickets_filename: str) -> None:
        self.white_noise = pyglet.media.load(white_noise_filename, streaming=False)
        self.crickets = pyglet.media.load(crickets_filename, streaming=False)

        self.player = pyglet.media.Player()
        self.player.loop = True
        self.player.queue(self.crickets)

        self.playing_crickets = True
        self.player.play()

    def update(self, gesture: HandStatus) -> None:
        if gesture == HandStatus.POINTING:
            self.play_white_noise()
        else:
            self.play_crickets()

    def play_white_noise(self) -> None:
        if self.playing_crickets:
            self.player.queue(self.white_noise)
            self.player.next_source()
            self.playing_crickets = False

    def play_crickets(self) -> None:
        if not self.playing_crickets:
            self.player.queue(self.crickets)
            self.player.next_source()
            self.playing_crickets = True

    def stop(self) -> None:
        self.player.pause()
