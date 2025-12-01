"""
Machine Learning Tap Classifier for Simple CamIO.

This module implements a simple yet effective classifier that learns to detect taps
from the rich set of features already computed by the pose detector. It uses a
lightweight online learning approach that can adapt to user behavior over time.

The classifier learns from:
- Z-depth features (fingertip depth changes)
- Angle-based features (finger flexion at DIP joint)
- Palm plane features (penetration analysis)
- Relative depth features (tip vs palm center)
- Velocity features (Z, angle, plane, ray projection)
- Spatial features (XY drift during press)
- Temporal features (press duration)
- Hand size features (adaptive scaling)

ARCHITECTURE:
- Uses a simple logistic regression model with feature engineering
- Online learning allows model to adapt to individual users
- Lightweight enough to run in real-time on each frame
- Saves/loads trained weights for persistence across sessions

USAGE:
    from tap_classifier import TapClassifier

    classifier = TapClassifier()

    # Extract features from pose detector state
    features = classifier.extract_features(state, thresholds, velocities)

    # Predict tap probability
    tap_probability = classifier.predict(features)

    # Train on labeled examples (online learning)
    classifier.train(features, is_tap=True)

    # Save/load model
    classifier.save_model('tap_model.json')
    classifier.load_model('tap_model.json')
"""

import numpy as np
import json
import logging
from pathlib import Path
from collections import deque
from src.config import TapDetectionConfig

logger = logging.getLogger(__name__)


class TapClassifier:
    """
    Online learning classifier for tap detection.

    Uses logistic regression with feature engineering to detect taps based on
    multiple signals from the pose detector. Supports online learning to adapt
    to individual users over time.
    """

    def __init__(self, model_path=None, learning_rate=0.01):
        """
        Initialize the tap classifier.

        Args:
            model_path (str, optional): Path to load pre-trained model
            learning_rate (float): Learning rate for online updates
        """
        self.learning_rate = learning_rate

        # Feature names for interpretability
        self.feature_names = [
            'zrel_depth',           # Relative Z-depth of press
            'plane_depth',          # Palm plane penetration depth
            'ang_depth',            # Angle flexion depth
            'z_depth',              # Absolute Z-depth (from base detector)
            'drift',                # XY spatial drift during press
            'vzrel',                # Z-relative velocity
            'vplane',               # Plane velocity
            'vang',                 # Angular velocity
            'vz',                   # Absolute Z velocity
            'ray_vel',              # Ray projection velocity
            'duration',             # Press duration
            'scale_factor',         # Hand size scaling factor
            'palm_width',           # Palm width in pixels
            'trigger_count',        # Number of active triggers
            'depth_ratio',          # zrel_depth / (plane_depth + eps)
            'vel_consistency',      # Velocity signal agreement
            'spatial_stability',    # Low drift indicator
            'temporal_fitness'      # Duration within expected range
        ]

        # Initialize weights (default to reasonable starting values)
        self.num_features = len(self.feature_names)
        self.weights = np.array([
            2.5,    # zrel_depth (strong indicator)
            1.8,    # plane_depth (strong indicator)
            1.2,    # ang_depth (moderate indicator)
            1.5,    # z_depth (moderate indicator)
            -1.2,   # drift (negative - high drift = not tap)
            -0.8,   # vzrel (negative velocity = inward motion = tap)
            -0.6,   # vplane (similar to vzrel)
            1.0,    # vang (positive = closing = tap)
            -0.7,   # vz (negative = inward = tap)
            1.2,    # ray_vel (positive = inward along finger = tap)
            0.8,    # duration (moderate positive)
            0.5,    # scale_factor (slight preference for larger hands)
            0.3,    # palm_width (slight preference)
            1.5,    # trigger_count (more triggers = more confident)
            0.9,    # depth_ratio (consistency check)
            1.1,    # vel_consistency (velocities agree = tap)
            0.7,    # spatial_stability (low drift = tap)
            0.8     # temporal_fitness (good duration = tap)
        ], dtype=float)

        self.bias = -3.5  # Decision boundary bias

        # Training statistics
        self.num_updates = 0
        self.training_history = deque(maxlen=100)  # Track recent predictions

        # Performance metrics
        self.true_positives = 0
        self.false_positives = 0
        self.true_negatives = 0
        self.false_negatives = 0

        # Load pre-trained model if provided
        if model_path and Path(model_path).exists():
            self.load_model(model_path)

        logger.info(f"Initialized TapClassifier with {self.num_features} features")

    def extract_features(self, base_state=None, enhanced_state=None,
                        base_velocities=None, enhanced_velocities=None,
                        thresholds=None, triggers=None):
        """
        Extract features from pose detector state.

        This method combines features from both base and enhanced detectors
        to create a comprehensive feature vector for classification.

        Args:
            base_state (dict, optional): Base detector tap state
            enhanced_state (dict, optional): Enhanced detector tap state
            base_velocities (dict, optional): Base detector velocities
            enhanced_velocities (dict, optional): Enhanced detector velocities
            thresholds (dict, optional): Scaled thresholds
            triggers (dict, optional): Trigger states

        Returns:
            numpy.ndarray: Feature vector of shape (num_features,)
        """
        features = np.zeros(self.num_features, dtype=float)

        # Extract depth features
        if enhanced_state is not None:
            features[0] = enhanced_state.get('peak_zrel_depth', 0.0)
            features[1] = enhanced_state.get('peak_plane_depth', 0.0)
            features[2] = enhanced_state.get('peak_ang_depth', 0.0)

        if base_state is not None:
            features[3] = base_state.get('peak_depth', 0.0)
            if enhanced_state is None:
                # Use base angle depth if enhanced not available
                features[2] = base_state.get('peak_angle_depth', 0.0)

        # Extract spatial drift
        if enhanced_state is not None and 'press_start_xy' in enhanced_state:
            # Compute drift from stored press start position
            # Note: actual current position needs to be passed separately
            # For now, we'll compute from available data
            pass  # Will be set by caller
        elif base_state is not None and 'press_start_xy' in base_state:
            pass  # Will be set by caller

        # Extract velocity features
        if enhanced_velocities is not None:
            features[5] = abs(enhanced_velocities.get('vzrel', 0.0))
            features[6] = abs(enhanced_velocities.get('vplane', 0.0))
            features[7] = enhanced_velocities.get('vang', 0.0)
            features[9] = enhanced_velocities.get('ray_in_v', 0.0)

        if base_velocities is not None:
            features[8] = abs(base_velocities.get('vz', 0.0))
            if enhanced_velocities is None:
                features[7] = base_velocities.get('vang', 0.0)

        # Extract temporal features
        if enhanced_state is not None and 'press_start' in enhanced_state:
            import time
            features[10] = time.time() - enhanced_state['press_start']
        elif base_state is not None and 'press_start' in base_state:
            import time
            features[10] = time.time() - base_state['press_start']

        # Extract scaling features
        if thresholds is not None:
            features[11] = thresholds.get('scale_factor', 1.0)
            features[12] = thresholds.get('palm_width', 180.0)

        # Extract trigger count
        if triggers is not None:
            features[13] = triggers.get('trigger_count', 0)

        # Compute engineered features
        features[14] = self._compute_depth_ratio(features[0], features[1])
        features[15] = self._compute_velocity_consistency(features[5:10])
        features[16] = self._compute_spatial_stability(features[4])
        features[17] = self._compute_temporal_fitness(features[10])

        return features

    def _compute_depth_ratio(self, zrel_depth, plane_depth):
        """
        Compute ratio of Z-relative depth to plane depth.

        Good taps should have consistent depth across different measurements.

        Args:
            zrel_depth (float): Z-relative depth
            plane_depth (float): Plane penetration depth

        Returns:
            float: Depth ratio (clamped to reasonable range)
        """
        if plane_depth > 1e-6:
            ratio = zrel_depth / (plane_depth + 1e-6)
            return float(np.clip(ratio, 0.0, 5.0))
        return 0.0

    def _compute_velocity_consistency(self, velocities):
        """
        Compute consistency score across velocity signals.

        Good taps should have consistent velocity directions across measurements.

        Args:
            velocities (numpy.ndarray): Array of velocity features

        Returns:
            float: Consistency score (0-1)
        """
        # Count how many velocities indicate tap (negative for Z velocities, positive for angle)
        vzrel, vplane, vang, vz, ray_vel = velocities

        # Normalize to tap indicators: negative Z velocities → positive, positive angle → positive
        indicators = [
            -vzrel,   # Negative Z-rel → positive indicator
            -vplane,  # Negative plane → positive indicator
            vang,     # Positive angle → positive indicator
            -vz,      # Negative Z → positive indicator
            ray_vel   # Positive ray → positive indicator
        ]

        # Compute agreement: all positive = consistent tap, mixed = inconsistent
        positive_count = sum(1 for x in indicators if x > 0.05)
        consistency = positive_count / len(indicators)

        return float(consistency)

    def _compute_spatial_stability(self, drift):
        """
        Compute spatial stability score from drift.

        Good taps have low drift (stable hand position).

        Args:
            drift (float): XY drift in pixels

        Returns:
            float: Stability score (0-1, higher = more stable)
        """
        # Sigmoid mapping: low drift → high score
        max_expected_drift = 150.0
        stability = 1.0 / (1.0 + np.exp((drift - max_expected_drift/2) / 30.0))
        return float(stability)

    def _compute_temporal_fitness(self, duration):
        """
        Compute temporal fitness score from duration.

        Good taps have duration in expected range (50-500ms).

        Args:
            duration (float): Press duration in seconds

        Returns:
            float: Fitness score (0-1)
        """
        cfg = TapDetectionConfig
        min_dur = cfg.TAP_MIN_DURATION
        max_dur = cfg.TAP_MAX_DURATION
        optimal_dur = (min_dur + max_dur) / 2

        # Gaussian-like fitness centered at optimal duration
        sigma = (max_dur - min_dur) / 4
        fitness = np.exp(-0.5 * ((duration - optimal_dur) / sigma) ** 2)

        return float(fitness)

    def predict(self, features):
        """
        Predict tap probability from features.

        Args:
            features (numpy.ndarray): Feature vector

        Returns:
            float: Tap probability (0-1)
        """
        # Ensure features is numpy array
        features = np.asarray(features, dtype=float)

        # Compute logistic regression: sigmoid(w^T x + b)
        z = float(np.dot(self.weights, features) + self.bias)
        probability = 1.0 / (1.0 + np.exp(-z))

        return probability

    def predict_with_confidence(self, features):
        """
        Predict tap probability with confidence interval.

        Args:
            features (numpy.ndarray): Feature vector

        Returns:
            tuple: (probability, confidence)
                - probability: Predicted tap probability (0-1)
                - confidence: Confidence in prediction (0-1)
        """
        prob = self.predict(features)

        # Confidence based on distance from decision boundary (0.5)
        # More extreme probabilities = higher confidence
        confidence = abs(prob - 0.5) * 2.0

        return prob, confidence

    def train(self, features, is_tap, sample_weight=1.0):
        """
        Perform online learning update (stochastic gradient descent).

        Updates model weights based on prediction error for a single example.

        Args:
            features (numpy.ndarray): Feature vector
            is_tap (bool): True label (True=tap, False=not tap)
            sample_weight (float): Weight for this training example

        Returns:
            float: Loss for this example
        """
        features = np.asarray(features, dtype=float)
        y_true = 1.0 if is_tap else 0.0

        # Predict
        y_pred = self.predict(features)

        # Compute loss (binary cross-entropy)
        loss = -y_true * np.log(y_pred + 1e-10) - (1 - y_true) * np.log(1 - y_pred + 1e-10)

        # Compute gradient
        error = y_pred - y_true
        gradient_w = error * features
        gradient_b = error

        # Update weights
        self.weights -= self.learning_rate * sample_weight * gradient_w
        self.bias -= self.learning_rate * sample_weight * gradient_b

        # Update statistics
        self.num_updates += 1
        self.training_history.append({
            'features': features.tolist(),
            'y_true': y_true,
            'y_pred': y_pred,
            'loss': loss
        })

        # Update confusion matrix
        prediction = (y_pred >= 0.5)
        if is_tap and prediction:
            self.true_positives += 1
        elif is_tap and not prediction:
            self.false_negatives += 1
        elif not is_tap and prediction:
            self.false_positives += 1
        else:
            self.true_negatives += 1

        return float(loss)

    def batch_train(self, features_list, labels_list, epochs=1):
        """
        Train on a batch of examples.

        Args:
            features_list (list): List of feature vectors
            labels_list (list): List of labels (True/False)
            epochs (int): Number of training epochs

        Returns:
            float: Average loss
        """
        total_loss = 0.0
        num_samples = len(features_list)

        for epoch in range(epochs):
            epoch_loss = 0.0

            # Shuffle data
            indices = np.random.permutation(num_samples)

            for idx in indices:
                loss = self.train(features_list[idx], labels_list[idx])
                epoch_loss += loss

            total_loss += epoch_loss / num_samples

        avg_loss = total_loss / epochs
        logger.info(f"Batch training complete: {num_samples} samples, "
                   f"{epochs} epochs, avg_loss={avg_loss:.4f}")

        return avg_loss

    def get_performance_metrics(self):
        """
        Get classifier performance metrics.

        Returns:
            dict: Performance metrics including accuracy, precision, recall, F1
        """
        total = self.true_positives + self.false_positives + \
                self.true_negatives + self.false_negatives

        if total == 0:
            return {
                'accuracy': 0.0,
                'precision': 0.0,
                'recall': 0.0,
                'f1_score': 0.0,
                'total_samples': 0
            }

        accuracy = (self.true_positives + self.true_negatives) / total

        precision = self.true_positives / (self.true_positives + self.false_positives) \
                   if (self.true_positives + self.false_positives) > 0 else 0.0

        recall = self.true_positives / (self.true_positives + self.false_negatives) \
                if (self.true_positives + self.false_negatives) > 0 else 0.0

        f1_score = 2 * precision * recall / (precision + recall) \
                  if (precision + recall) > 0 else 0.0

        return {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1_score,
            'total_samples': total,
            'true_positives': self.true_positives,
            'false_positives': self.false_positives,
            'true_negatives': self.true_negatives,
            'false_negatives': self.false_negatives
        }

    def reset_metrics(self):
        """Reset performance metrics."""
        self.true_positives = 0
        self.false_positives = 0
        self.true_negatives = 0
        self.false_negatives = 0

    def get_feature_importance(self):
        """
        Get feature importance scores based on weight magnitudes.

        Returns:
            dict: Feature names mapped to importance scores
        """
        importances = np.abs(self.weights)
        total = np.sum(importances) + 1e-10
        normalized = importances / total

        feature_importance = {
            name: float(score)
            for name, score in zip(self.feature_names, normalized)
        }

        # Sort by importance
        feature_importance = dict(sorted(
            feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        ))

        return feature_importance

    def save_model(self, filepath):
        """
        Save model weights and statistics to JSON file.

        Args:
            filepath (str): Path to save model
        """
        model_data = {
            'weights': self.weights.tolist(),
            'bias': float(self.bias),
            'feature_names': self.feature_names,
            'num_updates': self.num_updates,
            'metrics': self.get_performance_metrics(),
            'learning_rate': self.learning_rate
        }

        try:
            with open(filepath, 'w') as f:
                json.dump(model_data, f, indent=2)
            logger.info(f"Model saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")

    def load_model(self, filepath):
        """
        Load model weights and statistics from JSON file.

        Args:
            filepath (str): Path to load model from
        """
        try:
            with open(filepath, 'r') as f:
                model_data = json.load(f)

            self.weights = np.array(model_data['weights'], dtype=float)
            self.bias = float(model_data['bias'])
            self.num_updates = model_data.get('num_updates', 0)
            self.learning_rate = model_data.get('learning_rate', self.learning_rate)

            # Load metrics if available
            if 'metrics' in model_data:
                metrics = model_data['metrics']
                self.true_positives = metrics.get('true_positives', 0)
                self.false_positives = metrics.get('false_positives', 0)
                self.true_negatives = metrics.get('true_negatives', 0)
                self.false_negatives = metrics.get('false_negatives', 0)

            logger.info(f"Model loaded from {filepath} ({self.num_updates} updates)")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")


class AdaptiveTapClassifier(TapClassifier):
    """
    Adaptive classifier that automatically adjusts to user behavior.

    Extends TapClassifier with:
    - Automatic threshold adaptation based on user patterns
    - Confidence-weighted online learning
    - Periodic model saving
    """

    def __init__(self, model_path='models/adaptive_tap_model.json',
                 learning_rate=0.01, auto_save_interval=50):
        """
        Initialize adaptive classifier.

        Args:
            model_path (str): Path for saving/loading model
            learning_rate (float): Learning rate for updates
            auto_save_interval (int): Save model every N updates
        """
        super().__init__(model_path, learning_rate)

        self.model_path = model_path
        self.auto_save_interval = auto_save_interval
        self.updates_since_save = 0

        # Adaptive threshold (starts at default, adjusts based on user)
        self.adaptive_threshold = 0.5
        self.threshold_history = deque(maxlen=100)

    def predict_adaptive(self, features):
        """
        Predict with adaptive threshold.

        Args:
            features (numpy.ndarray): Feature vector

        Returns:
            tuple: (is_tap, probability)
        """
        prob = self.predict(features)
        is_tap = prob >= self.adaptive_threshold
        return is_tap, prob

    def train_adaptive(self, features, is_tap, confidence=1.0):
        """
        Train with confidence weighting and auto-save.

        Args:
            features (numpy.ndarray): Feature vector
            is_tap (bool): True label
            confidence (float): Confidence in label (0-1)

        Returns:
            float: Loss for this example
        """
        # Train with confidence as sample weight
        loss = self.train(features, is_tap, sample_weight=confidence)

        # Update threshold history
        prob = self.predict(features)
        self.threshold_history.append(prob)

        # Adapt threshold based on user patterns
        if len(self.threshold_history) >= 20:
            self._update_adaptive_threshold()

        # Auto-save periodically
        self.updates_since_save += 1
        if self.updates_since_save >= self.auto_save_interval:
            self.save_model(self.model_path)
            self.updates_since_save = 0

        return loss

    def _update_adaptive_threshold(self):
        """
        Update adaptive threshold based on recent predictions.

        Uses median of recent positive predictions to adapt to user style.
        """
        recent = list(self.threshold_history)
        # Use median of upper half as adaptive threshold
        sorted_probs = sorted(recent)
        upper_half = sorted_probs[len(sorted_probs)//2:]
        if len(upper_half) > 0:
            new_threshold = np.median(upper_half)
            # Smooth threshold changes
            alpha = 0.1
            self.adaptive_threshold = alpha * new_threshold + (1 - alpha) * self.adaptive_threshold
            # Clamp to reasonable range
            self.adaptive_threshold = np.clip(self.adaptive_threshold, 0.3, 0.7)

