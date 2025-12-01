"""
Training and evaluation script for TapClassifier.

This script provides utilities to:
- Generate synthetic training data based on tap detection parameters
- Train the classifier offline
- Evaluate classifier performance
- Visualize feature importance
- Export trained models
- Load and train from collected real-world data

USAGE:
    # Generate synthetic training data and train
    python train_tap_classifier.py --train --samples 1000

    # Evaluate trained model
    python train_tap_classifier.py --evaluate

    # Show feature importance
    python train_tap_classifier.py --feature-importance

    # Train with custom parameters
    python train_tap_classifier.py --train --samples 2000 --learning-rate 0.02 --epochs 5
    
    # Train from collected real-world data
    python train_tap_classifier.py --train-from-collected --data-dir ../data/tap_dataset

COLLECTING REAL-WORLD DATA:
    1. Enable data collection in config.py:
       TapDetectionConfig.COLLECT_TAP_DATA = True
    
    2. Run the program and use it normally:
       python simple_camio.py
    
    3. Perform taps on the map as you normally would. The system will automatically
       collect both positive examples (confirmed taps) and negative examples
       (rejected gestures) with all relevant features.
    
    4. When you exit the program, collected data is saved to:
       data/tap_dataset/tap_data_<timestamp>.json
    
    5. Train the classifier on your collected data:
       python train_tap_classifier.py --train-from-collected --data-dir ../data/tap_dataset
    
    6. Optionally merge multiple sessions:
       python train_tap_classifier.py --merge-datasets --data-dir ../data/tap_dataset --output merged_data.json
    
    7. The trained model will be more accurate for your specific usage patterns!

TIPS FOR COLLECTING GOOD DATA:
    - Perform a variety of tap speeds and depths
    - Include intentional "bad" taps (too fast, too slow, with drift)
    - Use different hand distances from camera
    - Try taps while hand is moving slightly
    - The more diverse your collected data, the better the classifier will generalize
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]  # one level up from tap_classifier/
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import argparse
import logging
import json
from pathlib import Path
from tap_classifier.tap_classifier import TapClassifier
from src.config import TapDetectionConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_synthetic_tap_data(num_samples=500):
    """
    Generate synthetic training data for tap detection.

    Creates realistic feature vectors based on typical tap characteristics
    defined in TapDetectionConfig.

    Args:
        num_samples (int): Number of positive tap examples to generate

    Returns:
        tuple: (features_list, labels_list)
    """
    cfg = TapDetectionConfig
    features_list = []
    labels_list = []

    logger.info(f"Generating {num_samples} synthetic tap examples...")

    # Generate positive examples (actual taps)
    for i in range(num_samples):
        # Depth features (realistic tap depths)
        zrel_depth = np.random.uniform(cfg.ZREL_MIN_PRESS_DEPTH, 0.06)
        plane_depth = np.random.uniform(cfg.PLANE_MIN_PRESS_DEPTH, 0.05)
        ang_depth = np.random.uniform(cfg.ANG_MIN_PRESS_DEPTH, 40.0)
        z_depth = np.random.uniform(cfg.TAP_MIN_PRESS_DEPTH, 0.05)

        # Spatial features (low drift for good taps)
        drift = np.random.uniform(0, cfg.TAP_MAX_XY_DRIFT * 0.5)

        # Velocity features (inward motion)
        vzrel = np.random.uniform(cfg.TAP_MIN_VEL, 0.5)
        vplane = np.random.uniform(cfg.TAP_MIN_VEL, 0.5)
        vang = np.random.uniform(cfg.ANG_MIN_VEL, 300.0)
        vz = np.random.uniform(cfg.TAP_MIN_VEL, 0.5)
        ray_vel = np.random.uniform(cfg.RAY_MIN_IN_VEL, 0.3)

        # Temporal features (typical tap duration)
        duration = np.random.uniform(cfg.TAP_MIN_DURATION, cfg.TAP_MAX_DURATION * 0.7)

        # Hand size features
        scale_factor = np.random.uniform(cfg.MIN_SCALE_FACTOR, cfg.MAX_SCALE_FACTOR)
        palm_width = np.random.uniform(cfg.SMALL_HAND_THRESHOLD, cfg.REFERENCE_PALM_WIDTH)

        # Trigger count (taps typically trigger multiple detectors)
        trigger_count = np.random.randint(2, 5)

        # Engineered features
        depth_ratio = zrel_depth / (plane_depth + 1e-6)
        vel_consistency = np.random.uniform(0.6, 1.0)
        spatial_stability = 1.0 / (1.0 + np.exp((drift - 75.0) / 30.0))
        temporal_fitness = np.exp(-0.5 * ((duration - 0.25) / 0.125) ** 2)

        # Create feature vector
        features = np.array([
            zrel_depth, plane_depth, ang_depth, z_depth,
            drift, vzrel, vplane, vang, vz, ray_vel,
            duration, scale_factor, palm_width, trigger_count,
            depth_ratio, vel_consistency, spatial_stability, temporal_fitness
        ], dtype=float)

        features_list.append(features)
        labels_list.append(True)

    logger.info(f"Generating {num_samples} synthetic non-tap examples...")

    # Generate negative examples (not taps)
    for i in range(num_samples):
        # Non-taps can have various failure modes
        failure_mode = np.random.choice(['insufficient_depth', 'too_much_drift',
                                        'wrong_duration', 'low_velocity'])

        if failure_mode == 'insufficient_depth':
            # Too shallow press
            zrel_depth = np.random.uniform(0, cfg.ZREL_MIN_PRESS_DEPTH * 0.5)
            plane_depth = np.random.uniform(0, cfg.PLANE_MIN_PRESS_DEPTH * 0.5)
            ang_depth = np.random.uniform(0, cfg.ANG_MIN_PRESS_DEPTH * 0.5)
            z_depth = np.random.uniform(0, cfg.TAP_MIN_PRESS_DEPTH * 0.5)
            drift = np.random.uniform(0, cfg.TAP_MAX_XY_DRIFT * 0.7)
            duration = np.random.uniform(cfg.TAP_MIN_DURATION, cfg.TAP_MAX_DURATION)
        elif failure_mode == 'too_much_drift':
            # Hand moved too much
            zrel_depth = np.random.uniform(cfg.ZREL_MIN_PRESS_DEPTH, 0.04)
            plane_depth = np.random.uniform(cfg.PLANE_MIN_PRESS_DEPTH, 0.04)
            ang_depth = np.random.uniform(cfg.ANG_MIN_PRESS_DEPTH, 30.0)
            z_depth = np.random.uniform(cfg.TAP_MIN_PRESS_DEPTH, 0.04)
            drift = np.random.uniform(cfg.TAP_MAX_XY_DRIFT, cfg.TAP_MAX_XY_DRIFT * 2.0)
            duration = np.random.uniform(cfg.TAP_MIN_DURATION, cfg.TAP_MAX_DURATION)
        elif failure_mode == 'wrong_duration':
            # Too long or too short
            zrel_depth = np.random.uniform(cfg.ZREL_MIN_PRESS_DEPTH, 0.04)
            plane_depth = np.random.uniform(cfg.PLANE_MIN_PRESS_DEPTH, 0.04)
            ang_depth = np.random.uniform(cfg.ANG_MIN_PRESS_DEPTH, 30.0)
            z_depth = np.random.uniform(cfg.TAP_MIN_PRESS_DEPTH, 0.04)
            drift = np.random.uniform(0, cfg.TAP_MAX_XY_DRIFT * 0.7)
            duration_choice = np.random.choice(['too_short', 'too_long'])
            if duration_choice == 'too_short':
                duration = np.random.uniform(0.001, cfg.TAP_MIN_DURATION * 0.8)
            else:
                duration = np.random.uniform(cfg.TAP_MAX_DURATION, cfg.TAP_MAX_DURATION * 2.0)
        else:  # low_velocity
            # Not enough movement
            zrel_depth = np.random.uniform(0, cfg.ZREL_MIN_PRESS_DEPTH * 1.5)
            plane_depth = np.random.uniform(0, cfg.PLANE_MIN_PRESS_DEPTH * 1.5)
            ang_depth = np.random.uniform(0, cfg.ANG_MIN_PRESS_DEPTH * 1.5)
            z_depth = np.random.uniform(0, cfg.TAP_MIN_PRESS_DEPTH * 1.5)
            drift = np.random.uniform(0, cfg.TAP_MAX_XY_DRIFT * 0.5)
            duration = np.random.uniform(cfg.TAP_MIN_DURATION, cfg.TAP_MAX_DURATION)

        # Velocity features (varied)
        vzrel = np.random.uniform(0, cfg.TAP_MIN_VEL * 2.0)
        vplane = np.random.uniform(0, cfg.TAP_MIN_VEL * 2.0)
        vang = np.random.uniform(0, 200.0)
        vz = np.random.uniform(0, cfg.TAP_MIN_VEL * 2.0)
        ray_vel = np.random.uniform(0, cfg.RAY_MIN_IN_VEL * 1.5)

        # Hand size features
        scale_factor = np.random.uniform(cfg.MIN_SCALE_FACTOR, cfg.MAX_SCALE_FACTOR)
        palm_width = np.random.uniform(cfg.SMALL_HAND_THRESHOLD, cfg.REFERENCE_PALM_WIDTH)

        # Trigger count (non-taps typically trigger fewer detectors)
        trigger_count = np.random.randint(0, 3)

        # Engineered features
        depth_ratio = zrel_depth / (plane_depth + 1e-6) if plane_depth > 1e-6 else 0.0
        vel_consistency = np.random.uniform(0.0, 0.6)
        spatial_stability = 1.0 / (1.0 + np.exp((drift - 75.0) / 30.0))
        temporal_fitness = np.exp(-0.5 * ((duration - 0.25) / 0.125) ** 2)

        # Create feature vector
        features = np.array([
            zrel_depth, plane_depth, ang_depth, z_depth,
            drift, vzrel, vplane, vang, vz, ray_vel,
            duration, scale_factor, palm_width, trigger_count,
            depth_ratio, vel_consistency, spatial_stability, temporal_fitness
        ], dtype=float)

        features_list.append(features)
        labels_list.append(False)

    logger.info(f"Generated {len(features_list)} total examples "
               f"({sum(labels_list)} positive, {len(labels_list) - sum(labels_list)} negative)")

    return features_list, labels_list


def train_classifier(num_samples=1000, learning_rate=0.01, epochs=10,
                     model_path='models/tap_model.json'):
    """
    Train the tap classifier on synthetic data.

    Args:
        num_samples (int): Number of samples per class
        learning_rate (float): Learning rate for training
        epochs (int): Number of training epochs
        model_path (str): Path to save trained model
    """
    logger.info("Starting classifier training...")

    # Generate training data
    features_list, labels_list = generate_synthetic_tap_data(num_samples)

    # Initialize classifier
    classifier = TapClassifier(learning_rate=learning_rate)

    # Train
    logger.info(f"Training classifier for {epochs} epochs...")
    avg_loss = classifier.batch_train(features_list, labels_list, epochs=epochs)

    # Get performance metrics
    metrics = classifier.get_performance_metrics()
    logger.info(f"Training complete!")
    logger.info(f"  Average loss: {avg_loss:.4f}")
    logger.info(f"  Accuracy: {metrics['accuracy']:.3f}")
    logger.info(f"  Precision: {metrics['precision']:.3f}")
    logger.info(f"  Recall: {metrics['recall']:.3f}")
    logger.info(f"  F1 Score: {metrics['f1_score']:.3f}")

    # Save model
    classifier.save_model(model_path)
    logger.info(f"Model saved to {model_path}")

    return classifier


def evaluate_classifier(model_path='models/tap_model.json', num_test_samples=500):
    """
    Evaluate a trained classifier on test data.

    Args:
        model_path (str): Path to trained model
        num_test_samples (int): Number of test samples per class
    """
    logger.info("Evaluating classifier...")

    # Load classifier
    classifier = TapClassifier(model_path=model_path)

    # Generate test data
    features_list, labels_list = generate_synthetic_tap_data(num_test_samples)

    # Reset metrics
    classifier.reset_metrics()

    # Evaluate
    correct = 0
    total = len(features_list)

    for features, label in zip(features_list, labels_list):
        prob = classifier.predict(features)
        prediction = prob >= 0.5

        if prediction == label:
            correct += 1

        # Update confusion matrix
        if label and prediction:
            classifier.true_positives += 1
        elif label and not prediction:
            classifier.false_negatives += 1
        elif not label and prediction:
            classifier.false_positives += 1
        else:
            classifier.true_negatives += 1

    # Get metrics
    metrics = classifier.get_performance_metrics()

    logger.info("Evaluation Results:")
    logger.info(f"  Test Samples: {total}")
    logger.info(f"  Accuracy: {metrics['accuracy']:.3f}")
    logger.info(f"  Precision: {metrics['precision']:.3f}")
    logger.info(f"  Recall: {metrics['recall']:.3f}")
    logger.info(f"  F1 Score: {metrics['f1_score']:.3f}")
    logger.info(f"  Confusion Matrix:")
    logger.info(f"    True Positives: {metrics['true_positives']}")
    logger.info(f"    False Positives: {metrics['false_positives']}")
    logger.info(f"    True Negatives: {metrics['true_negatives']}")
    logger.info(f"    False Negatives: {metrics['false_negatives']}")


def show_feature_importance(model_path='models/tap_model.json'):
    """
    Display feature importance from trained model.

    Args:
        model_path (str): Path to trained model
    """
    logger.info("Loading model for feature importance analysis...")

    # Load classifier
    classifier = TapClassifier(model_path=model_path)

    # Get feature importance
    importance = classifier.get_feature_importance()

    logger.info("\nFeature Importance (normalized):")
    logger.info("=" * 50)

    for i, (feature_name, score) in enumerate(importance.items(), 1):
        bar = "█" * int(score * 50)
        logger.info(f"{i:2d}. {feature_name:20s} {bar} {score:.4f}")


def load_collected_data(data_dir):
    """
    Load collected tap data from directory.
    
    Args:
        data_dir (str): Directory containing collected JSON files
        
    Returns:
        tuple: (features_list, labels_list) or (None, None) if no data found
    """
    data_path = Path(data_dir)
    
    if not data_path.exists():
        logger.error(f"Data directory does not exist: {data_dir}")
        return None, None
    
    # Find all JSON files
    json_files = list(data_path.glob('tap_data_*.json'))
    
    if not json_files:
        logger.error(f"No tap data files found in {data_dir}")
        return None, None
    
    logger.info(f"Found {len(json_files)} data files in {data_dir}")
    
    all_features = []
    all_labels = []
    
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            samples = data.get('samples', [])
            logger.info(f"  {json_file.name}: {len(samples)} samples")
            
            for sample in samples:
                features = np.array(sample['features'], dtype=float)
                label = sample['label']
                
                all_features.append(features)
                all_labels.append(label)
                
        except Exception as e:
            logger.warning(f"Failed to load {json_file}: {e}")
    
    if not all_features:
        logger.error("No valid samples found in data files")
        return None, None
    
    logger.info(f"\nLoaded {len(all_features)} total samples:")
    logger.info(f"  Positive (taps): {sum(all_labels)}")
    logger.info(f"  Negative (non-taps): {len(all_labels) - sum(all_labels)}")
    
    return all_features, all_labels


def train_from_collected_data(data_dir, learning_rate=0.01, epochs=10,
                              model_path='models/tap_model.json'):
    """
    Train classifier on collected real-world data.
    
    Args:
        data_dir (str): Directory containing collected data
        learning_rate (float): Learning rate
        epochs (int): Training epochs
        model_path (str): Path to save model
    """
    logger.info("Training from collected data...")
    
    # Load collected data
    features_list, labels_list = load_collected_data(data_dir)
    
    if features_list is None:
        logger.error("No data to train on")
        return None
    
    # Initialize classifier
    classifier = TapClassifier(learning_rate=learning_rate)
    
    # Train
    logger.info(f"\nTraining classifier for {epochs} epochs...")
    avg_loss = classifier.batch_train(features_list, labels_list, epochs=epochs)
    
    # Get performance metrics
    metrics = classifier.get_performance_metrics()
    logger.info(f"\nTraining complete!")
    logger.info(f"  Average loss: {avg_loss:.4f}")
    logger.info(f"  Accuracy: {metrics['accuracy']:.3f}")
    logger.info(f"  Precision: {metrics['precision']:.3f}")
    logger.info(f"  Recall: {metrics['recall']:.3f}")
    logger.info(f"  F1 Score: {metrics['f1_score']:.3f}")
    
    # Save model
    classifier.save_model(model_path)
    logger.info(f"\nModel saved to {model_path}")
    
    return classifier


def merge_datasets(data_dir, output_file):
    """
    Merge multiple collected data files into one.
    
    Args:
        data_dir (str): Directory containing data files
        output_file (str): Output merged file path
    """
    logger.info(f"Merging datasets from {data_dir}...")
    
    features_list, labels_list = load_collected_data(data_dir)
    
    if features_list is None:
        logger.error("No data to merge")
        return False
    
    # Create merged data structure
    samples = []
    for features, label in zip(features_list, labels_list):
        samples.append({
            'features': features.tolist(),
            'label': label,
            'timestamp': '',  # Original timestamps lost in merge
            'metadata': {'source': 'merged'}
        })
    
    merged_data = {
        'metadata': {
            'session_id': 'merged',
            'collection_date': '',
            'num_positive': sum(labels_list),
            'num_negative': len(labels_list) - sum(labels_list),
            'total_samples': len(samples)
        },
        'samples': samples
    }
    
    # Save merged file
    try:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(merged_data, f, indent=2)
        
        logger.info(f"Merged {len(samples)} samples into {output_file}")
        return True
    except Exception as e:
        logger.error(f"Failed to save merged file: {e}")
        return False


def show_feature_importance(model_path='models/tap_model.json'):
    """
    Display feature importance from trained model.

    Args:
        model_path (str): Path to trained model
    """
    logger.info("Loading model for feature importance analysis...")

    # Load classifier
    classifier = TapClassifier(model_path=model_path)

    # Get feature importance
    importance = classifier.get_feature_importance()

    logger.info("\nFeature Importance (normalized):")
    logger.info("=" * 50)

    for i, (feature_name, score) in enumerate(importance.items(), 1):
        bar = "█" * int(score * 50)
        logger.info(f"{i:2d}. {feature_name:20s} {bar} {score:.4f}")


def main():
    """Main entry point for training script."""
    parser = argparse.ArgumentParser(description='Train and evaluate TapClassifier')

    parser.add_argument('--train', action='store_true',
                       help='Train the classifier on synthetic data')
    parser.add_argument('--train-from-collected', action='store_true',
                       help='Train the classifier on collected real-world data')
    parser.add_argument('--merge-datasets', action='store_true',
                       help='Merge multiple collected data files into one')
    parser.add_argument('--evaluate', action='store_true',
                       help='Evaluate the classifier')
    parser.add_argument('--feature-importance', action='store_true',
                       help='Show feature importance')
    parser.add_argument('--samples', type=int, default=1000,
                       help='Number of training samples per class (default: 1000)')
    parser.add_argument('--test-samples', type=int, default=500,
                       help='Number of test samples per class (default: 500)')
    parser.add_argument('--learning-rate', type=float, default=0.01,
                       help='Learning rate (default: 0.01)')
    parser.add_argument('--epochs', type=int, default=10,
                       help='Number of training epochs (default: 10)')
    parser.add_argument('--model-path', type=str, default='models/tap_model.json',
                       help='Path to model file (default: models/tap_model.json)')
    parser.add_argument('--data-dir', type=str, default='../data/tap_dataset',
                       help='Directory containing collected data (default: ../data/tap_dataset)')
    parser.add_argument('--output', type=str, default='merged_tap_data.json',
                       help='Output file for merged datasets (default: merged_tap_data.json)')

    args = parser.parse_args()

    # Ensure models directory exists
    Path('../models').mkdir(exist_ok=True)

    # Execute requested operations
    if args.train:
        train_classifier(
            num_samples=args.samples,
            learning_rate=args.learning_rate,
            epochs=args.epochs,
            model_path=args.model_path
        )
    
    if args.train_from_collected:
        train_from_collected_data(
            data_dir=args.data_dir,
            learning_rate=args.learning_rate,
            epochs=args.epochs,
            model_path=args.model_path
        )
    
    if args.merge_datasets:
        merge_datasets(
            data_dir=args.data_dir,
            output_file=args.output
        )

    if args.evaluate:
        evaluate_classifier(
            model_path=args.model_path,
            num_test_samples=args.test_samples
        )

    if args.feature_importance:
        show_feature_importance(model_path=args.model_path)

    # If no action specified, show help
    if not (args.train or args.train_from_collected or args.merge_datasets or
            args.evaluate or args.feature_importance):
        parser.print_help()
        print("\nExample usage:")
        print("  # Train on synthetic data:")
        print("  python train_tap_classifier.py --train --samples 1000")
        print("\n  # Train on collected real-world data:")
        print("  python train_tap_classifier.py --train-from-collected --data-dir ../data/tap_dataset")
        print("\n  # Merge collected datasets:")
        print("  python train_tap_classifier.py --merge-datasets --data-dir ../data/tap_dataset --output merged.json")
        print("\n  # Evaluate trained model:")
        print("  python train_tap_classifier.py --evaluate")
        print("\n  # Show feature importance:")
        print("  python train_tap_classifier.py --feature-importance")


if __name__ == '__main__':
    main()

