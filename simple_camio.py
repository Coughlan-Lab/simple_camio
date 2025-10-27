"""
Simple CamIO - Interactive Map System with Hand Tracking.

This is the main entry point for the CamIO system, which uses hand tracking
and gesture recognition to enable interactive exploration of physical maps.
"""

import cv2 as cv
import time
import argparse
import pyglet
import queue
import threading
import signal
import logging
import numpy as np  # moved to top to avoid per-call imports

# Import from new modular structure
from config import CameraConfig, AudioConfig, WorkerConfig, UIConfig, TapDetectionConfig
from utils import select_camera_port, load_map_parameters, draw_rectangle_on_image, draw_rectangle_from_points, is_gesture_valid
from audio import AmbientSoundPlayer, ZoneAudioPlayer
from gesture_detection import GestureDetector, MovementMedianFilter
from pose_detector import CombinedPoseDetector
from sift_detector import SIFTModelDetectorMP
from interaction_policy import InteractionPolicy2D
from workers import PoseWorker, SIFTWorker, AudioWorker, AudioCommand

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Reusable identity homography to avoid per-frame allocations
IDENTITY_3 = np.eye(3, dtype=float)


def initialize_system(model_path):
    """
    Initialize all system components.

    Args:
        model_path (str): Path to the map configuration JSON file

    Returns:
        dict: Dictionary containing all initialized components
    """
    logger.info("Initializing CamIO system...")

    # Load map configuration
    model = load_map_parameters(model_path)

    # Select camera
    cam_port = select_camera_port()

    # Initialize components based on model type
    if model["modelType"] == "sift_2d_mediapipe":
        model_detector = SIFTModelDetectorMP(model)
        pose_detector = CombinedPoseDetector(model)
        gesture_detector = GestureDetector()
        motion_filter = MovementMedianFilter()
        interact = InteractionPolicy2D(model)
        camio_player = ZoneAudioPlayer(model)
        crickets_player = AmbientSoundPlayer(model['crickets'])
        heartbeat_player = AmbientSoundPlayer(model['heartbeat'])
    else:
        logger.error(f"Unknown model type: {model['modelType']}")
        raise ValueError(f"Unsupported model type: {model['modelType']}")

    # Configure audio
    heartbeat_player.set_volume(AudioConfig.HEARTBEAT_VOLUME)
    # Note: Welcome message will be played by AudioWorker after it starts

    logger.info("System initialization complete")

    return {
        'model': model,
        'cam_port': cam_port,
        'model_detector': model_detector,
        'pose_detector': pose_detector,
        'gesture_detector': gesture_detector,
        'motion_filter': motion_filter,
        'interact': interact,
        'camio_player': camio_player,
        'crickets_player': crickets_player,
        'heartbeat_player': heartbeat_player
    }


def setup_camera(cam_port):
    """
    Initialize and configure the camera.

    Args:
        cam_port (int): Camera port number

    Returns:
        cv.VideoCapture: Configured camera capture object
    """
    logger.info(f"Setting up camera on port {cam_port}")

    cap = cv.VideoCapture(cam_port, cv.CAP_DSHOW)
    cap.set(cv.CAP_PROP_FRAME_HEIGHT, CameraConfig.DEFAULT_HEIGHT)
    cap.set(cv.CAP_PROP_FRAME_WIDTH, CameraConfig.DEFAULT_WIDTH)
    cap.set(cv.CAP_PROP_FOCUS, CameraConfig.FOCUS)

    # Reduce latency
    try:
        cap.set(cv.CAP_PROP_BUFFERSIZE, CameraConfig.BUFFER_SIZE)
    except Exception as e:
        logger.warning(f"Could not set camera buffer size: {e}")

    # Enable OpenCV optimizations and set a reasonable thread count
    try:
        cv.setUseOptimized(True)
    except Exception:
        pass
    try:
        # Use about half the CPUs to reduce contention with Python threads
        num_threads = max(1, int(getattr(cv, "getNumberOfCPUs", lambda: 4)() // 2))
        cv.setNumThreads(num_threads)
    except Exception:
        pass

    return cap


def create_worker_threads(components, stop_event):
    """
    Create and start background worker threads.

    Args:
        components (dict): Dictionary of system components
        stop_event (threading.Event): Event for coordinated shutdown

    Returns:
        dict: Dictionary containing workers and synchronization objects
    """
    logger.info("Creating worker threads...")

    # Create queues
    pose_queue = queue.Queue(maxsize=WorkerConfig.POSE_QUEUE_MAXSIZE)
    sift_queue = queue.Queue(maxsize=WorkerConfig.SIFT_QUEUE_MAXSIZE)
    lock = threading.Lock()

    # Create workers
    pose_worker = PoseWorker(
        components['pose_detector'],
        pose_queue,
        lock,
        processing_scale=CameraConfig.POSE_PROCESSING_SCALE,
        stop_event=stop_event
    )

    sift_worker = SIFTWorker(
        components['model_detector'],
        sift_queue,
        lock,
        stop_event=stop_event
    )

    # Create audio worker for non-blocking audio playback
    audio_worker = AudioWorker(
        components['camio_player'],
        components['heartbeat_player'],
        components['crickets_player'],
        stop_event
    )

    # Start workers
    pose_worker.start()
    sift_worker.start()
    audio_worker.start()

    # Play welcome message through audio worker
    audio_worker.enqueue_command(AudioCommand('play_welcome'))

    logger.info("Worker threads started")

    return {
        'pose_queue': pose_queue,
        'sift_queue': sift_queue,
        'lock': lock,
        'pose_worker': pose_worker,
        'sift_worker': sift_worker,
        'audio_worker': audio_worker
    }


def setup_signal_handler(stop_event):
    """
    Setup signal handler for graceful shutdown.

    Args:
        stop_event (threading.Event): Event to signal on interrupt
    """
    def signal_handler(sig, frame):
        logger.info("Signal received, shutting down...")
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)


def feed_worker_queues(frame, gray, workers, model_detector):
    """
    Feed frames to worker queues for background processing.

    Args:
        frame: Color camera frame
        gray: Grayscale camera frame
        workers (dict): Worker threads and queues
        model_detector: SIFT detector instance
    """
    # Feed SIFT worker (always use latest frame, drop old ones)
    try:
        workers['sift_queue'].put_nowait(gray)
    except queue.Full:
        try:
            _ = workers['sift_queue'].get_nowait()
        except queue.Empty:
            pass
        try:
            workers['sift_queue'].put_nowait(gray)
        except queue.Full:
            pass

    # Feed pose worker with frame and current homography
    H_current = model_detector.H if model_detector.H is not None else IDENTITY_3
    try:
        workers['pose_queue'].put_nowait((frame, H_current))
    except queue.Full:
        try:
            _ = workers['pose_queue'].get_nowait()
        except queue.Empty:
            pass
        try:
            workers['pose_queue'].put_nowait((frame, H_current))
        except queue.Full:
            pass


def process_gestures_and_audio(gesture_loc, gesture_status, components,
                               last_double_tap_ts, audio_worker):
    """
    Process detected gestures and trigger appropriate audio feedback.

    Args:
        gesture_loc: Detected gesture location
        gesture_status: Status of the gesture
        components (dict): System components
        last_double_tap_ts (float): Timestamp of last double-tap
        audio_worker (AudioWorker): Audio worker for non-blocking playback

    Returns:
        float: Updated last_double_tap_ts
    """
    if not is_gesture_valid(gesture_loc):
        audio_worker.enqueue_command(AudioCommand('heartbeat_pause'))
        return last_double_tap_ts

    # Handle double-tap
    if gesture_status == 'double_tap':
        now = time.time()
        # Suppress repeated processing of same double-tap
        if now - last_double_tap_ts > TapDetectionConfig.DOUBLE_TAP_COOLDOWN_MAIN:
            try:
                zone_id = components['interact'].push_gesture(gesture_loc)
                audio_worker.enqueue_command(
                    AudioCommand('play_zone', zone_id=zone_id, gesture_status='double_tap')
                )
                last_double_tap_ts = now
                logger.info(f"Double-tap processed for zone {zone_id}")
            except Exception as e:
                logger.error(f"Error handling double_tap: {e}")
    else:
        # Normal gesture processing
        audio_worker.enqueue_command(AudioCommand('heartbeat_play'))
        zone_id = components['interact'].push_gesture(gesture_loc)
        audio_worker.enqueue_command(
            AudioCommand('play_zone', zone_id=zone_id, gesture_status=gesture_status)
        )

    return last_double_tap_ts


def draw_map_tracking(display_img, model_detector, interact, rect_flash_remaining):
    """
    Draw the map tracking rectangle on the display image.

    Args:
        display_img: Image to draw on
        model_detector: SIFT detector with tracking info
        interact: Interaction policy with map shape
        rect_flash_remaining (int): Frames remaining for flash effect

    Returns:
        tuple: (updated_image, updated_flash_remaining)
    """
    if getattr(model_detector, 'last_rect_pts', None) is not None:
        if rect_flash_remaining > 0:
            display_img = draw_rectangle_from_points(
                display_img, model_detector.last_rect_pts,
                color=UIConfig.COLOR_YELLOW, thickness=5
            )
            rect_flash_remaining -= 1
        else:
            display_img = draw_rectangle_from_points(
                display_img, model_detector.last_rect_pts,
                color=UIConfig.COLOR_GREEN, thickness=3
            )
    else:
        display_img = draw_rectangle_on_image(
            display_img, interact.image_map_color.shape, model_detector.H
        )

    return display_img, rect_flash_remaining


def draw_ui_overlay(display_img, model_detector, gesture_status, timer):
    """
    Draw status information overlay on the display image.

    Args:
        display_img: Image to draw on
        model_detector: SIFT detector for status
        gesture_status: Current gesture status
        timer (float): Previous frame timestamp for FPS calculation

    Returns:
        float: Current timestamp (new timer value)
    """
    # Tracking status
    status_text = model_detector.get_tracking_status()
    cv.putText(display_img, status_text, (10, 30),
              cv.FONT_HERSHEY_SIMPLEX, UIConfig.FONT_SCALE,
              UIConfig.COLOR_GREEN, UIConfig.FONT_THICKNESS)

    # Gesture status
    if gesture_status:
        cv.putText(display_img, f"Gesture: {gesture_status}", (10, 90),
                  cv.FONT_HERSHEY_SIMPLEX, UIConfig.FONT_SCALE,
                  UIConfig.COLOR_YELLOW, UIConfig.FONT_THICKNESS)

    # FPS counter
    prev_time = timer
    current_time = time.time()
    elapsed_time = current_time - prev_time
    if elapsed_time > 0:
        fps_text = f"FPS: {1/elapsed_time:.1f}"
        cv.putText(display_img, fps_text, (10, 60),
                  cv.FONT_HERSHEY_SIMPLEX, UIConfig.FONT_SCALE,
                  UIConfig.COLOR_GREEN, UIConfig.FONT_THICKNESS)

    return current_time


def handle_keyboard_input(waitkey, stop_event, frame, workers, components):
    """
    Handle keyboard input for user controls.

    Args:
        waitkey: Key code from cv.waitKey()
        stop_event: Event for shutdown signaling
        frame: Current camera frame
        workers (dict): Worker threads and queues
        components (dict): System components

    Returns:
        bool: True if should continue, False if should exit
    """
    # Quit
    if waitkey == 27 or waitkey == ord('q'):
        logger.info('Exiting...')
        stop_event.set()
        return False

    # Manual re-detection
    if waitkey == ord('h'):
        logger.info("Manual re-detection triggered by user")
        gray_now = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        components['model_detector'].requires_homography = True
        components['model_detector'].last_rect_pts = None

        # Force feed the frame to SIFT worker
        for _ in range(3):
            try:
                workers['sift_queue'].put_nowait(gray_now)
            except queue.Full:
                try:
                    _ = workers['sift_queue'].get_nowait()
                except queue.Empty:
                    pass
                try:
                    workers['sift_queue'].put_nowait(gray_now)
                except queue.Full:
                    pass
        workers['sift_worker'].trigger_redetect()

    # Toggle blips
    if waitkey == ord('b'):
        workers['audio_worker'].enqueue_command(AudioCommand('toggle_blips'))

    return True


def run_main_loop(cap, components, workers, stop_event):
    """
    Main processing loop for the CamIO system.

    Args:
        cap: Camera capture object
        components (dict): System components
        workers (dict): Worker threads and queues
        stop_event: Event for shutdown coordination
    """
    last_double_tap_ts = 0.0
    rect_flash_remaining = 0
    timer = time.time() - 1

    logger.info("Starting main loop")

    while cap.isOpened() and not stop_event.is_set():
        # Capture frame
        ret, frame = cap.read()
        if not ret:
            logger.error("No camera image returned")
            break

        # Convert to grayscale for SIFT
        gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)

        # Feed worker queues
        feed_worker_queues(frame, gray, workers, components['model_detector'])

        # Get latest pose detection results
        with workers['lock']:
            gesture_loc, gesture_status, annotated = workers['pose_worker'].latest

        display_img = frame if annotated is None else annotated

        # Check for homography update (triggers flash)
        if getattr(components['model_detector'], 'homography_updated', False):
            rect_flash_remaining = UIConfig.RECT_FLASH_FRAMES
            components['model_detector'].homography_updated = False

        # Process based on map detection status
        if components['model_detector'].H is None:
            # Map not detected - play ambient crickets
            workers['audio_worker'].enqueue_command(AudioCommand('heartbeat_pause'))
            workers['audio_worker'].enqueue_command(AudioCommand('crickets_play'))
        else:
            # Map detected - increment age counter
            try:
                components['model_detector'].frames_since_last_detection += 1
            except Exception:
                components['model_detector'].frames_since_last_detection = 1

            # Draw tracking rectangle
            display_img, rect_flash_remaining = draw_map_tracking(
                display_img, components['model_detector'],
                components['interact'], rect_flash_remaining
            )

            # Process gestures and audio
            last_double_tap_ts = process_gestures_and_audio(
                gesture_loc, gesture_status, components, last_double_tap_ts,
                workers['audio_worker']
            )

        # Draw UI overlay
        timer = draw_ui_overlay(display_img, components['model_detector'],
                               gesture_status, timer)

        # Display the frame
        cv.imshow('image reprojection', display_img)

        # Handle keyboard input
        waitkey = cv.waitKey(1)
        if not handle_keyboard_input(waitkey, stop_event, frame, workers, components):
            break

        # Update Pyglet event loop
        pyglet.clock.tick()
        pyglet.app.platform_event_loop.dispatch_posted_events()


def cleanup(cap, components, workers):
    """
    Clean up resources and shut down gracefully.

    Args:
        cap: Camera capture object
        components (dict): System components
        workers (dict): Worker threads
    """
    logger.info("Cleaning up resources...")

    # Play goodbye message through audio worker before stopping it
    try:
        workers['audio_worker'].enqueue_command(AudioCommand('play_goodbye'))
        # Give it a moment to play
        time.sleep(0.5)
    except Exception as e:
        logger.error(f"Error queueing goodbye message: {e}")

    # Stop worker threads
    workers['pose_worker'].stop()
    workers['sift_worker'].stop()
    workers['audio_worker'].stop()

    # Wait for threads to exit
    workers['pose_worker'].join(timeout=WorkerConfig.THREAD_SHUTDOWN_TIMEOUT)
    workers['sift_worker'].join(timeout=WorkerConfig.THREAD_SHUTDOWN_TIMEOUT)
    workers['audio_worker'].join(timeout=WorkerConfig.THREAD_SHUTDOWN_TIMEOUT)

    # Stop ambient sounds
    components['heartbeat_player'].pause_sound()
    components['crickets_player'].pause_sound()

    # Brief delay for audio to finish
    time.sleep(1)

    # Release camera and close windows
    cap.release()
    cv.destroyAllWindows()

    logger.info("Cleanup complete")


# ==================== Main Entry Point ====================

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='CamIO - Interactive Map System')
    parser.add_argument('--input1', help='Path to map configuration JSON file',
                       default='models/UkraineMap/UkraineMap.json')
    args = parser.parse_args()

    # Initialize system
    components = initialize_system(args.input1)
    cap = setup_camera(components['cam_port'])

    # Setup shutdown handling
    stop_event = threading.Event()
    setup_signal_handler(stop_event)

    # Create worker threads
    workers = create_worker_threads(components, stop_event)

    # UI state
    last_double_tap_ts = 0.0
    rect_flash_remaining = 0
    timer = time.time() - 1

    logger.info("Controls: 'h'=re-detect map, 'b'=toggle blips, 'q'=quit")

    # ==================== Main Loop ====================
    try:
        run_main_loop(cap, components, workers, stop_event)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, shutting down...")
        stop_event.set()
    finally:
        cleanup(cap, components, workers)
