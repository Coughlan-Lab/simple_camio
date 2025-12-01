# Tap Classifier for Simple CamIO

## Overview

The **Tap Classifier** is a machine learning component that learns to detect taps based on the rich set of features already computed by Simple CamIO's pose detector. It uses a lightweight logistic regression model with online learning to adapt to user behavior over time.

## Features

The classifier learns from **18 engineered features** extracted from tap detection:

### Depth Features (4)
1. **zrel_depth** - Relative Z-depth of press (tip vs palm center)
2. **plane_depth** - Palm plane penetration depth
3. **ang_depth** - Angle flexion depth at DIP joint
4. **z_depth** - Absolute Z-depth from base detector

### Spatial Features (1)
5. **drift** - XY spatial drift during press (pixels)

### Velocity Features (5)
6. **vzrel** - Z-relative velocity
7. **vplane** - Plane penetration velocity
8. **vang** - Angular velocity (finger closing)
9. **vz** - Absolute Z velocity
10. **ray_vel** - Ray projection velocity (along finger direction)

### Temporal Features (1)
11. **duration** - Press duration (seconds)

### Hand Size Features (2)
12. **scale_factor** - Adaptive scaling factor based on hand distance
13. **palm_width** - Palm width in pixels

### Trigger Features (1)
14. **trigger_count** - Number of active detection triggers

### Engineered Features (4)
15. **depth_ratio** - Consistency check across depth measurements
16. **vel_consistency** - Agreement between velocity signals
17. **spatial_stability** - Inverse of drift (stable = good tap)
18. **temporal_fitness** - Gaussian fitness for optimal tap duration

## Feature Importance

Based on the trained model, the most important features are:

1. **ang_depth** (35.6%) - Finger flexion angle is the strongest indicator
2. **trigger_count** (13.1%) - Multiple concurrent triggers indicate reliable tap
3. **palm_width** (9.4%) - Hand size affects detection reliability
4. **drift** (8.3%) - Low spatial drift is critical for valid taps
5. **vang** (7.8%) - Angular velocity provides strong signal

## Performance

The classifier achieves strong performance on synthetic test data:

- **Accuracy**: 90.3%
- **Precision**: 87.8% (few false positives)
- **Recall**: 93.7% (catches most real taps)
- **F1 Score**: 90.6%

### Confusion Matrix
```
                Predicted
              Tap  Not-Tap
Actual Tap    281      19
      Not-Tap  39     261
```

## Architecture

### TapClassifier
- **Model**: Logistic regression with L2 regularization
- **Training**: Online learning via stochastic gradient descent
- **Features**: 18-dimensional feature vector
- **Output**: Probability (0-1) that input represents a valid tap

### AdaptiveTapClassifier
Extends `TapClassifier` with:
- Automatic threshold adaptation based on user patterns
- Confidence-weighted online learning
- Periodic auto-save functionality
- Personalized tap detection over time

## Usage

### Training a New Model

```powershell
# Train with default parameters (1000 samples, 10 epochs)
python tap_classifier/train_tap_classifier.py --train

# Train with custom parameters
python tap_classifier/train_tap_classifier.py --train --samples 2000 --learning-rate 0.02 --epochs 15

# Save to custom location
python tap_classifier/train_tap_classifier.py --train --model-path models/my_model.json
```

### Evaluating a Model

```powershell
# Evaluate on test data
python tap_classifier/train_tap_classifier.py --evaluate

# Evaluate with more test samples
python tap_classifier/train_tap_classifier.py --evaluate --test-samples 1000
```

### Feature Importance Analysis

```powershell
# Show which features matter most
python tap_classifier/train_tap_classifier.py --feature-importance
```

### Integration in Pose Detector

The classifier is automatically integrated into `PoseDetectorMPEnhanced`:

```python
from pose_detector import CombinedPoseDetector

# Initialize detector (classifier loaded automatically)
detector = CombinedPoseDetector(model)

# Detect taps (classifier validates automatically)
index_pos, status, img = detector.detect(frame, H, None, draw=True)

if status == 'double_tap':
    # Tap was validated by both rules and classifier
    print("Double tap detected!")
```

### Direct Classifier Usage

```python
from tap_classifier import TapClassifier

# Load trained model
classifier = TapClassifier(model_path='../models/tap_model.json')

# Extract features from pose detector state
features = extract_features_from_state(state, velocities, thresholds)

# Predict tap probability
prob = classifier.predict(features)
is_tap = prob >= 0.65  # Default threshold

print(f"Tap probability: {prob:.2%}")

# Online learning (optional)
if user_confirmed_tap:
    classifier.train(features, is_tap=True)
    classifier.save_model('models/tap_model.json')
```

## How It Works

### 1. Feature Extraction
During tap detection, the enhanced pose detector computes all 18 features based on:
- Hand landmark positions (MediaPipe)
- Temporal tracking (velocity, acceleration)
- Geometric analysis (palm plane, finger angles)
- Statistical baselines (median, noise estimates)

### 2. Classification
The classifier combines features using learned weights:

```
score = w₁×zrel_depth + w₂×plane_depth + ... + w₁₈×temporal_fitness + bias
probability = sigmoid(score) = 1 / (1 + e^(-score))
```

### 3. Validation
A tap is validated if:
- **Rule-based validation** passes (duration, drift, depth thresholds)
- **Classifier probability** ≥ 0.65 (configurable via `CLS_MIN_PROB`)

### 4. Online Learning (Optional)
When a tap is confirmed (double-tap detected):
- Features are stored during validation
- Model trains on the successful example
- Weights adapt to user's tap style
- Model auto-saves periodically

## Synthetic Training Data

The classifier is pre-trained on synthetic data that models realistic tap characteristics:

### Positive Examples (Taps)
- Depth: 0.01-0.06 units (sufficient press depth)
- Drift: 0-90 pixels (stable hand position)
- Duration: 0.05-0.35 seconds (typical tap duration)
- Velocity: Strong inward motion
- Triggers: 2-4 concurrent detectors active

### Negative Examples (Non-Taps)
Four failure modes simulated:
1. **Insufficient depth** - Grazing touch, not firm press
2. **Too much drift** - Hand moving during press
3. **Wrong duration** - Too quick (<50ms) or too long (>500ms)
4. **Low velocity** - Slow movement, not crisp tap

## Configuration

Key parameters in `config.py`:

```python
class TapDetectionConfig:
    # Classifier threshold
    CLS_MIN_PROB = 0.65  # Minimum probability for valid tap
    
    # Feature weights (pre-trained, can be overridden)
    CLS_WEIGHTS = [2.5, 1.8, 1.2, ...]  # Per-feature weights
    CLS_BIAS = -3.5  # Decision boundary bias
```

## Benefits

### 1. Robustness
- Learns complex patterns that rules might miss
- Combines multiple weak signals into strong decision
- Adapts to edge cases through online learning

### 2. Personalization
- Model adapts to individual user's tap style
- Becomes more accurate over time with use
- Handles variations in hand size, speed, pressure

### 3. Maintainability
- Feature engineering is explicit and interpretable
- Model weights show which signals matter most
- Easy to retrain with new data or adjust thresholds

### 4. Performance
- Lightweight inference (<1ms per prediction)
- No external dependencies (NumPy only)
- Minimal memory footprint (~10KB model file)

## Files

- `tap_classifier/tap_classifier.py` - Main classifier implementation
- `tap_classifier/train_tap_classifier.py` - Training and evaluation utilities
- `tap_classifier/tap_data_collector.py` - Automatic data collection from usage
- `models/tap_model.json` - Pre-trained model weights
- `tap_classifier/TAP_CLASSIFIER_README.md` - This documentation
- `tap_classifier/DATA_COLLECTION_GUIDE.md` - Guide for collecting real-world data

## Collecting Real Training Data

Simple CamIO now has built-in automatic data collection! See [DATA_COLLECTION_GUIDE.md](DATA_COLLECTION_GUIDE.md) for full details.

**Quick start:**

1. Enable in `config.py`:
   ```python
   class TapDetectionConfig:
       COLLECT_TAP_DATA = True
       TAP_DATA_DIR = 'data/tap_dataset'
   ```

2. Run normally and perform taps:
   ```powershell
   python simple_camio.py
   ```

3. Train on collected data:
   ```powershell
   python tap_classifier/train_tap_classifier.py --train-from-collected --data-dir data/tap_dataset
   ```

The system automatically collects both positive (confirmed taps) and negative (rejected gestures) examples with all 18 features, timestamps, and metadata.

## Troubleshooting

### Low Accuracy
- Increase training samples: `--samples 2000`
- More training epochs: `--epochs 20`
- Adjust learning rate: `--learning-rate 0.005`

### Too Sensitive (False Positives)
- Increase threshold: `CLS_MIN_PROB = 0.75` in `config.py`
- Train with more negative examples

### Missing Taps (False Negatives)
- Decrease threshold: `CLS_MIN_PROB = 0.55` in `config.py`
- Train with more diverse positive examples
- Collect real-world data to personalize model

### Model Not Loading
- Check file path: `models/tap_model.json` exists
- Verify JSON format is valid
- Re-train if corrupted: `python tap_classifier/train_tap_classifier.py --train`

## Future Enhancements

Potential improvements:
1. **Neural Network** - Replace logistic regression with small MLP
2. **Real-time Adaptation** - Continuous online learning during use
3. **Multi-user Models** - Separate models for different users
4. **Ensemble Methods** - Combine multiple classifiers
5. **Active Learning** - Request user feedback on uncertain cases

## References

- MediaPipe Hand Tracking: https://google.github.io/mediapipe/solutions/hands
- Logistic Regression: https://en.wikipedia.org/wiki/Logistic_regression
- Online Learning: https://en.wikipedia.org/wiki/Online_machine_learning

## License

Part of Simple CamIO project. See main README for license information.

