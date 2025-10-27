"""
Background worker threads for asynchronous processing.

This module contains worker threads that handle pose detection, SIFT tracking,
and audio playback in parallel with the main UI loop to maintain responsive frame rates.
"""

import threading
import queue
import time
import cv2 as cv
import logging
from config import WorkerConfig
from utils import normalize_gesture_location

logger = logging.getLogger(__name__)


# ==================== Audio Worker ====================

class AudioCommand:
    """Represents an audio command to be executed."""

    def __init__(self, command_type, **kwargs):
        """
        Initialize an audio command.

        Args:
            command_type (str): Type of command ('play_zone', 'play_welcome', 'play_goodbye',
                                                  'heartbeat_play', 'heartbeat_pause', etc.)
            **kwargs: Command-specific parameters
        """
        self.command_type = command_type
        self.params = kwargs


class AudioWorker(threading.Thread):
    """
    Background thread for handling all audio playback operations.

    This worker processes audio commands from a queue, preventing audio
    operations from blocking the main processing loop. This improves
    frame processing consistency and overall system responsiveness.
    """

    def __init__(self, camio_player, heartbeat_player, crickets_player,
                 stop_event, queue_maxsize=50):
        """
        Initialize the audio worker.

        Args:
            camio_player (ZoneAudioPlayer): Player for zone-based audio
            heartbeat_player (AmbientSoundPlayer): Heartbeat sound player
            crickets_player (AmbientSoundPlayer): Ambient crickets player
            stop_event (threading.Event): Event to signal shutdown
            queue_maxsize (int): Maximum size of command queue
        """
        super().__init__(daemon=True, name="AudioWorker")

        self.camio_player = camio_player
        self.heartbeat_player = heartbeat_player
        self.crickets_player = crickets_player
        self.stop_event = stop_event
        self.command_queue = queue.Queue(maxsize=queue_maxsize)

        logger.info("AudioWorker initialized")

    def enqueue_command(self, command):
        """
        Add an audio command to the queue (non-blocking).

        Args:
            command (AudioCommand): Command to execute

        Returns:
            bool: True if command was enqueued, False if queue was full
        """
        try:
            self.command_queue.put_nowait(command)
            return True
        except queue.Full:
            logger.warning(f"Audio queue full, dropping command: {command.command_type}")
            return False

    def run(self):
        """Main worker loop - processes audio commands from queue."""
        logger.info("AudioWorker started")

        while not self.stop_event.is_set():
            try:
                # Wait for command with timeout to allow checking stop_event
                command = self.command_queue.get(timeout=0.1)
                self._execute_command(command)
                self.command_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing audio command: {e}", exc_info=True)

        logger.info("AudioWorker stopped")

    def _execute_command(self, command):
        """
        Execute a single audio command.

        Args:
            command (AudioCommand): Command to execute
        """
        try:
            cmd_type = command.command_type
            params = command.params

            if cmd_type == 'play_zone':
                zone_id = params.get('zone_id')
                gesture_status = params.get('gesture_status', 'pointing')
                self.camio_player.convey(zone_id, gesture_status)

            elif cmd_type == 'play_welcome':
                self.camio_player.play_welcome()

            elif cmd_type == 'play_goodbye':
                self.camio_player.play_goodbye()

            elif cmd_type == 'heartbeat_play':
                self.heartbeat_player.play_sound()

            elif cmd_type == 'heartbeat_pause':
                self.heartbeat_player.pause_sound()

            elif cmd_type == 'crickets_play':
                self.crickets_player.play_sound()

            elif cmd_type == 'crickets_pause':
                self.crickets_player.pause_sound()

            elif cmd_type == 'toggle_blips':
                self.camio_player.enable_blips = not self.camio_player.enable_blips
                status = "enabled" if self.camio_player.enable_blips else "disabled"
                logger.info(f"Blips {status}")

            else:
                logger.warning(f"Unknown audio command type: {cmd_type}")

        except Exception as e:
            logger.error(f"Error executing command {command.command_type}: {e}", exc_info=True)

    def stop(self):
        """Signal the worker to stop."""
        logger.info("Stopping AudioWorker...")
        self.stop_event.set()


# ==================== Pose Worker ====================


class PoseWorker(threading.Thread):
    """
    Background worker thread for hand pose detection.

    This worker processes camera frames asynchronously to detect hand poses
    without blocking the main UI thread, enabling smooth video display.
    """

    def __init__(self, pose_detector, in_queue, lock, processing_scale=0.5,
                 stop_event=None):
        """
        Initialize the pose worker thread.

        Args:
            pose_detector: PoseDetectorMP instance for hand detection
            in_queue: Queue for receiving (frame, homography) tuples
            lock: Threading lock for synchronized access to results
            processing_scale (float): Scale factor for processing (smaller = faster)
            stop_event: Event to signal thread shutdown
        """
        super().__init__(daemon=True)
        self.pose_detector = pose_detector
        self.in_queue = in_queue
        self.lock = lock
        self.processing_scale = processing_scale
        self.latest = (None, None, None)  # (gesture_loc, status, annotated_image)
        self.running = True
        self.stop_event = stop_event

        logger.info(f"Initialized pose worker with scale {processing_scale}")

    def run(self):
        """Main worker loop - processes frames from queue."""
        while self.running and (self.stop_event is None or not self.stop_event.is_set()):
            try:
                frame, H = self.in_queue.get(timeout=WorkerConfig.QUEUE_TIMEOUT)
            except queue.Empty:
                continue

            # Run pose detection (downscaled processing inside)
            try:
                gesture_loc, gesture_status, annotated = self.pose_detector.detect(
                    frame, H, None, processing_scale=self.processing_scale, draw=True
                )
            except Exception as e:
                logger.error(f"Pose detection error: {e}")
                gesture_loc, gesture_status, annotated = None, None, None

            # Normalize gesture location to ensure consistent format
            gesture_loc = normalize_gesture_location(gesture_loc)

            # Update latest results with thread-safe lock
            with self.lock:
                self.latest = (gesture_loc, gesture_status, annotated)

    def stop(self):
        """Signal the worker to stop and exit."""
        logger.info("Stopping pose worker")
        self.running = False
        if self.stop_event is not None:
            self.stop_event.set()


class SIFTWorker(threading.Thread):
    """
    Background worker thread for SIFT-based template tracking.

    This worker handles template detection and validation asynchronously,
    allowing the main thread to focus on rendering and user interaction.
    """

    def __init__(self, sift_detector, in_queue, lock, stop_event=None):
        """
        Initialize the SIFT worker thread.

        Args:
            sift_detector: SIFTModelDetectorMP instance for template tracking
            in_queue: Queue for receiving grayscale frames
            lock: Threading lock for synchronized access to results
            stop_event: Event to signal thread shutdown
        """
        super().__init__(daemon=True)
        self.sift_detector = sift_detector
        self.in_queue = in_queue
        self.lock = lock
        self.running = True
        self.force_redetect = False
        self.validate_interval = WorkerConfig.SIFT_RETRY_ATTEMPTS
        self._last_validation_ts = 0.0
        self.stop_event = stop_event

        logger.info("Initialized SIFT worker")

    def run(self):
        """
        Main worker loop - processes frames for template detection/validation.

        If homography exists, performs periodic validation.
        If homography is missing or invalid, attempts full detection.
        """
        RETRIES = WorkerConfig.SIFT_RETRY_ATTEMPTS

        while self.running and (self.stop_event is None or not self.stop_event.is_set()):
            try:
                frame = self.in_queue.get(timeout=WorkerConfig.QUEUE_GET_TIMEOUT)
            except queue.Empty:
                continue

            try:
                # If tracking is good and no force flag, do periodic validation
                if (not self.sift_detector.requires_homography) and (not self.force_redetect):
                    now = time.time()
                    if now - self._last_validation_ts >= self.validate_interval:
                        self._last_validation_ts = now
                        valid = self.sift_detector.quick_validate_position(
                            frame, min_matches=6, position_threshold=40
                        )
                        if not valid:
                            # Mark stale and proceed to re-detection
                            self.sift_detector.requires_homography = True
                            self.sift_detector.last_rect_pts = None
                        else:
                            continue

                # Need to detect/re-detect homography
                detected = False
                attempts = self._prepare_detection_attempts(frame)

                # Try detection with different preprocessing
                for attempt_img in attempts:
                    try:
                        retval, H, _ = self.sift_detector.detect(
                            attempt_img, force_redetect=self.force_redetect
                        )
                    except Exception as e:
                        logger.debug(f"Detection attempt failed: {e}")
                        retval, H = False, None

                    # Clear force flag after first attempt
                    if self.force_redetect:
                        self.force_redetect = False

                    if retval and H is not None:
                        detected = True
                        break

                # If preprocessing didn't work, try multiple retries with raw frame
                if not detected:
                    for _ in range(RETRIES):
                        try:
                            retval, H, _ = self.sift_detector.detect(
                                frame, force_redetect=False
                            )
                        except Exception as e:
                            logger.debug(f"Retry failed: {e}")
                            retval, H = False, None

                        if retval and H is not None:
                            break

            except Exception as e:
                logger.error(f"SIFT worker error: {e}")

    def _prepare_detection_attempts(self, frame):
        """
        Prepare multiple versions of the frame with different preprocessing.

        Args:
            frame (numpy.ndarray): Original grayscale frame

        Returns:
            list: List of preprocessed frames to try for detection
        """
        attempts = [frame]

        # CLAHE (Contrast Limited Adaptive Histogram Equalization)
        try:
            clahe = cv.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            attempts.append(clahe.apply(frame))
        except Exception as e:
            logger.debug(f"CLAHE preprocessing failed: {e}")

        # Gaussian blur
        try:
            attempts.append(cv.GaussianBlur(frame, (5, 5), 0))
        except Exception as e:
            logger.debug(f"Blur preprocessing failed: {e}")

        return attempts

    def trigger_redetect(self):
        """Manually trigger re-detection of the template."""
        logger.info("Manual re-detection triggered")
        self.force_redetect = True

    def stop(self):
        """Signal the worker to stop and exit."""
        logger.info("Stopping SIFT worker")
        self.running = False
        if self.stop_event is not None:
            self.stop_event.set()

