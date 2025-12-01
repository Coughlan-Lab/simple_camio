"""
Audio playback components for Simple CamIO.

This module handles all audio-related functionality including ambient sounds,
sound effects, and zone-based audio descriptions.

HEADLESS MODE SUPPORT:
For Raspberry Pi or other headless systems without X11, this module will
automatically fall back to pygame for audio playback if pyglet fails.
Pygame doesn't require X11 display for audio operations.
"""

import os
import sys
import logging

logger = logging.getLogger(__name__)

# Try to import pyglet first, fall back to pygame if it fails
AUDIO_BACKEND = None
USE_PYGLET = False
USE_PYGAME = False

# Attempt to import and initialize pyglet
try:
    # Set DISPLAY if not present (some systems can play audio without actual display)
    if 'DISPLAY' not in os.environ:
        os.environ['DISPLAY'] = ':0'
        logger.info("Set DISPLAY=:0 for pyglet audio")
    
    import pyglet.media
    USE_PYGLET = True
    AUDIO_BACKEND = 'pyglet'
    logger.info("Audio backend: pyglet")
except Exception as e:
    logger.warning(f"Failed to initialize pyglet: {e}")
    logger.info("Attempting to use pygame as audio backend...")
    
    # Fall back to pygame
    try:
        import pygame
        # Initialize pygame mixer for audio only
        pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=512)
        pygame.mixer.init()
        USE_PYGAME = True
        AUDIO_BACKEND = 'pygame'
        logger.info("Audio backend: pygame (headless compatible)")
    except Exception as e2:
        logger.error(f"Failed to initialize pygame: {e2}")
        logger.error("No audio backend available! Audio will not work.")
        logger.error("For headless operation, install pygame: pip install pygame")
        AUDIO_BACKEND = None

if AUDIO_BACKEND is None:
    logger.warning("="*60)
    logger.warning("WARNING: No audio backend available!")
    logger.warning("Install pygame for headless audio: pip install pygame")
    logger.warning("Or run with xvfb: xvfb-run python simple_camio.py --headless")
    logger.warning("="*60)


class AmbientSoundPlayer:
    """
    Player for looping ambient background sounds.

    This class manages a single looping audio track with volume control,
    typically used for ambient sounds like crickets or heartbeat.
    Supports both pyglet and pygame backends.
    """

    def __init__(self, soundfile):
        """
        Initialize the ambient sound player.

        Args:
            soundfile (str): Path to the audio file to play
        """
        self.soundfile = soundfile
        self.volume = 1.0
        
        if USE_PYGLET:
            import pyglet.media
            self.sound = pyglet.media.load(soundfile, streaming=False)
            self.player = pyglet.media.Player()
            self.player.queue(self.sound)
            self.player.eos_action = 'loop'
            self.player.loop = True
            logger.debug(f"Initialized pyglet ambient sound player with {soundfile}")
        elif USE_PYGAME:
            import pygame
            self.sound = pygame.mixer.Sound(soundfile)
            self.player = None
            self._playing = False
            logger.debug(f"Initialized pygame ambient sound player with {soundfile}")
        else:
            logger.warning(f"No audio backend - ambient sound not loaded: {soundfile}")
            self.sound = None
            self.player = None

    def set_volume(self, volume):
        """
        Set the playback volume.

        Args:
            volume (float): Volume level between 0.0 and 1.0
        """
        if 0 <= volume <= 1:
            self.volume = volume
            if USE_PYGLET and self.player:
                self.player.volume = volume
            elif USE_PYGAME and self.sound:
                self.sound.set_volume(volume)
            logger.debug(f"Set volume to {volume}")

    def play_sound(self):
        """Start playing the ambient sound if not already playing."""
        if USE_PYGLET and self.player:
            if not self.player.playing:
                self.player.play()
                logger.debug("Started pyglet ambient sound playback")
        elif USE_PYGAME and self.sound:
            if not self._playing:
                # Set volume before playing (pygame requirement)
                self.sound.set_volume(self.volume)
                self.sound.play(loops=-1)  # -1 means loop forever
                self._playing = True
                logger.debug(f"Started pygame ambient sound playback at volume {self.volume}")

    def pause_sound(self):
        """Pause the ambient sound if currently playing."""
        if USE_PYGLET and self.player:
            if self.player.playing:
                self.player.pause()
                logger.debug("Paused pyglet ambient sound playback")
        elif USE_PYGAME and self.sound:
            if self._playing:
                self.sound.stop()
                self._playing = False
                logger.debug("Stopped pygame ambient sound playback")


class ZoneAudioPlayer:
    """
    Manages audio playback for interactive zones on the map.

    This class handles playing audio descriptions when users interact with
    different zones, including blip sounds for zone transitions and
    descriptive audio for each hotspot.
    Supports both pyglet and pygame backends.
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
        self.enable_blips = False
        
        if USE_PYGLET:
            import pyglet.media
            self.player = pyglet.media.Player()
            self.welcome_player = None
            self.goodbye_player = None
            
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
            
        elif USE_PYGAME:
            import pygame
            self.player = None
            self.welcome_player = None
            self.goodbye_player = None
            self.current_channel = None  # Track playing channel
            
            # Load blip sound
            self.blip_sound = pygame.mixer.Sound(self.model['blipsound'])
            
            # Load map description if available
            if "map_description" in self.model:
                self.map_description = pygame.mixer.Sound(self.model['map_description'])
                self.have_played_description = False
            else:
                self.have_played_description = True
            
            # Load welcome and goodbye messages
            self.welcome_message = pygame.mixer.Sound(self.model['welcome_message'])
            self.goodbye_message = pygame.mixer.Sound(self.model['goodbye_message'])
            
        else:
            logger.warning("No audio backend - zone audio player disabled")
            self.player = None
            self.blip_sound = None
            self.map_description = None
            self.welcome_message = None
            self.goodbye_message = None
            self.have_played_description = True

        # Load audio files for each hotspot
        self._load_hotspot_audio()

        logger.info(f"Initialized zone audio player ({AUDIO_BACKEND}) with {len(self.hotspots)} hotspots")

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
                if USE_PYGLET:
                    import pyglet.media
                    self.sound_files[key] = pyglet.media.load(
                        hotspot['audioDescription'],
                        streaming=False
                    )
                elif USE_PYGAME:
                    import pygame
                    self.sound_files[key] = pygame.mixer.Sound(hotspot['audioDescription'])
            else:
                logger.warning(f"Audio file not found: {hotspot['audioDescription']}")

    def set_zone_volume(self, volume):
        """
        Set the volume for zone audio playback (descriptions, welcome, goodbye).
        
        Args:
            volume (float): Volume level between 0.0 and 1.0
        """
        if not 0 <= volume <= 1:
            logger.warning(f"Invalid volume {volume}, must be between 0.0 and 1.0")
            return
            
        # Note: For pygame, volumes are set per-sound when playing
        # For pyglet, we'll store the volume to apply when playing
        self.zone_volume = volume
        
        # Set volume for all loaded zone sounds
        if USE_PYGAME:
            if self.blip_sound:
                self.blip_sound.set_volume(volume * 0.3)  # Blips quieter than descriptions
            if hasattr(self, 'map_description') and self.map_description:
                self.map_description.set_volume(volume)
            if self.welcome_message:
                self.welcome_message.set_volume(volume)
            if self.goodbye_message:
                self.goodbye_message.set_volume(volume)
            for sound in self.sound_files.values():
                sound.set_volume(volume)
        
        logger.debug(f"Set zone audio volume to {volume}")

    def play_description(self):
        """Play the map description audio (only once)."""
        if not self.have_played_description:
            if USE_PYGLET:
                self.player = self.map_description.play()
            elif USE_PYGAME:
                self.map_description.play()
            self.have_played_description = True
            logger.info("Playing map description")

    def play_welcome(self):
        """Play the welcome message."""
        if USE_PYGLET:
            # Stop previous welcome if still playing
            if self.welcome_player and self.welcome_player.playing:
                self.welcome_player.pause()
                self.welcome_player.delete()
            self.welcome_player = self.welcome_message.play()
        elif USE_PYGAME:
            self.welcome_message.play()
        logger.info("Playing welcome message")

    def play_goodbye(self, blocking=False):
        """
        Play the goodbye message.
        
        Args:
            blocking (bool): If True, returns player object for caller to manage.
                           If False (default), plays asynchronously.
        
        Returns:
            pyglet.media.Player or None: Player object if blocking=True, else None
        """
        if USE_PYGLET:
            # Stop previous goodbye if still playing
            if self.goodbye_player and self.goodbye_player.playing:
                logger.info("Stopping previous goodbye player")
                self.goodbye_player.pause()
                self.goodbye_player.delete()
            
            try:
                player = self.goodbye_message.play()
                logger.info("Playing goodbye message")
                if blocking:
                    return player
                else:
                    self.goodbye_player = player
                    return None
            except Exception as e:
                logger.error(f"Error starting goodbye player: {e}", exc_info=True)
                raise
        elif USE_PYGAME:
            self.goodbye_message.play()
            logger.info("Playing goodbye message (pygame)")
            return None
        
        return None
    
    def stop_all(self):
        """
        Stop all currently playing audio.
        
        Stops zone audio, welcome, goodbye, description, and blips.
        """
        logger.info("Stopping all ZoneAudioPlayer sounds...")
        
        if USE_PYGLET:
            # Stop main zone player
            try:
                if self.player and self.player.playing:
                    self.player.pause()
                    self.player.delete()
            except Exception as e:
                logger.debug(f"Error stopping main player: {e}")
            
            # Stop welcome player
            try:
                if self.welcome_player and self.welcome_player.playing:
                    self.welcome_player.pause()
                    self.welcome_player.delete()
            except Exception as e:
                logger.debug(f"Error stopping welcome player: {e}")
            
            # Stop goodbye player
            try:
                if self.goodbye_player and self.goodbye_player.playing:
                    self.goodbye_player.pause()
                    self.goodbye_player.delete()
            except Exception as e:
                logger.debug(f"Error stopping goodbye player: {e}")
        
        elif USE_PYGAME:
            import pygame
            pygame.mixer.stop()  # Stop all channels
            logger.debug("Stopped all pygame mixer channels")

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

            if USE_PYGLET:
                if self.player and self.player.playing:
                    self.player.delete()
                try:
                    self.player = self.blip_sound.play()
                    logger.debug(f"Playing blip for zone {zone}")
                except Exception as e:
                    logger.error(f"Cannot play blip sound: {e}")
            elif USE_PYGAME:
                self.blip_sound.play()
                logger.debug(f"Playing blip for zone {zone}")

            self.curr_zone_moving = zone

        self.prev_zone_moving = zone

    def _play_zone_audio(self, zone):
        """
        Play the audio description for a specific zone.

        Args:
            zone (int): Zone ID to play audio for
        """
        if USE_PYGLET:
            # Stop current audio
            if self.player:
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
        
        elif USE_PYGAME:
            # Stop current audio
            import pygame
            pygame.mixer.stop()
            
            # Play new audio if available
            if zone in self.sound_files:
                sound = self.sound_files[zone]
                try:
                    sound.play()
                    logger.debug(f"Playing audio for zone {zone}")
                except Exception as e:
                    logger.error(f"Cannot play zone audio: {e}")

