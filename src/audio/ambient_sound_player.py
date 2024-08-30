import pyglet

from src.frame_processing import HandStatus


class AmbientSoundPlayer:
    def __init__(self, background_path: str, pointing_path: str) -> None:
        self.background = pyglet.media.load(background_path, streaming=False)
        self.pointing = pyglet.media.load(pointing_path, streaming=False)

        self.background_player = pyglet.media.Player()
        self.background_player.loop = True
        self.background_player.queue(self.background)

        self.background_player.play()
        self.last_hand_status: HandStatus = HandStatus.NOT_FOUND

    def update(self, hand_status: HandStatus) -> None:
        if hand_status == self.last_hand_status:
            return

        if hand_status == HandStatus.POINTING:
            self.stop_background()
            self.pointing.play()
        else:
            self.play_background()

        self.last_hand_status = hand_status

    def play_background(self) -> None:
        if not self.background_player.playing:
            self.background_player.play()

    def stop_background(self) -> None:
        if self.background_player.playing:
            self.background_player.pause()
