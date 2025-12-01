# Tap Data Collection and Training Guide

This guide explains how to use the automatic tap data collection feature to improve the tap classifier with real-world data from your usage.

## Overview

Simple CamIO can automatically collect tap detection data while you use the program. This data includes:
- **Positive examples**: Confirmed taps that triggered actions
- **Negative examples**: Rejected gestures that didn't qualify as taps
- **Feature vectors**: All detection signals (depth, velocity, duration, etc.)
- **Metadata**: Context like hand size, detector type, rejection reasons

By training the classifier on your collected data, you can significantly improve tap detection accuracy for your specific usage patterns.

## Quick Start

### 1. Enable Data Collection

Edit `config.py` and set:

```python
class TapDetectionConfig:
    # ... other settings ...

    COLLECT_TAP_DATA = True  # Enable data collection
    TAP_DATA_DIR = '../data/tap_dataset'  # Where to save data
    MAX_COLLECTED_SAMPLES = 10000  # Max samples per session
```

### 2. Collect Data

Run Simple CamIO normally:

```powershell
python simple_camio.py
```

Use the program as you normally would:
- Perform taps on different map zones
- Try various tap speeds and pressures
- Include some intentional "bad" taps (too fast, with drift, etc.)
- Use different hand distances from the camera
- Try taps while moving your hand slightly

**The more diverse your taps, the better the trained model will be!**

### 3. Review Collected Data

When you exit the program, data is automatically saved to:
```
data/tap_dataset/tap_data_YYYYMMDD_HHMMSS.json
```

The console will show:
```
Saving 247 collected tap samples...
  Positive: 156, Negative: 91
Tap data saved to data/tap_dataset/tap_data_20251027_143022.json
```

### 4. Train on Your Data

Train on your collected data from the project root:

```powershell
python tap_classifier/train_tap_classifier.py --train-from-collected --data-dir data/tap_dataset
```

This will:
- Load all collected data files
- Train the classifier on your real-world examples
- Save the trained model to `models/tap_model.json`
- Display performance metrics

### 5. Use Your Trained Model

The next time you run Simple CamIO, it will automatically use your trained model for improved tap detection!

## Advanced Usage

### Merge Multiple Sessions

If you've collected data across multiple sessions:

```powershell
python tap_classifier/train_tap_classifier.py --merge-datasets --data-dir data/tap_dataset --output merged_data.json
```

Then train on the merged dataset:

```powershell
python tap_classifier/train_tap_classifier.py --train-from-collected --data-dir data/tap_dataset --epochs 15
```

### Evaluate Model Performance

Check how well your trained model performs:

```powershell
python tap_classifier/train_tap_classifier.py --evaluate --model-path models/tap_model.json
```

### View Feature Importance

See which features are most important for tap detection:

```powershell
python tap_classifier/train_tap_classifier.py --feature-importance
```

### Combine Synthetic and Real Data

For best results, you can train on both synthetic and collected data:

```powershell
# First train on synthetic data
python tap_classifier/train_tap_classifier.py --train --samples 2000 --epochs 10

# Then fine-tune on your collected data
python tap_classifier/train_tap_classifier.py --train-from-collected --learning-rate 0.005 --epochs 5
```

## Data Collection Details

### What Gets Collected

Each sample includes 18 features:

1. **Depth features**: `zrel_depth`, `plane_depth`, `ang_depth`, `z_depth`
2. **Spatial features**: `drift` (XY movement during tap)
3. **Velocity features**: `vzrel`, `vplane`, `vang`, `vz`, `ray_vel`
4. **Temporal features**: `duration`
5. **Scaling features**: `scale_factor`, `palm_width`
6. **Context features**: `trigger_count`
7. **Engineered features**: `depth_ratio`, `vel_consistency`, `spatial_stability`, `temporal_fitness`

### Positive vs Negative Examples

**Positive examples** are collected when:
- A tap passes all validation checks
- Double-tap is confirmed
- Classifier confidence is high

**Negative examples** are collected when:
- Tap is rejected due to insufficient depth
- Excessive XY drift detected
- Duration outside valid range
- Classifier rejects the gesture

### Privacy and Data

All collected data is stored **locally** on your machine. No data is sent anywhere.

Data files contain:
- Numerical feature vectors
- Boolean labels (tap/not-tap)
- Timestamps
- Metadata (detector type, rejection reason)

**No camera images, personal information, or map content is stored.**

## Tips for Collecting Quality Data

### Variety is Key

Collect data that covers:
- ✅ Fast taps and slow taps
- ✅ Light taps and firm taps
- ✅ Taps at different depths (close/far from camera)
- ✅ Taps with both left and right hands
- ✅ Taps while hand is perfectly still
- ✅ Taps while hand is moving slightly
- ✅ Intentional "mistakes" (too fast, with drift)

### Aim for Balance

Try to collect roughly equal numbers of:
- Positive examples (confirmed taps)
- Negative examples (rejected gestures)

If you're getting too many positives, intentionally perform some bad gestures. If too many negatives, adjust your tap technique.

### Multiple Sessions

Collecting data across multiple sessions (different lighting, different times of day, different fatigue levels) helps the model generalize better.

### Monitor the Console

Watch the console output to see:
```
Collected positive sample: total=45, positive=28
Collected negative sample: total=46, negative=18
```

This helps you track balance between positive and negative examples.

## Training Parameters

### Learning Rate

- **Default**: 0.01
- **Higher** (0.02-0.05): Faster learning, may be unstable
- **Lower** (0.001-0.005): Slower but more stable, good for fine-tuning

### Epochs

- **Default**: 10
- **More epochs**: Better fit to training data, risk of overfitting
- **Fewer epochs**: Faster training, may not fully learn patterns

### Example Commands

```powershell
# Conservative training (stable, safe)
python tap_classifier/train_tap_classifier.py --train-from-collected --learning-rate 0.005 --epochs 20

# Aggressive training (fast, may overfit)
python tap_classifier/train_tap_classifier.py --train-from-collected --learning-rate 0.02 --epochs 5

# Balanced (recommended)
python tap_classifier/train_tap_classifier.py --train-from-collected --learning-rate 0.01 --epochs 10
```

## Troubleshooting

### "No tap data files found"

Make sure:
1. `COLLECT_TAP_DATA = True` in config.py
2. You actually performed taps during the session
3. The program exited cleanly (not killed forcefully)
4. Check the `data/tap_dataset` directory exists

### "No valid samples found"

The collected JSON files may be corrupted. Try:
1. Deleting old data files and collecting fresh data
2. Checking file permissions on the data directory

### Model performs worse after training

This can happen if:
- Not enough training data (collect more samples)
- Training data is too specific (collect more variety)
- Too many epochs (reduce to 5-10)

Try training on synthetic data first, then fine-tune on collected data with lower learning rate.

### Data collection seems slow

Data collection has negligible performance impact (<1ms per frame). If the program feels slow:
- It's likely unrelated to data collection
- Check camera resolution and `POSE_PROCESSING_SCALE` in config
- Try disabling data collection to verify

## File Formats

### JSON Structure

```json
{
  "metadata": {
    "session_id": "20251027_143022",
    "num_positive": 156,
    "num_negative": 91,
    "total_samples": 247
  },
  "samples": [
    {
      "features": [0.012, 0.015, 12.5, ...],
      "label": true,
      "timestamp": "2025-10-27T14:30:45.123456",
      "metadata": {
        "detector": "enhanced",
        "zrel_depth": 0.012
      }
    }
  ]
}
```

### CSV Export

You can also export to CSV for analysis in other tools:

```python
from tap_classifier.tap_data_collector import TapDataCollector

collector = TapDataCollector()
collector.load_from_json('data/tap_dataset/tap_data_20251027_143022.json')
collector.save_csv('tap_data.csv')
```

## Configuration Reference

All settings in `config.py` under `TapDetectionConfig`:

```python
# Enable/disable collection
COLLECT_TAP_DATA = False  # Set to True to enable

# Output directory
TAP_DATA_DIR = 'data/tap_dataset'

# Maximum samples per session (prevents disk overflow)
MAX_COLLECTED_SAMPLES = 10000
```

## Integration Details

### Base Detector Collection

The base `PoseDetectorMP` collects features from:
- Z-depth tap detection
- Angle-based tap detection
- Basic timing and spatial data

### Enhanced Detector Collection

The `PoseDetectorMPEnhanced` collects additional features:
- Palm plane penetration
- Relative depth tracking
- Ray projection velocity
- Motion stability metrics
- Classifier confidence scores

### CombinedPoseDetector

When using `CombinedPoseDetector` (default), data is collected from whichever detector confirms the tap. This provides the most comprehensive feature set.

## Best Practices

1. **Start Fresh**: Delete old models before training on new data
2. **Incremental Training**: Train on synthetic → train on collected → fine-tune
3. **Validate Results**: Always run `--evaluate` after training
4. **Version Models**: Save dated backups of trained models
5. **Monitor Accuracy**: Track metrics across training sessions
6. **Diverse Data**: Collect in various conditions and scenarios

## See Also

- `tap_classifier/TAP_CLASSIFIER_README.md` - Classifier architecture details
- `ARCHITECTURE.md` - System architecture and data flow
- `config.py` - All configuration options
- `.github/copilot-instructions.md` - Development guidelines
