# Simple CamIO - Refactored Architecture

## Overview

This document describes the refactored architecture of Simple CamIO, an interactive map system using hand tracking, robust tap detection, SIFT-based template tracking, and asynchronous audio playback.

## Project Structure

```
simple_camio/
├── simple_camio.py                  # Main application entry point and UI loop
├── requirements.txt                 # Python dependencies
├── README.md                        # Project overview and quick start
├── ARCHITECTURE.md                  # This file - architecture documentation
├── LAUNCH_GUIDE.md                  # Detailed setup and launch instructions
│
├── src/                            # Source code package
│   ├── __init__.py
│   ├── config.py                   # Centralized configuration
│   │
│   ├── core/                       # Core system components
│   │   ├── __init__.py
│   │   ├── utils.py               # Utility functions
│   │   ├── workers.py             # Background worker threads (Pose, SIFT, Audio)
│   │   ├── interaction_policy.py  # Zone-based interaction logic
│   │   ├── camera_thread.py       # Non-blocking camera capture thread
│   │   └── display_thread.py      # Non-blocking display rendering thread
│   │
│   ├── detection/                 # Detection & tracking modules
│   │   ├── __init__.py
│   │   ├── pose_detector.py       # Hand pose detection with tap recognition
│   │   ├── sift_detector.py       # SIFT-based template tracking
│   │   └── gesture_detection.py   # Movement filtering and gesture analysis
│   │
│   ├── audio/                     # Audio playback
│   │   ├── __init__.py
│   │   └── audio.py               # Ambient and zone audio players
│   │
│   ├── ui/                        # UI & display components
│   │   ├── __init__.py
│   │   └── display.py             # Drawing and overlay rendering
│   │
│   └── tap_classifier/            # ML tap classifier package
│       ├── __init__.py
│       ├── tap_classifier.py          # Classifier implementation
│       ├── train_tap_classifier.py    # Training script
│       ├── test_tap_classifier.py     # Testing utilities
│       ├── tap_data_collector.py      # Data collection for training
│       ├── TAP_CLASSIFIER_README.md   # Classifier documentation
│       └── DATA_COLLECTION_GUIDE.md   # Guide for collecting training data
│
├── models/                        # Map configurations & assets
│   ├── tap_model.json            # Trained tap classifier model
│   ├── UkraineMap/               # Example map: Ukraine
│   ├── RivneMap/                 # Example map: Rivne
│   └── TestDemo/                 # Test/demo map
│
├── data/                         # Runtime data
│   └── tap_dataset/              # Collected tap training data
│
├── tests/                        # Unit tests (future)
│   └── __init__.py
│
└── legacy/                       # Legacy compatibility files
    ├── simple_camio_2d.py       # Old 2D compatibility layer
    └── simple_camio_mp.py       # Old MediaPipe compatibility layer
```

## Top-level Flow

1. `simple_camio.py` loads a map model JSON and initializes components via `initialize_system()`.
2. Camera is configured via `src.ui.display.setup_camera()` (optionally wrapped in `ThreadedCamera`).
3. Background workers are created with `create_worker_threads()`:
   - `PoseWorker` processes (frame, homography) tuples and updates latest pose/gesture results.
   - `SIFTWorker` processes grayscale frames: validates tracking and (re-)detects homography.
   - `AudioWorker` handles all audio commands asynchronously via an internal queue.
4. The main loop (`run_main_loop`) captures frames (optionally via `ThreadedCamera`), feeds worker queues, reads pose results, draws overlays using `src.ui.display` functions, processes gestures into audio commands, displays frames (optionally via `DisplayThread`), and handles keyboard input.
5. Helper functions break down the main loop:
   - `initialize_display()` - Sets up display system (threaded or traditional)
   - `capture_and_preprocess()` - Captures and converts frames
   - `get_pose_results()` - Retrieves latest pose data from worker
   - `process_map_detection()` - Handles map tracking and gesture processing
   - `handle_display_and_input()` - Manages display and keyboard input
   - `update_performance_stats()` - Logs performance metrics
6. `cleanup()` performs a graceful shutdown: stop workers, stop display thread, pause ambient sounds, release camera.

## Module Descriptions

### `src/config.py` - Configuration (Root Level)

Centralized configuration module at the src root for easy importing.

Main configuration classes:
- `CameraConfig` - Camera settings (resolution, buffer, processing scale, threaded capture/display)
- `MovementFilterConfig` - Movement smoothing parameters
- `GestureDetectorConfig` - Gesture detection thresholds
- `TapDetectionConfig` - Comprehensive tap detection parameters
- `InteractionConfig` - Zone filtering and interaction settings
- `SIFTConfig` - SIFT/ORB feature detection and matching parameters
- `MediaPipeConfig` - MediaPipe hand tracking configuration
- `AudioConfig` - Audio volume and playback settings
- `UIConfig` - Display colors, fonts, and UI elements
- `WorkerConfig` - Worker thread queue sizes and timeouts

### `src/core/` - Core System Components

#### `utils.py`
Utility helpers used throughout the system:
- Camera helpers: `list_camera_ports()`, `select_camera_port()`
- Map I/O: `load_map_parameters()`
- Drawing helpers: `draw_rectangle_on_image()`, `draw_rectangle_from_points()`
- Gesture helpers: `is_gesture_valid()`, `normalize_gesture_location()`
- Misc: color utilities and math helpers

#### `workers.py`
Background worker threads for asynchronous processing:
- `AudioCommand` - Command objects for audio operations
- `AudioWorker` - Non-blocking audio playback thread
- `PoseWorker` - Hand pose detection worker (downscaled frames)
- `SIFTWorker` - Template tracking and homography validation

#### `camera_thread.py`
Non-blocking camera capture:
- `ThreadedCamera` - Background thread for camera frame capture
- Eliminates camera I/O blocking from main loop
- Configurable via `CameraConfig.USE_THREADED_CAPTURE`

#### `display_thread.py`
Non-blocking display rendering:
- `DisplayThread` - Background thread for cv.imshow() operations
- Queues frames for display without blocking main processing
- Handles keyboard input asynchronously
- Configurable via `CameraConfig.USE_THREADED_DISPLAY`

#### `interaction_policy.py`
Zone-based mapping from gestures to map zones:
- `InteractionPolicy2D` - Maps normalized gesture locations to zone IDs with flicker filtering

### `src/detection/` - Detection & Tracking

#### `pose_detector.py`
Hand pose detection and tap recognition:
- `CombinedPoseDetector` - Main detector combining MediaPipe tracking with multi-modal tap detection
- Supports Z-depth, angle-based, and enhanced palm-plane tap detection
- Hand-size adaptive thresholds for robust detection
- Integrated with tap classifier and data collector

#### `sift_detector.py`
SIFT-based template detection and tracking:
- `SIFTModelDetectorMP` - Detects and tracks physical maps using SIFT features
- Homography estimation with RANSAC
- Periodic validation and automatic re-detection
- CLAHE preprocessing and multiple detection strategies

#### `gesture_detection.py`
Movement filtering and gesture analysis:
- `MovementFilter` / `MovementMedianFilter` - Position smoothing with median filtering
- `GestureDetector` - Classifies dwell vs moving gestures from position history

### `src/audio/` - Audio Playback

#### `audio.py`
Audio playback components:
- `AmbientSoundPlayer` - Looping background audio (heartbeat, crickets)
- `ZoneAudioPlayer` - Zone-based audio descriptions with welcome/goodbye messages

### `src/ui/` - User Interface

#### `display.py`
Display and rendering functions:
- `setup_camera()` - Camera initialization and configuration
- `draw_map_tracking()` - Renders tracking rectangles with flash effects
- `draw_ui_overlay()` - Draws status text, FPS counter, and gesture info

### `src/tap_classifier/` - Machine Learning Tap Detection

ML-based tap classifier for improved detection accuracy:
- `TapClassifier` - Linear classifier for tap validation
- `train_tap_classifier.py` - Training script with synthetic and real data support
- `tap_data_collector.py` - Automatic data collection during runtime
- Supports training from collected real-world usage data
- See `TAP_CLASSIFIER_README.md` and `DATA_COLLECTION_GUIDE.md` for details

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

- **Main thread**: Camera capture (or reading from ThreadedCamera), UI rendering (or queuing to DisplayThread), event handling.
- **ThreadedCamera** (optional): Background camera capture to eliminate I/O blocking from main loop. Enabled via `CameraConfig.USE_THREADED_CAPTURE`.
- **DisplayThread** (optional): Background display rendering to eliminate cv.imshow() blocking from main loop. Enabled via `CameraConfig.USE_THREADED_DISPLAY`.
- **PoseWorker**: Downscaled detection; returns annotated image and a canonical gesture object.
- **SIFTWorker**: Full-resolution detection/validation and preprocessing attempts.
- **AudioWorker**: Single-threaded audio command processing to avoid blocking I/O.
- Queues for pose and SIFT use `WorkerConfig.POSE_QUEUE_MAXSIZE` and `SIFT_QUEUE_MAXSIZE` (defaults are 1) to keep only the latest frame and avoid backlog.
- **Frame skipping**: `CameraConfig.DISPLAY_FRAME_SKIP` controls how often frames are displayed (less critical when using DisplayThread).

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
