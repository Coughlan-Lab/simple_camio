# Simple CamIO - Refactored Architecture

## Overview

This document describes the refactored architecture of Simple CamIO, an interactive map system using hand tracking, robust tap detection, SIFT-based template tracking, and asynchronous audio playback.

## Project Structure

```
simple_camio/
├── config.py                  # Centralized configuration parameters (Camera, SIFT, Tap, Workers...)
├── utils.py                   # Utility functions (camera helpers, I/O, drawing, normalization)
├── audio.py                   # Audio playback components (AmbientSoundPlayer, ZoneAudioPlayer)
├── gesture_detection.py       # Movement filters and gesture analysis
├── pose_detector.py           # Hand pose detection classes (Combined/Enhanced detectors)
├── sift_detector.py           # SIFT-based template detection and tracking (SIFTModelDetectorMP)
├── interaction_policy.py      # Zone-based interaction logic (InteractionPolicy2D)
├── workers.py                 # Background worker threads (PoseWorker, SIFTWorker, AudioWorker)
├── simple_camio.py            # Main application entry point and UI loop
├── simple_camio_2d.py         # Legacy compatibility layer
├── simple_camio_mp.py         # Legacy compatibility layer
└── models/                    # Map configurations and assets (JSON, images, audio)
```

## Top-level Flow

1. `simple_camio.py` loads a map model JSON and initializes components via `initialize_system()`.
2. Camera is configured via `setup_camera()`.
3. Background workers are created with `create_worker_threads()`:
   - `PoseWorker` processes (frame, homography) tuples and updates latest pose/gesture results.
   - `SIFTWorker` processes grayscale frames: validates tracking and (re-)detects homography.
   - `AudioWorker` handles all audio commands asynchronously via an internal queue.
4. The main loop (`run_main_loop`) captures frames, feeds worker queues, reads pose results, draws overlays, processes gestures into audio commands, and handles keyboard input.
5. `cleanup()` performs a graceful shutdown: stop workers, pause ambient sounds, release camera.

## Module Descriptions

### `config.py`
Centralized configuration module. Main configuration classes (examples):
- `CameraConfig` (DEFAULT_WIDTH, DEFAULT_HEIGHT, BUFFER_SIZE, POSE_PROCESSING_SCALE)
- `MovementFilterConfig` (smoothing and buffer sizes)
- `GestureDetectorConfig` (dwell thresholds, history lengths)
- `TapDetectionConfig` (comprehensive tap detection thresholds and adaptive scaling)
- `InteractionConfig` (zone filter size, Z threshold)
- `SIFTConfig` (SIFT/ORB params, matching thresholds, REDETECT_INTERVAL, MIN_TRACKING_QUALITY)
- `MediaPipeConfig` (model complexity, confidence thresholds, max hands)
- `AudioConfig` (ambient volumes)
- `UIConfig` (colors, font sizes, flash frames)
- `WorkerConfig` (queue sizes, timeouts, retry attempts, shutdown timeout)

Refer to `config.py` for full parameter names and tuned defaults.

### `utils.py`
Utility helpers used throughout the system. Notable functions:
- Camera helpers: `list_camera_ports()`, `select_camera_port()`
- Map I/O: `load_map_parameters()`
- Drawing helpers: `draw_rectangle_on_image()`, `draw_rectangle_from_points()`
- Gesture helpers: `is_gesture_valid()`, `normalize_gesture_location()`
- Misc helpers: color utilities, small math helpers used by detectors

### `audio.py`
Audio playback components:
- `AmbientSoundPlayer`: Looping/ambient sound player (heartbeat, crickets). Methods: `play_sound()`, `pause_sound()`, `set_volume()`.
- `ZoneAudioPlayer`: Responsible for zone-based audio interactions and controls such as `play_welcome()`, `play_goodbye()`, `convey(zone_id, gesture_status)` and an `enable_blips` toggle.

Audio is driven through `AudioWorker` to keep playback non-blocking.

### `gesture_detection.py`
Movement filtering and gesture analysis:
- `MovementFilter`/`MovementMedianFilter`: Position smoothing and robust median filtering
- `GestureDetector`: Tracks position history and classifies dwell vs moving gestures

These modules produce a canonical gesture location object used by interaction logic.

### `pose_detector.py`
Hand pose detection and tap recognition:
- `CombinedPoseDetector` (entry point used by the app): wraps MediaPipe-based tracking with enhanced tap detectors.
- Tap detection strategies combined in `TapDetectionConfig`:
  - Z-depth velocity and baselines
  - Angle-based detection (finger DIP flexion)
  - Palm-plane penetration and relative depth signals
  - A small engineered linear classifier for final tap validation
- Detectors support adaptive thresholds based on measured palm width (hand-size scaling) and multiple history buffers for robust baselines.
- The detector's `detect(frame, H, ...)` returns `(gesture_loc, gesture_status, annotated_image)` when asked to draw.

### `sift_detector.py`
SIFT-based template detection and tracking (`SIFTModelDetectorMP`):
- `detect(frame, force_redetect=False)` performs template detection and homography estimation.
- `quick_validate_position(frame, min_matches, position_threshold)` checks if current homography still matches the scene.
- Members used by workers: `H` (current homography), `requires_homography`, `last_rect_pts`, `frames_since_last_detection`, `homography_updated`.
- Uses SIFT (with ORB fallback), optional CLAHE / blur preprocessing, RANSAC/MAGSAC-style homography estimation and inlier counting.

### `interaction_policy.py`
Zone-based mapping from normalized gesture locations to zone IDs (`InteractionPolicy2D`):
- Maintains a small ring buffer to filter zone flicker
- Provides `push_gesture(gesture_loc)` which returns the resolved `zone_id` for audio playback
- Handles out-of-bounds gestures gracefully

### `workers.py`
Background workers (threaded) to keep the main loop responsive.

Audio worker:
- `AudioCommand`: Lightweight command object (type and params)
- `AudioWorker`: Thread that consumes commands from an internal queue and executes them via `ZoneAudioPlayer` and `AmbientSoundPlayer` instances.
- Supported commands include: `play_zone` (zone_id + gesture_status), `play_welcome`, `play_goodbye`, `heartbeat_play`, `heartbeat_pause`, `crickets_play`, `crickets_pause`, `toggle_blips`.
- `enqueue_command(AudioCommand)` is non-blocking and returns False if the queue is full.

Pose worker:
- `PoseWorker` consumes `(frame, H)` tuples and runs `pose_detector.detect(...)` on downscaled frames.
- Results are stored in `self.latest = (gesture_loc, gesture_status, annotated_image)` and accessed under a shared lock by the main thread.
- Uses `processing_scale` from `CameraConfig.POSE_PROCESSING_SCALE` when created.

SIFT worker:
- `SIFTWorker` consumes grayscale frames for either quick validation or full (re-)detection.
- Periodic validation uses `quick_validate_position()`; when validation fails or `requires_homography` is True it runs full detection attempts with multiple preprocessing variants.
- Provides `trigger_redetect()` to force a manual re-detection (used from keyboard handler).

## Main Application: `simple_camio.py`

Key functions and responsibilities:
- `initialize_system(model_path)`: Loads model JSON, constructs detectors and players. For `modelType == 'sift_2d_mediapipe'` it initializes:
  - `SIFTModelDetectorMP(model)`
  - `CombinedPoseDetector(model)`
  - `GestureDetector()` and `MovementMedianFilter()`
  - `InteractionPolicy2D(model)`
  - `ZoneAudioPlayer(model)` and `AmbientSoundPlayer` instances for heartbeat/crickets
- `setup_camera(cam_port)`: Configures OpenCV capture with resolution, focus and buffer hints, and attempts to set `CAP_PROP_BUFFERSIZE` when available.
- `create_worker_threads(components, stop_event)`: Creates `pose_queue` and `sift_queue`, starts `PoseWorker`, `SIFTWorker`, and `AudioWorker`, then enqueues a `play_welcome` audio command.
- `feed_worker_queues(frame, gray, workers, model_detector)`: Puts latest frames into worker queues using non-blocking semantics (drops older frames when full). For pose worker it sends `(frame, H_current)`.
- `process_gestures_and_audio(gesture_loc, gesture_status, components, last_double_tap_ts, audio_worker)`: Maps valid gestures to zones via `InteractionPolicy2D.push_gesture()` and enqueues audio commands. Implements double-tap cooldown logic using `TapDetectionConfig.DOUBLE_TAP_COOLDOWN_MAIN`.
- `draw_map_tracking(...)`, `draw_ui_overlay(...)`: Helpers to render tracking rectangle and status overlay.
- `handle_keyboard_input(...)`: Keyboard controls:
  - `q` or `ESC`: quit
  - `h`: manually trigger map re-detection (sets `model_detector.requires_homography = True` and calls `SIFTWorker.trigger_redetect()`)
  - `b`: toggle blip sounds via `AudioCommand('toggle_blips')`
- `run_main_loop(...)`: Capture, feed workers, read pose results (from `PoseWorker.latest` under lock), draw, process gestures, show image, and dispatch pyglet events.
- `cleanup(...)`: Enqueue goodbye audio, stop and join workers, pause ambient players, release camera and windows.

## Threading and Performance Notes

- Main thread: camera capture, UI rendering, event handling.
- PoseWorker: downscaled detection; returns annotated image and a canonical gesture object.
- SIFTWorker: full-resolution detection/validation and preprocessing attempts.
- AudioWorker: single-threaded audio command processing to avoid blocking I/O.
- Queues for pose and SIFT use `WorkerConfig.POSE_QUEUE_MAXSIZE` and `SIFT_QUEUE_MAXSIZE` (defaults are 1) to keep only the latest frame and avoid backlog.

## Runtime Controls and Keys

- `h` — Force map re-detection (calls `SIFTWorker.trigger_redetect()`)
- `b` — Toggle zone blip sounds
- `q` or `ESC` — Quit application

## Logging

The application uses Python's `logging` module (configured in `simple_camio.py`). Key events are logged:
- Initialization steps
- Worker start/stop and audio commands
- Gesture detections (taps, double-taps)
- Tracking status changes and detection failures
- Errors and exceptions with stack traces where appropriate

## Extending the System

- New detectors should expose the same `detect()` signature returning `(gesture_loc, gesture_status, annotated)` so `PoseWorker` and the main loop continue to work unchanged.
- Audio features are accessed via `ZoneAudioPlayer` and routed through `AudioWorker` using `AudioCommand` objects.
- Interaction logic is encapsulated by `InteractionPolicy2D` and can be replaced with minimal changes to the main loop.

## Troubleshooting (practical tips)

- If map isn't detected: check lighting, template image quality, call manual re-detect (`h`), and inspect SIFT matching thresholds in `SIFTConfig`.
- If taps aren't detected: verify pointing pose, inspect `TapDetectionConfig` parameters, enable DEBUG logs to observe detector internals.
- If performance is low: reduce `POSE_PROCESSING_SCALE`, lower camera resolution, or increase `REDETECT_INTERVAL` in `SIFTConfig`.


## Future Enhancements

- [ ] Support multiple simultaneous maps and independent SIFT trackers
- [ ] Dataset-driven tap classifier or small learned model to replace linear classifier
- [ ] Improved UI overlays with assistive debug modes
- [ ] Remote telemetry and a web configuration interface
