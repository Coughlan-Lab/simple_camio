"""
Audio playback components for Simple CamIO.

This module handles all audio-related functionality including ambient sounds,
sound effects, and zone-based audio descriptions.
"""

import os
import pyglet.media
import logging

logger = logging.getLogger(__name__)


class AmbientSoundPlayer:
    """
    Player for looping ambient background sounds.

    This class manages a single looping audio track with volume control,
    typically used for ambient sounds like crickets or heartbeat.
    """

    def __init__(self, soundfile):
        """
        Initialize the ambient sound player.

        Args:
            soundfile (str): Path to the audio file to play
        """
        self.sound = pyglet.media.load(soundfile, streaming=False)
        self.player = pyglet.media.Player()
        self.player.queue(self.sound)
        self.player.eos_action = 'loop'
        self.player.loop = True
        logger.debug(f"Initialized ambient sound player with {soundfile}")

    def set_volume(self, volume):
        """
        Set the playback volume.

        Args:
            volume (float): Volume level between 0.0 and 1.0
        """
        if 0 <= volume <= 1:
            self.player.volume = volume
            logger.debug(f"Set volume to {volume}")

    def play_sound(self):
        """Start playing the ambient sound if not already playing."""
        if not self.player.playing:
            self.player.play()
            logger.debug("Started ambient sound playback")

    def pause_sound(self):
        """Pause the ambient sound if currently playing."""
        if self.player.playing:
            self.player.pause()
            logger.debug("Paused ambient sound playback")


class ZoneAudioPlayer:
    """
    Manages audio playback for interactive zones on the map.

    This class handles playing audio descriptions when users interact with
    different zones, including blip sounds for zone transitions and
    descriptive audio for each hotspot.
    """

    def __init__(self, model):
        """
        Initialize the zone audio player.

        Args:
            model (dict): Map model configuration containing audio file paths
        """
        self.model = model
        self.prev_zone_name = ''
        self.prev_zone_moving = -1
        self.curr_zone_moving = -1
        self.sound_files = {}
        self.hotspots = {}
        self.player = pyglet.media.Player()
        self.enable_blips = False

        # Load blip sound for zone transitions
        self.blip_sound = pyglet.media.load(self.model['blipsound'], streaming=False)

        # Load map description if available
        if "map_description" in self.model:
            self.map_description = pyglet.media.load(self.model['map_description'], streaming=False)
            self.have_played_description = False
        else:
            self.have_played_description = True

        # Load welcome and goodbye messages
        self.welcome_message = pyglet.media.load(self.model['welcome_message'], streaming=False)
        self.goodbye_message = pyglet.media.load(self.model['goodbye_message'], streaming=False)

        # Load audio files for each hotspot
        self._load_hotspot_audio()

        logger.info(f"Initialized zone audio player with {len(self.hotspots)} hotspots")

    def _load_hotspot_audio(self):
        """Load audio files for all hotspots defined in the model."""
        for hotspot in self.model['hotspots']:
            # Create unique key from color
            key = (hotspot['color'][2] +
                   hotspot['color'][1] * 256 +
                   hotspot['color'][0] * 256 * 256)

            self.hotspots[key] = hotspot

            # Load audio file if it exists
            if os.path.exists(hotspot['audioDescription']):
                self.sound_files[key] = pyglet.media.load(
                    hotspot['audioDescription'],
                    streaming=False
                )
            else:
                logger.warning(f"Audio file not found: {hotspot['audioDescription']}")

    def play_description(self):
        """Play the map description audio (only once)."""
        if not self.have_played_description:
            self.player = self.map_description.play()
            self.have_played_description = True
            logger.info("Playing map description")

    def play_welcome(self):
        """Play the welcome message."""
        self.welcome_message.play()
        logger.info("Playing welcome message")

    def play_goodbye(self):
        """Play the goodbye message."""
        self.goodbye_message.play()
        logger.info("Playing goodbye message")

    def convey(self, zone, status):
        """
        Play audio based on zone interaction.

        Args:
            zone (int): Zone ID that the user is interacting with
            status (str): Interaction status ('moving', 'still', 'double_tap', etc.)
        """
        # Handle moving status with blip sounds
        if status == "moving":
            self._handle_moving_zone(zone)
            return

        # Ignore invalid zones
        if zone not in self.hotspots:
            self.prev_zone_name = None
            return

        # Get zone name and play audio if zone changed
        zone_name = self.hotspots[zone]['textDescription']
        if self.prev_zone_name != zone_name:
            self._play_zone_audio(zone)
            self.prev_zone_name = zone_name

    def _handle_moving_zone(self, zone):
        """
        Handle audio for moving through zones (play blip sound).

        Args:
            zone (int): Current zone ID
        """
        if (self.curr_zone_moving != zone and
            self.prev_zone_moving == zone and
            self.enable_blips):

            if self.player.playing:
                self.player.delete()

            try:
                self.player = self.blip_sound.play()
                logger.debug(f"Playing blip for zone {zone}")
            except Exception as e:
                logger.error(f"Cannot play blip sound: {e}")

            self.curr_zone_moving = zone

        self.prev_zone_moving = zone

    def _play_zone_audio(self, zone):
        """
        Play the audio description for a specific zone.

        Args:
            zone (int): Zone ID to play audio for
        """
        # Stop current audio
        self.player.pause()
        self.player.delete()

        # Play new audio if available
        if zone in self.sound_files:
            sound = self.sound_files[zone]
            try:
                self.player = sound.play()
                logger.debug(f"Playing audio for zone {zone}")
            except Exception as e:
                logger.error(f"Cannot play zone audio: {e}")

