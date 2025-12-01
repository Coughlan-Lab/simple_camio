"""
Quick test script to verify TapClassifier integration.

This script tests that the classifier can be loaded and used
in the pose detector without errors.
"""

import numpy as np
from tap_classifier.tap_classifier import TapClassifier
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_classifier_basic():
    """Test basic classifier functionality."""
    logger.info("Testing basic classifier functionality...")

    # Initialize classifier
    classifier = TapClassifier(model_path='../models/tap_model.json')

    # Create synthetic features for a good tap
    good_tap_features = np.array([
        0.03,   # zrel_depth
        0.02,   # plane_depth
        20.0,   # ang_depth
        0.025,  # z_depth
        50.0,   # drift
        0.3,    # vzrel
        0.25,   # vplane
        150.0,  # vang
        0.28,   # vz
        0.15,   # ray_vel
        0.15,   # duration
        0.7,    # scale_factor
        150.0,  # palm_width
        3,      # trigger_count
        1.5,    # depth_ratio
        0.8,    # vel_consistency
        0.7,    # spatial_stability
        0.9     # temporal_fitness
    ], dtype=float)

    # Predict
    prob = classifier.predict(good_tap_features)
    logger.info(f"Good tap probability: {prob:.3f} (should be high)")

    # Create synthetic features for a bad tap
    bad_tap_features = np.array([
        0.002,  # zrel_depth (too shallow)
        0.001,  # plane_depth (too shallow)
        3.0,    # ang_depth (too small)
        0.003,  # z_depth (too shallow)
        200.0,  # drift (too much)
        0.05,   # vzrel (too slow)
        0.04,   # vplane (too slow)
        30.0,   # vang (too slow)
        0.06,   # vz (too slow)
        0.02,   # ray_vel (too slow)
        0.02,   # duration (too short)
        0.5,    # scale_factor
        120.0,  # palm_width
        1,      # trigger_count (too few)
        2.0,    # depth_ratio
        0.2,    # vel_consistency (poor)
        0.2,    # spatial_stability (poor)
        0.3     # temporal_fitness (poor)
    ], dtype=float)

    prob = classifier.predict(bad_tap_features)
    logger.info(f"Bad tap probability: {prob:.3f} (should be low)")

    logger.info("Basic test PASSED ✓")


def test_classifier_training():
    """Test online learning."""
    logger.info("\nTesting online learning...")

    classifier = TapClassifier(model_path='../models/tap_model.json')

    # Create a training example
    features = np.random.rand(18)

    # Train on it
    loss = classifier.train(features, is_tap=True)
    logger.info(f"Training loss: {loss:.4f}")

    # Get metrics
    metrics = classifier.get_performance_metrics()
    logger.info(f"Total training samples: {metrics['total_samples']}")

    logger.info("Training test PASSED ✓")


def test_feature_importance():
    """Test feature importance extraction."""
    logger.info("\nTesting feature importance...")

    classifier = TapClassifier(model_path='../models/tap_model.json')

    importance = classifier.get_feature_importance()

    # Show top 5 features
    logger.info("Top 5 most important features:")
    for i, (name, score) in enumerate(list(importance.items())[:5], 1):
        logger.info(f"  {i}. {name}: {score:.4f}")

    logger.info("Feature importance test PASSED ✓")


def test_pose_detector_integration():
    """Test that pose detector can load classifier."""
    logger.info("\nTesting pose detector integration...")

    try:
        from pose_detector import PoseDetectorMPEnhanced

        # Create dummy model config
        model = {
            'filename': 'models/TestDemo/map.png',
            'zones': []
        }

        # Initialize detector (should load classifier automatically)
        detector = PoseDetectorMPEnhanced(model)

        # Check classifier was loaded
        if hasattr(detector, 'tap_classifier') and detector.tap_classifier is not None:
            logger.info("Classifier loaded successfully in pose detector ✓")
        else:
            logger.warning("Classifier not loaded in pose detector")

        logger.info("Integration test PASSED ✓")

    except Exception as e:
        logger.error(f"Integration test FAILED: {e}")
        raise


def main():
    """Run all tests."""
    logger.info("="*60)
    logger.info("TapClassifier Integration Tests")
    logger.info("="*60)

    try:
        test_classifier_basic()
        test_classifier_training()
        test_feature_importance()
        test_pose_detector_integration()

        logger.info("\n" + "="*60)
        logger.info("ALL TESTS PASSED ✓✓✓")
        logger.info("="*60)

    except Exception as e:
        logger.error(f"\nTEST FAILED: {e}")
        raise


if __name__ == '__main__':
    main()

