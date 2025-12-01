# Simple CamIO - AI Agent Instructions

## Project Overview

Simple CamIO is a **computer vision-based assistive technology** that enables vision-impaired users to explore tactile maps through hand gestures. It combines MediaPipe hand tracking, SIFT-based map detection, multi-modal tap recognition, and spatial audio feedback to create an interactive map exploration experience.

## Architecture Quick Reference

### Threading Model (Critical)
- **Main thread**: Frame coordination, gesture processing, event dispatch (`simple_camio.py`)
- **ThreadedCamera** (optional): Non-blocking camera capture in background thread
- **DisplayThread** (optional): Non-blocking cv.imshow() in background thread
- **PoseWorker**: Downscaled (0.35x) hand pose detection with tap analysis
- **SIFTWorker**: Full-resolution map tracking and homography validation
- **AudioWorker**: Non-blocking audio playback via command queue

**Key insight**: Queues are size=1 by default to avoid backlog and keep only latest frame. Never batch-process old frames.

### Data Flow
```
ThreadedCamera (optional) → Gray frame → SIFTWorker (homography H)
                         ↓
                RGB frame + H → PoseWorker → (gesture_loc, gesture_status, annotated_image)
                                           ↓
                                     InteractionPolicy2D → zone_id → AudioWorker → ZoneAudioPlayer
                                           ↓
                                DisplayThread (optional) → cv.imshow()
```

### Core Components
- **src/config.py**: ALL tunable parameters centralized at src root (50+ config classes)
- **src/core/camera_thread.py**: Background camera capture (ThreadedCamera)
- **src/core/display_thread.py**: Background display rendering (DisplayThread)
- **src/core/workers.py**: Background processing threads (Pose, SIFT, Audio)
- **src/detection/pose_detector.py**: 3 detectors (Base, Enhanced, Combined) with hand-size adaptive tap detection
- **src/detection/sift_detector.py**: SIFT/ORB-based template tracking with RANSAC homography
- **src/audio/audio.py**: Pyglet-based audio (ambient loops + zone-specific playback)
- **src/core/interaction_policy.py**: Normalized gesture → zone_id mapping with flicker filtering
- **src/ui/display.py**: Drawing functions and UI overlays

## Critical Development Patterns

### 1. Hand Size Adaptive Thresholds
ALL tap detection thresholds scale inversely with hand size (smaller hands = more sensitive):
```python
scale = max(MIN_SCALE_FACTOR, min(MAX_SCALE_FACTOR, REFERENCE_PALM_WIDTH / palm_width))
threshold_scaled = base_threshold * scale  # Smaller hand → smaller threshold
```
When tuning detection in `TapDetectionConfig`, always consider reference size is 180px at close range.

### 2. Configuration Changes
**Never hardcode values in detector classes.** Always add to `src/config.py`:
```python
class TapDetectionConfig:
    TAP_MIN_DURATION = 0.05  # Centralized, documented
```
Then import: `from src.config import TapDetectionConfig`

Available config classes: `CameraConfig` (includes threading options), `MovementFilterConfig`, `GestureDetectorConfig`, `TapDetectionConfig`, `InteractionConfig`, `SIFTConfig`, `MediaPipeConfig`, `AudioConfig`, `UIConfig`, `WorkerConfig`

**Performance Tuning:**
- `CameraConfig.USE_THREADED_CAPTURE` - Enable non-blocking camera capture (default: True)
- `CameraConfig.USE_THREADED_DISPLAY` - Enable non-blocking display (default: True)
- `CameraConfig.DISPLAY_FRAME_SKIP` - Display every Nth frame (default: 4)
- `CameraConfig.POSE_PROCESSING_SCALE` - Pose detection scale (default: 0.35)

**Audio Configuration:**
- `AudioConfig.HEARTBEAT_VOLUME` - Volume for heartbeat ambient sound (default: 0.05)
- `AudioConfig.PLAY_DESCRIPTION_ONCE` - If True: play map description only once (first hand). If False: play every time hand appears to support multiple users (default: False)

### 3. Worker Communication Pattern
```python
# Enqueue (non-blocking, drop if full)
worker.queue.put_nowait((frame, H))  

# Read latest result (thread-safe)
with worker.lock:
    gesture_loc, status, img = worker.latest
```
Never use blocking `.put()` or `.get()` - would freeze main loop.

### 4. Tap Detection Multi-Modal Fusion
Three concurrent detection methods fused in `CombinedPoseDetector`:
- **Z-depth**: Fingertip depth change vs baseline
- **Angle-based**: DIP joint flexion angle
- **Enhanced**: Palm plane penetration, relative depth, ray velocity

A tap requires: `(base_detector OR enhanced_detector) AND tap_classifier AND rule_validation`

### 5. Data Collection for Classifier Training
Enable automatic collection of tap data for model improvement:
```python
# In config.py
class TapDetectionConfig:
    COLLECT_TAP_DATA = True  # Enable collection
    TAP_DATA_DIR = 'data/tap_dataset'  # Save location
```
Train on collected data: `python tap_classifier/train_tap_classifier.py --train-from-collected --data-dir ../data/tap_dataset`
See `tap_classifier/DATA_COLLECTION_GUIDE.md` for full workflow.

### 5. Map Model JSON Structure
```json
{
  "model": {
    "modelType": "sift_2d_mediapipe",  // Must match for initialization
    "filename": "models/UkraineMap/UkraineMap.png",  // Zone map (RGB=zone_id)
    "template_image": "models/UkraineMap/template.png",  // SIFT reference
    "hotspots": [
      {"color": [255,0,0], "audioDescription": "path/to/audio.mp3"}
    ]
  }
}
```
Color values are exact RGB matches (no tolerance). Template must show full map with clear corner features.

## Common Development Tasks

### Adding a New Tap Detection Feature
1. Add config to `TapDetectionConfig` in `config.py`
2. Add feature extraction in `_extract_classifier_features()` in `pose_detector.py`
3. Update `TapClassifier.feature_names` in `tap_classifier/tap_classifier.py`
4. Retrain: `python tap_classifier/train_tap_classifier.py --train --samples 2000 --learning-rate 0.02 --epochs 5`
5. Test manually: observe logs at DEBUG level for feature values

### Collecting Real-World Tap Data
1. Enable in `config.py`: `TapDetectionConfig.COLLECT_TAP_DATA = True`
2. Run normally: `python simple_camio.py --input1 models/UkraineMap/UkraineMap.json`
3. Data auto-saves to `data/tap_dataset/tap_data_YYYYMMDD_HHMMSS.json`
4. Train on your data: `python tap_classifier/train_tap_classifier.py --train-from-collected --data-dir ../data/tap_dataset`
5. Merge sessions (optional): `python tap_classifier/train_tap_classifier.py --merge-datasets --data-dir ../data/tap_dataset --output merged.json`
6. Model adapts to different tap styles over time

### Debugging Tap Detection Issues
```python
# In config.py, enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```
Watch for:
- `scale_factor` values (should be 0.35-1.0)
- `trigger_count` (2+ means multiple methods agree)
- `Classifier trained on successful tap` (online learning working)

### Testing New Models
```powershell
python simple_camio.py --input1 models/TestDemo/demo_map.json
```
Press `h` to force map re-detection if tracking lost.
Press `b` to toggle zone transition blips for testing audio zones.
Press `q` or `ESC` to quit.

### Performance Optimization
Check `CameraConfig.POSE_PROCESSING_SCALE` (default 0.35). Lower = faster but less accurate.
Monitor `SIFTConfig.REDETECT_INTERVAL` (150 frames default). Higher = less CPU but slower recovery from tracking loss.

## Project-Specific Conventions

### Import Order
```python
import cv2 as cv  # Always "cv" not "cv2"
import numpy as np
import mediapipe as mp
from src.config import *Config  # Configuration at src root
from src.core.utils import ...  # Core utilities
from src.detection import ...  # Detection modules
from src.audio.audio import ...  # Audio components
```

### Naming Conventions
- `H`: Always refers to 3x3 homography matrix (np.ndarray)
- `gesture_loc`: Normalized (x, y) in [0,1] or None
- `gesture_status`: String in {'pointing', 'tap', 'double_tap', None}
- `zone_id`: Integer index into hotspots list

### Coordinate Systems
- **Camera space**: Pixels (0,0) = top-left
- **Normalized space**: (0,0) = top-left, (1,1) = bottom-right (used for gesture_loc)
- **MediaPipe landmarks**: (x,y,z) with z negative = toward camera

### Thread Safety
- **PoseWorker.latest**: Protected by `PoseWorker.lock`
- **SIFTWorker.H**: Protected by `SIFTWorker.lock`
- AudioWorker is internally thread-safe (queue-based)

## Testing & Validation

### Quick Smoke Test
```powershell
# Test imports work correctly
python -c "from simple_camio_mp import PoseDetectorMP, SIFTModelDetectorMP; print('Import successful!')"

# Run with default UkraineMap (auto-detects camera)
python simple_camio.py
```

### Tap Classifier Training
```powershell
# Train on synthetic data
python tap_classifier/train_tap_classifier.py --train --samples 1000

# Evaluate trained model
python tap_classifier/train_tap_classifier.py --evaluate

# Show feature importance
python tap_classifier/train_tap_classifier.py --feature-importance

# Train with custom parameters
python tap_classifier/train_tap_classifier.py --train --samples 2000 --learning-rate 0.02 --epochs 5

# Train from collected real-world data
python tap_classifier/train_tap_classifier.py --train-from-collected --data-dir ../data/tap_dataset

# Merge multiple collection sessions
python tap_classifier/train_tap_classifier.py --merge-datasets --data-dir ../data/tap_dataset --output merged.json
```

### Running Tests
No formal test suite yet. Manual testing via:
1. Print map (models/UkraineMap/template.png)
2. Run `python simple_camio.py`
3. Point at map zones, verify audio playback
4. Test tap gestures, check console for `Double tap detected!` logs

## Integration Points

### MediaPipe Hands API
- 21 landmarks per hand (indices 0-20)
- Index finger: TIP=8, DIP=7, PIP=6, MCP=5
- Handedness: "Left" or "Right" (camera perspective)
- See: https://google.github.io/mediapipe/solutions/hands

### Pyglet Audio
- Used for `.mp3` and `.wav` playback
- `AmbientSoundPlayer`: Looping background (heartbeat, crickets)
- `ZoneAudioPlayer`: One-shot zone descriptions
- **Warning**: Pyglet 2.0+ has breaking changes; pinned to `<3.0.0`

### OpenCV SIFT/ORB
- `SIFT_N_FEATURES = 2000` (adjustable in `SIFTConfig`)
- Falls back to ORB if SIFT unavailable (patent restrictions in some builds)
- FLANN matcher with `RATIO_THRESH = 0.8` (Lowe's ratio test)

## Gotchas & Known Issues

1. **Camera buffering**: On Windows, `CAP_PROP_BUFFERSIZE` may not work. Enable `USE_THREADED_CAPTURE=True` for better performance. If latency issues occur, try different camera backend or reduce resolution.

2. **SIFT detection failures**: Requires good lighting and clear corner features on template. If map not detected, press `h` to retry or adjust `SIFT_CONTRAST_THRESHOLD` in `SIFTConfig`.

3. **Tap classifier not loading**: Ensure `models/tap_model.json` exists. Will fallback to rule-based detection with warning.

4. **Double-tap cooldown**: `DOUBLE_TAP_COOLDOWN_MAIN = 0.7s` prevents rapid re-triggering. If taps feel unresponsive, reduce in `TapDetectionConfig`.

5. **Display performance**: For smooth rendering at high FPS, enable `USE_THREADED_DISPLAY=True`. This moves cv.imshow() to background thread, allowing main loop to run at 400+ FPS.

6. **Legacy compatibility**: `simple_camio_2d.py` and `simple_camio_mp.py` are compatibility shims. Always edit the new modular files (workers.py, pose_detector.py, etc.), not the legacy files.

4. **Double-tap cooldown**: `DOUBLE_TAP_COOLDOWN_MAIN = 0.7s` prevents rapid re-triggering. If taps feel unresponsive, reduce in `TapDetectionConfig`.

5. **Display performance**: For smooth rendering at high FPS, enable `USE_THREADED_DISPLAY=True`. This moves cv.imshow() to background thread, allowing main loop to run at 400+ FPS.

6. **Legacy compatibility**: `simple_camio_2d.py` and `simple_camio_mp.py` are compatibility shims. Always edit the new modular files (workers.py, pose_detector.py, etc.), not the legacy files.

## When to Read These Files

- **Tuning detection**: `src/config.py` (all thresholds), `src/detection/pose_detector.py` (detector logic)
- **Audio issues**: `src/audio/audio.py`, `src/core/workers.py` (AudioWorker)
- **Tracking problems**: `src/detection/sift_detector.py`, `SIFTConfig` in src/config.py
- **Adding features**: `ARCHITECTURE.md` (data flow), then relevant detector/worker
- **Performance**: `CameraConfig` in src/config.py, worker queue sizes in `WorkerConfig`
- **Data collection**: `src/tap_classifier/DATA_COLLECTION_GUIDE.md`, `TapDetectionConfig.COLLECT_TAP_DATA`

## Dependency Versions (Critical)

From `requirements.txt`:
- **mediapipe**: 0.10.x (0.11+ breaks API)
- **numpy**: <1.27 (compatibility with mediapipe)
- **opencv-contrib-python**: 4.5.5+ (SIFT support)
- **pyglet**: <3.0.0 (2.0+ has breaking audio changes)

When updating dependencies, test tap detection immediately - MediaPipe landmark precision varies across versions.

## Quick Command Reference

```powershell
# Run with default map (UkraineMap)
python simple_camio.py

# Run with custom map
python simple_camio.py --input1 models/RivneMap/RivneMap.json

# Train classifier on synthetic data
python tap_classifier/train_tap_classifier.py --train --samples 1000

# Train on collected real-world data
python tap_classifier/train_tap_classifier.py --train-from-collected --data-dir ../data/tap_dataset

# Evaluate trained model
python tap_classifier/train_tap_classifier.py --evaluate

# Show feature importance
python tap_classifier/train_tap_classifier.py --feature-importance

# Merge collected datasets
python tap_classifier/train_tap_classifier.py --merge-datasets --data-dir ../data/tap_dataset --output merged.json

# Install dependencies
pip install -r requirements.txt
```

**In-app controls**: 
- `q` or `ESC` = quit
- `h` = manually re-detect map
- `b` = toggle zone transition blips

---

**Key principle**: When editing detection logic, always test with physical map and camera. Synthetic testing misses real-world hand jitter, lighting variations, and user interaction patterns.
