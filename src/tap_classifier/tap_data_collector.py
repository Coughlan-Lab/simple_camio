"""
Automatic tap data collection for Simple CamIO.

This module collects tap detection data during runtime to build training datasets
that can be used to improve the tap classifier. It captures both positive examples
(confirmed taps) and negative examples (rejected gestures) with all relevant features.

FEATURES:
- Automatic data collection during program execution
- Stores both positive and negative examples
- Handles duplicate detection
- CSV and JSON export formats
- Session-based data organization

USAGE:
    from tap_data_collector import TapDataCollector
    from src.config import TapDetectionConfig
    
    # Initialize collector
    collector = TapDataCollector(
        enabled=TapDetectionConfig.COLLECT_TAP_DATA,
        output_dir=TapDetectionConfig.TAP_DATA_DIR
    )
    
    # Collect positive example (confirmed tap)
    collector.collect_positive(features, metadata={'hand': 'Right'})
    
    # Collect negative example (rejected gesture)
    collector.collect_negative(features, metadata={'reason': 'insufficient_depth'})
    
    # Save collected data
    collector.save()
"""

import numpy as np
import json
import csv
import logging
from pathlib import Path
from datetime import datetime
from collections import deque
from src.config import TapDetectionConfig

logger = logging.getLogger(__name__)


class TapDataCollector:
    """
    Collects tap detection data during runtime for training purposes.
    
    Stores feature vectors and labels for both positive (tap) and negative
    (non-tap) examples. Data is organized by session and can be exported
    in multiple formats for training.
    """
    
    def __init__(self, enabled=False, output_dir='data/tap_dataset', max_samples=10000):
        """
        Initialize the data collector.
        
        Args:
            enabled (bool): Whether data collection is enabled
            output_dir (str): Directory to save collected data
            max_samples (int): Maximum samples to collect per session
        """
        self.enabled = enabled
        self.output_dir = Path(output_dir)
        self.max_samples = max_samples
        
        # Storage for collected samples
        self.positive_samples = []  # List of (features, metadata) tuples
        self.negative_samples = []  # List of (features, metadata) tuples
        
        # Session info
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_start = datetime.now()
        
        # Duplicate detection (keep last N feature hashes to avoid duplicates)
        self.recent_hashes = deque(maxlen=100)
        
        # Statistics
        self.total_collected = 0
        self.duplicates_rejected = 0
        
        # Create output directory if enabled
        if self.enabled:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"TapDataCollector initialized: session={self.session_id}, "
                       f"output_dir={self.output_dir}, max_samples={max_samples}")
            logger.info(f"Data collection ENABLED - will save to: {self.output_dir}")
        else:
            logger.debug("TapDataCollector disabled (COLLECT_TAP_DATA=False)")
    
    def _compute_feature_hash(self, features):
        """
        Compute hash of feature vector for duplicate detection.
        
        Args:
            features (numpy.ndarray): Feature vector
            
        Returns:
            int: Hash value
        """
        # Round to 4 decimals to handle floating point noise
        rounded = np.round(features, decimals=4)
        return hash(rounded.tobytes())
    
    def _is_duplicate(self, features):
        """
        Check if feature vector is a duplicate of recent samples.
        
        Args:
            features (numpy.ndarray): Feature vector
            
        Returns:
            bool: True if duplicate detected
        """
        feature_hash = self._compute_feature_hash(features)
        if feature_hash in self.recent_hashes:
            return True
        self.recent_hashes.append(feature_hash)
        return False
    
    def collect_positive(self, features, metadata=None):
        """
        Collect a positive example (confirmed tap).
        
        Args:
            features (numpy.ndarray): Feature vector
            metadata (dict, optional): Additional metadata about the tap
            
        Returns:
            bool: True if collected successfully, False if rejected/disabled
        """
        if not self.enabled:
            return False
        
        if self.total_collected >= self.max_samples:
            return False
        
        # Check for duplicates
        if self._is_duplicate(features):
            self.duplicates_rejected += 1
            return False
        
        # Store sample
        sample = {
            'features': np.asarray(features, dtype=float).tolist(),
            'label': True,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        self.positive_samples.append(sample)
        self.total_collected += 1
        
        logger.debug(f"Collected positive sample: total={self.total_collected}, "
                    f"positive={len(self.positive_samples)}")
        
        return True
    
    def collect_negative(self, features, metadata=None):
        """
        Collect a negative example (rejected gesture).
        
        Args:
            features (numpy.ndarray): Feature vector
            metadata (dict, optional): Additional metadata (e.g., reason for rejection)
            
        Returns:
            bool: True if collected successfully, False if rejected/disabled
        """
        if not self.enabled:
            return False
        
        if self.total_collected >= self.max_samples:
            return False
        
        # Check for duplicates
        if self._is_duplicate(features):
            self.duplicates_rejected += 1
            return False
        
        # Store sample
        sample = {
            'features': np.asarray(features, dtype=float).tolist(),
            'label': False,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        self.negative_samples.append(sample)
        self.total_collected += 1
        
        logger.debug(f"Collected negative sample: total={self.total_collected}, "
                    f"negative={len(self.negative_samples)}")
        
        return True
    
    def get_statistics(self):
        """
        Get collection statistics.
        
        Returns:
            dict: Statistics about collected data
        """
        return {
            'session_id': self.session_id,
            'session_duration': (datetime.now() - self.session_start).total_seconds(),
            'total_collected': self.total_collected,
            'positive_samples': len(self.positive_samples),
            'negative_samples': len(self.negative_samples),
            'duplicates_rejected': self.duplicates_rejected,
            'enabled': self.enabled
        }
    
    def save_json(self, filename=None):
        """
        Save collected data as JSON file.
        
        Args:
            filename (str, optional): Output filename (default: auto-generated)
            
        Returns:
            Path: Path to saved file, or None if disabled/no data
        """
        if not self.enabled or self.total_collected == 0:
            return None
        
        if filename is None:
            filename = f"tap_data_{self.session_id}.json"
        
        filepath = self.output_dir / filename
        
        data = {
            'metadata': {
                'session_id': self.session_id,
                'collection_date': datetime.now().isoformat(),
                'num_positive': len(self.positive_samples),
                'num_negative': len(self.negative_samples),
                'total_samples': self.total_collected
            },
            'samples': self.positive_samples + self.negative_samples
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {self.total_collected} samples to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save JSON data: {e}")
            return None
    
    def save_csv(self, filename=None):
        """
        Save collected data as CSV file.
        
        Args:
            filename (str, optional): Output filename (default: auto-generated)
            
        Returns:
            Path: Path to saved file, or None if disabled/no data
        """
        if not self.enabled or self.total_collected == 0:
            return None
        
        if filename is None:
            filename = f"tap_data_{self.session_id}.csv"
        
        filepath = self.output_dir / filename
        
        all_samples = self.positive_samples + self.negative_samples
        
        if len(all_samples) == 0:
            return None
        
        try:
            # Get feature names from first sample
            num_features = len(all_samples[0]['features'])
            feature_names = [f'feature_{i}' for i in range(num_features)]
            
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                
                # Header
                header = feature_names + ['label', 'timestamp']
                writer.writerow(header)
                
                # Data rows
                for sample in all_samples:
                    row = sample['features'] + [
                        1 if sample['label'] else 0,
                        sample['timestamp']
                    ]
                    writer.writerow(row)
            
            logger.info(f"Saved {self.total_collected} samples to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save CSV data: {e}")
            return None
    
    def save(self, format='json'):
        """
        Save collected data in specified format.
        
        Args:
            format (str): Output format ('json' or 'csv')
            
        Returns:
            Path: Path to saved file, or None if failed
        """
        if format == 'json':
            return self.save_json()
        elif format == 'csv':
            return self.save_csv()
        else:
            logger.error(f"Unknown format: {format}")
            return None
    
    def load_from_json(self, filepath):
        """
        Load previously collected data from JSON file.
        
        Args:
            filepath (str): Path to JSON file
            
        Returns:
            bool: True if loaded successfully
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Clear current samples
            self.positive_samples = []
            self.negative_samples = []
            
            # Load samples
            for sample in data.get('samples', []):
                if sample['label']:
                    self.positive_samples.append(sample)
                else:
                    self.negative_samples.append(sample)
            
            self.total_collected = len(self.positive_samples) + len(self.negative_samples)
            
            logger.info(f"Loaded {self.total_collected} samples from {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to load JSON data: {e}")
            return False
    
    def get_training_data(self):
        """
        Get collected data in format suitable for training.
        
        Returns:
            tuple: (features_list, labels_list)
                - features_list: List of numpy arrays
                - labels_list: List of booleans
        """
        all_samples = self.positive_samples + self.negative_samples
        
        features_list = [np.array(s['features'], dtype=float) for s in all_samples]
        labels_list = [s['label'] for s in all_samples]
        
        return features_list, labels_list
    
    def merge_with_file(self, filepath):
        """
        Merge current data with previously saved file.
        
        Args:
            filepath (str): Path to existing data file
            
        Returns:
            bool: True if merged successfully
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Add existing samples
            for sample in data.get('samples', []):
                # Check for duplicates before adding
                features = np.array(sample['features'], dtype=float)
                if not self._is_duplicate(features):
                    if sample['label']:
                        self.positive_samples.append(sample)
                    else:
                        self.negative_samples.append(sample)
                    self.total_collected += 1
            
            logger.info(f"Merged with {filepath}: now {self.total_collected} samples")
            return True
        except Exception as e:
            logger.error(f"Failed to merge with file: {e}")
            return False


def create_collector_from_config():
    """
    Create TapDataCollector instance from configuration.
    
    Convenience function to create collector with settings from config.py.
    
    Returns:
        TapDataCollector: Configured collector instance
    """
    cfg = TapDetectionConfig
    
    collector = TapDataCollector(
        enabled=cfg.COLLECT_TAP_DATA,
        output_dir=cfg.TAP_DATA_DIR,
        max_samples=cfg.MAX_COLLECTED_SAMPLES
    )
    
    return collector
