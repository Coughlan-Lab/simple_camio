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
from src.config import CameraConfig, AudioConfig, WorkerConfig, UIConfig, TapDetectionConfig
from src.core.utils import select_camera_port, load_map_parameters, is_gesture_valid
from src.audio.audio import AmbientSoundPlayer, ZoneAudioPlayer
from src.detection.gesture_detection import GestureDetector, MovementMedianFilter
from src.detection.pose_detector import CombinedPoseDetector
from src.detection.sift_detector import SIFTModelDetectorMP
from src.core.interaction_policy import InteractionPolicy2D
from src.core.workers import PoseWorker, SIFTWorker, AudioWorker, AudioCommand
from src.core.display_thread import DisplayThread
from src.ui.display import draw_map_tracking, draw_ui_overlay, setup_camera

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

    # Configure audio volumes
    heartbeat_player.set_volume(AudioConfig.HEARTBEAT_VOLUME)
    crickets_player.set_volume(AudioConfig.CRICKETS_VOLUME)
    camio_player.set_zone_volume(AudioConfig.ZONE_DESCRIPTION_VOLUME)
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
                               last_double_tap_ts, audio_worker, hand_state):
    """
    Process detected gestures and trigger appropriate audio feedback.

    Args:
        gesture_loc: Detected gesture location
        gesture_status: Status of the gesture
        components (dict): System components
        last_double_tap_ts (float): Timestamp of last double-tap
        audio_worker (AudioWorker): Audio worker for non-blocking playback
        hand_state (dict): Hand detection state tracking

    Returns:
        tuple: (updated_last_double_tap_ts, updated_hand_state)
    """
    # Cooldown should be longer than zone filter stabilization time
    # Zone filter uses 10 samples at ~30-60fps = ~0.3s to stabilize
    ZONE_AUDIO_COOLDOWN = 0.8  # Increased to ensure filter stabilizes before playing audio
    
    if not is_gesture_valid(gesture_loc):
        # No hand detected - switch to crickets
        if hand_state['was_detected']:
            audio_worker.enqueue_command(AudioCommand('heartbeat_pause'))
            audio_worker.enqueue_command(AudioCommand('crickets_play'))
        
        # Reset hand state
        hand_state['was_detected'] = False
        hand_state['first_detected_ts'] = 0.0
        return last_double_tap_ts, hand_state

    # Hand detected
    if not hand_state['was_detected']:
        # Hand just appeared - pause crickets, play map description, start heartbeat
        audio_worker.enqueue_command(AudioCommand('crickets_pause'))
        
        # Play map description based on config
        if AudioConfig.PLAY_DESCRIPTION_ONCE:
            if not hand_state['description_played']:
                audio_worker.enqueue_command(AudioCommand('play_description'))
                hand_state['description_played'] = True
        else:
            # Play every time hand appears (supports multiple users)
            audio_worker.enqueue_command(AudioCommand('play_description'))
        
        audio_worker.enqueue_command(AudioCommand('heartbeat_play'))
        
        # Reset zone filter to ensure clean tracking from start
        components['interact'].reset_zone_filter()
        
        # Update zone tracking and set prev_zone_name to prevent zone audio on first appearance
        zone_id = components['interact'].push_gesture(gesture_loc)
        if zone_id in components['camio_player'].hotspots:
            components['camio_player'].prev_zone_name = components['camio_player'].hotspots[zone_id]['textDescription']
        else:
            components['camio_player'].prev_zone_name = None
        
        # Update hand state
        hand_state['was_detected'] = True
        hand_state['first_detected_ts'] = time.time()
        
        return last_double_tap_ts, hand_state

    # Check if we're still in the cooldown period after hand first appeared
    time_since_first_detection = time.time() - hand_state['first_detected_ts'] if hand_state['first_detected_ts'] > 0 else 999
    in_cooldown = time_since_first_detection < ZONE_AUDIO_COOLDOWN

    # Handle double-tap
    if gesture_status == 'double_tap':
        now = time.time()
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
    elif not in_cooldown:
        # Normal gesture processing (only if not in cooldown)
        zone_id = components['interact'].push_gesture(gesture_loc)
        audio_worker.enqueue_command(
            AudioCommand('play_zone', zone_id=zone_id, gesture_status=gesture_status)
        )
    else:
        # In cooldown - update zone tracking but don't play audio
        zone_id = components['interact'].push_gesture(gesture_loc)
        # Also update prev_zone_name to track current zone during cooldown
        # This prevents audio from playing when cooldown expires
        if zone_id in components['camio_player'].hotspots:
            components['camio_player'].prev_zone_name = components['camio_player'].hotspots[zone_id]['textDescription']

    return last_double_tap_ts, hand_state


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


def initialize_display(use_threaded, headless=False):
    """
    Initialize display system (threaded or traditional).
    
    Args:
        use_threaded (bool): Whether to use threaded display
        headless (bool): Whether to run in headless mode (no display)
        
    Returns:
        DisplayThread or None: Display thread if enabled, None otherwise
    """
    if headless:
        logger.info("Headless mode enabled - display disabled")
        return None
    
    if use_threaded:
        display_thread = DisplayThread(window_name='image reprojection')
        display_thread.start()
        logger.info("DisplayThread enabled for non-blocking rendering")
        return display_thread
    else:
        # Create window for non-threaded display
        cv.namedWindow('image reprojection', cv.WINDOW_NORMAL)
        return None


def capture_and_preprocess(cap, prof_times):
    """
    Capture frame from camera and convert to grayscale.
    
    Args:
        cap: Camera capture object
        prof_times (dict): Performance timing dictionary
        
    Returns:
        tuple: (success, frame, gray) or (False, None, None) on error
    """
    frame_start = time.time()
    ret, frame = cap.read()
    prof_times['capture'] += time.time() - frame_start
    
    if not ret:
        logger.error("No camera image returned")
        return False, None, None
    
    # Convert to grayscale for SIFT
    t = time.time()
    gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
    prof_times['gray'] += time.time() - t
    
    return True, frame, gray


def get_pose_results(workers, prof_times):
    """
    Get latest pose detection results from worker thread.
    
    Args:
        workers (dict): Worker threads and queues
        prof_times (dict): Performance timing dictionary
        
    Returns:
        tuple: (gesture_loc, gesture_status, annotated_frame)
    """
    t = time.time()
    with workers['lock']:
        gesture_loc, gesture_status, annotated = workers['pose_worker'].latest
    prof_times['lock'] += time.time() - t
    return gesture_loc, gesture_status, annotated


def process_map_detection(components, workers, display_img, rect_flash_remaining, 
                          gesture_loc, gesture_status, last_double_tap_ts, prof_times,
                          hand_state):
    """
    Process map detection status and handle gestures/audio.
    
    Args:
        components (dict): System components
        workers (dict): Worker threads
        display_img: Current display image
        rect_flash_remaining (int): Flash counter for rectangle
        gesture_loc: Current gesture location
        gesture_status: Current gesture status
        last_double_tap_ts (float): Last double-tap timestamp
        prof_times (dict): Performance timing dictionary
        hand_state (dict): Hand detection state tracking
        
    Returns:
        tuple: (updated_display_img, rect_flash_remaining, last_double_tap_ts, updated_hand_state)
    """
    t = time.time()
    
    if components['model_detector'].H is None:
        # Map not detected - play ambient crickets
        if hand_state['was_detected']:
            workers['audio_worker'].enqueue_command(AudioCommand('heartbeat_pause'))
            workers['audio_worker'].enqueue_command(AudioCommand('crickets_play'))
        hand_state['was_detected'] = False
        hand_state['first_detected_ts'] = 0.0
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
        last_double_tap_ts, hand_state = process_gestures_and_audio(
            gesture_loc, gesture_status, components, last_double_tap_ts,
            workers['audio_worker'], hand_state
        )
    
    prof_times['draw'] += time.time() - t
    return display_img, rect_flash_remaining, last_double_tap_ts, hand_state


def handle_display_and_input(display_img, display_frame_counter, display_thread, 
                             stop_event, frame, workers, components, prof_times, fps_state, headless=False):
    """
    Handle frame display and keyboard input.

    Args:
        display_img: Image to display
        display_frame_counter (int): Frame skip counter
        display_thread: DisplayThread or None
        stop_event: Event for shutdown coordination
        frame: Current camera frame
        workers (dict): Worker threads
        components (dict): System components
        prof_times (dict): Performance timing dictionary
        fps_state (dict): FPS tracking state
        headless (bool): Whether running in headless mode (no display)
        
    Returns:
        tuple: (should_continue, updated_counter, updated_fps_state)
    """
    # Skip display and input handling if in headless mode
    if headless:
        # In headless mode, still check stop_event periodically
        return True, display_frame_counter, fps_state
    
    # Check if should display this frame
    display_frame_counter += 1
    should_display = (display_frame_counter >= CameraConfig.DISPLAY_FRAME_SKIP)
    if should_display:
        display_frame_counter = 0
    
    # Display frame (threaded or direct)
    t = time.time()
    if CameraConfig.USE_THREADED_DISPLAY:
        # Non-blocking display via thread
        if should_display and display_thread:
            display_thread.show(display_img)
        # ALWAYS check keyboard input (critical for 'q' to work reliably)
        waitkey = display_thread.get_last_key() if display_thread else 255
    else:
        # Blocking display (traditional)
        if should_display:
            cv.imshow('image reprojection', display_img)
            waitkey = cv.waitKey(1) & 0xFF
        else:
            # Still need to call waitKey to process window events
            waitkey = cv.waitKey(1) & 0xFF
    prof_times['show'] += time.time() - t
    
    # Handle keyboard input
    t = time.time()
    should_continue = True
    if waitkey != 255:  # 255 means no key pressed
        if not handle_keyboard_input(waitkey, stop_event, frame, workers, components):
            should_continue = False
    prof_times['key'] += time.time() - t
    
    return should_continue, display_frame_counter, fps_state
def update_performance_stats(frame_count, prof_start, prof_times, PROF_INTERVAL):
    """
    Update and log performance statistics.
    
    Args:
        frame_count (int): Number of frames processed
        prof_start (float): Start time of profiling period
        prof_times (dict): Performance timing dictionary
        PROF_INTERVAL (float): Profiling interval in seconds
        
    Returns:
        tuple: (updated_frame_count, updated_prof_start, updated_prof_times)
    """
    frame_count += 1
    elapsed = time.time() - prof_start
    
    if elapsed >= PROF_INTERVAL:
        fps = frame_count / elapsed
        logger.info(f"=== Performance (last {frame_count} frames, {elapsed:.1f}s, {fps:.1f} FPS) ===")
        for key, val in prof_times.items():
            pct = 100 * val / elapsed
            logger.info(f"  {key:10s}: {val*1000:.1f}ms ({pct:.1f}%)")
        
        # Reset counters
        frame_count = 0
        prof_start = time.time()
        prof_times = {k: 0 for k in prof_times}
    
    return frame_count, prof_start, prof_times


def run_main_loop(cap, components, workers, stop_event, headless=False):
    """
    Main processing loop for the CamIO system.

    Args:
        cap: Camera capture object
        components (dict): System components
        workers (dict): Worker threads and queues
        stop_event: Event for shutdown coordination
        headless (bool): Whether to run in headless mode (no display)
    """
    # Initialize state variables
    last_double_tap_ts = 0.0
    rect_flash_remaining = 0
    timer = time.time() - 1
    
    # Hand detection state (consolidated into one dict)
    hand_state = {
        'was_detected': False,         # Whether hand was detected in previous frame
        'description_played': False,   # Whether map description has been played once
        'first_detected_ts': 0.0       # Timestamp when hand was first detected (for cooldown)
    }
    
    # FPS tracking state
    fps_state = {
        'display_count': 0,     # Counts only displayed frames
        'start_time': time.time(),
        'display_fps': 0.0      # Actual display update rate
    }

    logger.info(f"Starting main loop (headless={headless})")

    # Performance profiling variables
    frame_count = 0
    prof_start = time.time()
    prof_times = {'capture': 0, 'gray': 0, 'feed': 0, 'lock': 0, 'draw': 0, 'ui': 0, 'show': 0, 'key': 0, 'pyglet': 0}
    PROF_INTERVAL = 15.0  # Log performance every 15 seconds
    display_frame_counter = 0  # Counter for frame skip
    
    # Initialize display system (disabled in headless mode)
    display_thread = initialize_display(CameraConfig.USE_THREADED_DISPLAY, headless=headless)

    # Play welcome message at startup and start with crickets
    workers['audio_worker'].enqueue_command(AudioCommand('play_welcome'))
    workers['audio_worker'].enqueue_command(AudioCommand('crickets_play'))

    # Main processing loop
    while cap.isOpened() and not stop_event.is_set():
        # Capture and preprocess frame
        success, frame, gray = capture_and_preprocess(cap, prof_times)
        if not success:
            break
        
        # Early exit check for responsiveness
        if stop_event.is_set():
            break

        # Feed worker queues
        t = time.time()
        feed_worker_queues(frame, gray, workers, components['model_detector'])
        prof_times['feed'] += time.time() - t

        # Get latest pose detection results
        gesture_loc, gesture_status, annotated = get_pose_results(workers, prof_times)
        display_img = frame if annotated is None else annotated

        # Check for homography update (triggers flash)
        if getattr(components['model_detector'], 'homography_updated', False):
            rect_flash_remaining = UIConfig.RECT_FLASH_FRAMES
            components['model_detector'].homography_updated = False

        # Process map detection and gestures
        display_img, rect_flash_remaining, last_double_tap_ts, hand_state = process_map_detection(
            components, workers, display_img, rect_flash_remaining,
            gesture_loc, gesture_status, last_double_tap_ts, prof_times, hand_state
        )

        # Draw UI overlay
        t = time.time()
        timer, fps_state = draw_ui_overlay(display_img, components['model_detector'],
                                           gesture_status, timer, fps_state, cap)
        prof_times['ui'] += time.time() - t

        # Handle display and keyboard input
        should_continue, display_frame_counter, fps_state = handle_display_and_input(
            display_img, display_frame_counter, display_thread,
            stop_event, frame, workers, components, prof_times, fps_state, headless=headless
        )
        if not should_continue:
            break

        # Update Pyglet event loop
        t = time.time()
        pyglet.clock.tick()
        pyglet.app.platform_event_loop.dispatch_posted_events()
        prof_times['pyglet'] += time.time() - t

        # Update performance statistics
        frame_count, prof_start, prof_times = update_performance_stats(
            frame_count, prof_start, prof_times, PROF_INTERVAL
        )
    
    # Cleanup display thread
    if display_thread:
        display_thread.stop()


def stop_all_sounds(components):
    """
    Stop all currently playing sounds.
    
    Args:
        components (dict): System components containing audio players
    """
    logger.info("Stopping all sounds...")
    
    # Stop ambient sounds
    try:
        components['heartbeat_player'].pause_sound()
    except Exception as e:
        logger.debug(f"Error stopping heartbeat: {e}")
    
    try:
        components['crickets_player'].pause_sound()
    except Exception as e:
        logger.debug(f"Error stopping crickets: {e}")
    
    # Stop all zone audio player sounds (includes welcome, goodbye, description, zones)
    try:
        components['camio_player'].stop_all()
    except Exception as e:
        logger.debug(f"Error stopping camio_player: {e}")


def cleanup(cap, components, workers):
    """
    Clean up resources and shut down gracefully.

    Args:
        cap: Camera capture object
        components (dict): System components
        workers (dict): Worker threads
    """
    logger.info("Cleaning up resources...")

    # Save collected tap data if enabled
    try:
        pose_detector = components.get('pose_detector')
        if pose_detector and hasattr(pose_detector, 'data_collector'):
            collector = pose_detector.data_collector
            logger.debug(f"Data collector found: enabled={collector.enabled}, "
                        f"total_collected={collector.total_collected}")
            if collector.enabled and collector.total_collected > 0:
                logger.info(f"Saving {collector.total_collected} collected tap samples...")
                stats = collector.get_statistics()
                logger.info(f"  Positive: {stats['positive_samples']}, "
                          f"Negative: {stats['negative_samples']}")
                filepath = collector.save_json()
                if filepath:
                    logger.info(f"Tap data saved to {filepath}")
            elif collector.enabled and collector.total_collected == 0:
                logger.info("Data collection was enabled but no samples were collected")
        else:
            logger.debug("No data collector found in pose_detector")
    except Exception as e:
        logger.error(f"Error saving collected tap data: {e}", exc_info=True)

    # Stop all currently playing sounds before goodbye
    stop_all_sounds(components)
    
    # Clear any pending audio commands in the queue
    workers['audio_worker'].clear_queue()

    # Play goodbye using AudioWorker's blocking method (cleaner architecture)
    # This method bypasses the async queue and returns a player object
    try:
        logger.info("Playing goodbye message via AudioWorker blocking method...")
        
        goodbye_player = workers['audio_worker'].play_goodbye_blocking()
        logger.info(f"Goodbye player created: {goodbye_player}")
        
        # Keep pyglet event loop running so audio can actually play
        goodbye_start = time.time()
        goodbye_duration = 1.0
        
        while time.time() - goodbye_start < goodbye_duration:
            # Check if player is still alive and playing
            if goodbye_player:
                pyglet.clock.tick()
                pyglet.app.platform_event_loop.dispatch_posted_events()
            time.sleep(0.01)  # Small sleep to avoid busy-waiting
            
        logger.info("Goodbye message playback time completed")
        
        # Clean up goodbye player
        if goodbye_player:
            try:
                goodbye_player.pause()
                goodbye_player.delete()
            except Exception as e:
                logger.debug(f"Error cleaning up goodbye player: {e}")
                
    except Exception as e:
        logger.error(f"Error playing goodbye message: {e}", exc_info=True)

    # Stop worker threads
    logger.info("Stopping worker threads...")
    workers['pose_worker'].stop()
    workers['sift_worker'].stop()
    workers['audio_worker'].stop()

    # Wait for threads to exit
    workers['pose_worker'].join(timeout=WorkerConfig.THREAD_SHUTDOWN_TIMEOUT)
    workers['sift_worker'].join(timeout=WorkerConfig.THREAD_SHUTDOWN_TIMEOUT)
    workers['audio_worker'].join(timeout=WorkerConfig.THREAD_SHUTDOWN_TIMEOUT)

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
    parser.add_argument('--headless', action='store_true',
                       help='Run in headless mode (no display window) - useful for Raspberry Pi daemon mode')
    args = parser.parse_args()

    # Apply headless mode to configuration if specified
    if args.headless:
        CameraConfig.HEADLESS = True
        logger.info("Headless mode enabled via command line argument")

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

    if not CameraConfig.HEADLESS:
        logger.info("Controls: 'h'=re-detect map, 'b'=toggle blips, 'q'=quit")
    else:
        logger.info("Running in headless mode. Send SIGINT (Ctrl+C) or SIGTERM to stop.")

    # ==================== Main Loop ====================
    try:
        run_main_loop(cap, components, workers, stop_event, headless=CameraConfig.HEADLESS)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, shutting down...")
        stop_event.set()
    finally:
        cleanup(cap, components, workers)
