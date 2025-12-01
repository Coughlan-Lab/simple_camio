# Simple CamIO - Launch Guide

## How to Run the Application

The refactored code is **100% backward compatible** with the previous version. You can launch it exactly the same way as before.

### Method 1: Using Default Map (Recommended)

```powershell
python simple_camio.py
```

This will load the default map: `models/UkraineMap/UkraineMap.json`

### Method 2: Specifying a Custom Map

```powershell
python simple_camio.py --input1 models/RivneMap/RivneMap.json
```

Or with the TestDemo:

```powershell
python simple_camio.py --input1 models/TestDemo/demo_map.json
```

### Method 3: Using the Executable (if built)

```powershell
simple_camio.exe --input1 models/UkraineMap/UkraineMap.json
```

## User Controls (Same as Before)

Once the application starts:

- **`q` or `ESC`**: Quit the application
- **`h`**: Manually trigger map re-detection (if tracking is lost)
- **`b`**: Toggle blip sounds on/off when moving between zones

## What's Different (For Developers)

While the launch is identical, the code structure has changed significantly:

### Old Structure (Before Refactoring)
```
simple_camio.py        (1000+ lines, everything mixed together)
simple_camio_2d.py     (200+ lines, interaction and audio)
simple_camio_mp.py     (800+ lines, pose detection and SIFT)
```

### New Structure (After Refactoring)
```
simple_camio.py           # Main entry point (~350 lines, clean and organized)
├── config.py             # All configuration parameters
├── utils.py              # Utility functions
├── audio.py              # Audio components
├── gesture_detection.py  # Movement filters and gesture detection
├── pose_detector.py      # MediaPipe hand tracking
├── sift_detector.py      # SIFT-based map tracking
├── interaction_policy.py # Zone interaction logic
└── workers.py            # Background worker threads
```

### Backward Compatibility

The old files (`simple_camio_2d.py` and `simple_camio_mp.py`) still work! They now act as **compatibility layers** that import from the new modules:

```python
# Old code still works!
from simple_camio_2d import InteractionPolicy2D, CamIOPlayer2D
from simple_camio_mp import PoseDetectorMP, SIFTModelDetectorMP

# These are now imported from the new modular structure behind the scenes
```

## Troubleshooting

### "Module not found" errors

Make sure all the new files are in the same directory:
- config.py
- utils.py
- audio.py
- gesture_detection.py
- pose_detector.py
- sift_detector.py
- interaction_policy.py
- workers.py

### Camera not detected

The application will automatically detect available cameras. If multiple cameras are found, you'll be prompted to select one.

### Map not tracking

1. Press `h` to manually trigger re-detection
2. Ensure good lighting conditions
3. Check that the template image matches your physical map

## Configuration Changes

You can now easily adjust parameters without digging through code:

**Open `config.py`** and modify values in the configuration classes:

```python
# Example: Make tap detection more sensitive
class TapDetectionConfig:
    TAP_MIN_DURATION = 0.03  # Change from 0.05
    TAP_MAX_DURATION = 0.60  # Change from 0.50
```

**Enable debug logging:**

```python
# In config.py
LOG_LEVEL = logging.DEBUG  # Change from logging.INFO
```

## Requirements

Make sure you have all dependencies installed:

```powershell
pip install -r requirements.txt
```

Required packages (from `requirements.txt`):
- `mediapipe>=0.10.0,<0.11.0`
- `numpy>=1.19.5,<1.27`
- `scipy>=1.5.4,<2.0`
- `opencv-contrib-python>=4.5.5.64,<5.0.0`
- `pyglet>=1.5.0,<3.0.0`

## Testing the Installation

Quick test to verify everything works:

```powershell
python -c "from simple_camio_mp import PoseDetectorMP, SIFTModelDetectorMP; print('Import successful!')"
```

If you see "Import successful!" without errors, you're ready to run!

## Summary

✅ **Launch command is identical to before**
✅ **All functionality preserved**  
✅ **Code is now modular and maintainable**
✅ **Old imports still work**
✅ **Configuration is centralized**
✅ **Better logging and error handling**

Just run:
```powershell
python simple_camio.py
```

And everything will work exactly as it did before, but with cleaner, more maintainable code!

