"""
MediaPipe-based hand pose detection for Simple CamIO.

This module provides three hand pose detection implementations with progressively
enhanced tap detection capabilities:

1. PoseDetectorMP (Base)
   - Basic hand tracking and pointing gesture recognition
   - Z-depth and finger angle-based tap detection
   - Hand size adaptive thresholds

2. PoseDetectorMPEnhanced (Enhanced)
   - All base functionality plus advanced tap detection
   - Palm plane penetration analysis
   - Relative depth tracking
   - Ray-projection velocity
   - Motion stability gates
   - Tiny classifier for tap validation

3. CombinedPoseDetector (Fusion)
   - Runs both base and enhanced detectors
   - Fuses outputs for maximum reliability
   - Recommended for production use

HAND SIZE SCALING:
All detectors adapt thresholds based on hand size (distance from camera).
When hands appear smaller (farther from camera), detection becomes MORE sensitive by
REDUCING thresholds proportionally. This ensures consistent tap detection across all
distances.

Scaling is based on palm width (index MCP to pinky MCP distance):
- Reference size: 180px (calibrated for close-up hands)
- Small hand threshold: <80px (applies aggressive 0.35x scaling)
- Scaling range: 0.35x to 1.0x (more sensitive when small)

Scaled parameters include:
- Z-depth thresholds (TAP_BASE_DELTA, TAP_MIN_PRESS_DEPTH)
- Angle thresholds (ANG_BASE_DELTA, ANG_MIN_PRESS_DEPTH)
- XY drift allowance (TAP_MAX_XY_DRIFT)
- Velocity thresholds (TAP_MIN_VEL, RAY_MIN_IN_VEL)
- Enhanced detection thresholds (PLANE_*, ZREL_*)

USAGE:
    from pose_detector import CombinedPoseDetector
    
    detector = CombinedPoseDetector(model)
    index_pos, status, img = detector.detect(frame, H, None, draw=True)
    
    if status == 'double_tap':
        # Handle double tap action
        pass
    elif status == 'pointing':
        # Handle pointing gesture
        pass

"""

import numpy as np
import cv2 as cv
import mediapipe as mp
from collections import deque
import time
import logging
from google.protobuf.json_format import MessageToDict
from src.config import MediaPipeConfig, TapDetectionConfig
from src.tap_classifier import TapClassifier
from src.tap_classifier.tap_data_collector import create_collector_from_config

logger = logging.getLogger(__name__)


class PoseDetectorMP:
    """
    MediaPipe-based hand pose detector with tap recognition.

    This class detects hands in camera frames, recognizes pointing gestures,
    and detects single/double taps using both Z-depth and finger flexion angles.
    """

    def __init__(self, model):
        """
        Initialize the MediaPipe pose detector.

        Args:
            model (dict): Map model configuration
        """
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            model_complexity=MediaPipeConfig.MODEL_COMPLEXITY,
            min_detection_confidence=MediaPipeConfig.MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=MediaPipeConfig.MIN_TRACKING_CONFIDENCE,
            max_num_hands=MediaPipeConfig.MAX_NUM_HANDS
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        self.image_map_color = cv.imread(model['filename'], cv.IMREAD_COLOR)

        # Initialize tap detection state (keyed by hand label: 'Left'/'Right')
        self._tap_state = {}

        # Load tap detection configuration
        self._load_tap_config()

        # Initialize data collector
        self.data_collector = create_collector_from_config()

        logger.info("Initialized MediaPipe pose detector")
        # Cache for reusing MP results (results object and frame dims)
        self._last_mp_results = None
        self._last_frame_dims = None  # (orig_w, orig_h)
        
        # Cache for hand size scaling
        self._hand_size_cache = {}  # keyed by hand label

    def _load_tap_config(self):
        """Load tap detection configuration parameters."""
        cfg = TapDetectionConfig

        # Z-based tap detection parameters
        self.TAP_BASE_DELTA = cfg.TAP_BASE_DELTA
        self.TAP_NOISE_MULT = cfg.TAP_NOISE_MULT
        self.TAP_MIN_VEL = cfg.TAP_MIN_VEL
        self.TAP_RELEASE_VEL = cfg.TAP_RELEASE_VEL
        self.TAP_MIN_DURATION = cfg.TAP_MIN_DURATION
        self.TAP_MAX_DURATION = cfg.TAP_MAX_DURATION
        self.TAP_MIN_INTERVAL = cfg.TAP_MIN_INTERVAL
        self.TAP_MAX_INTERVAL = cfg.TAP_MAX_INTERVAL
        self.TAP_MIN_PRESS_DEPTH = cfg.TAP_MIN_PRESS_DEPTH
        self.TAP_MAX_XY_DRIFT = cfg.TAP_MAX_XY_DRIFT
        self.TAP_MAX_RELEASE_BACK = cfg.TAP_MAX_RELEASE_BACK
        self.Z_HISTORY_LEN = cfg.Z_HISTORY_LEN
        self.XY_HISTORY_LEN = cfg.XY_HISTORY_LEN
        self.TAP_COOLDOWN = cfg.TAP_COOLDOWN

        # Angle-based tap detection parameters
        self.ANG_HISTORY_LEN = cfg.ANG_HISTORY_LEN
        self.ANG_BASE_DELTA = cfg.ANG_BASE_DELTA
        self.ANG_NOISE_MULT = cfg.ANG_NOISE_MULT
        self.ANG_MIN_VEL = cfg.ANG_MIN_VEL
        self.ANG_RELEASE_VEL = cfg.ANG_RELEASE_VEL
        self.ANG_MIN_PRESS_DEPTH = cfg.ANG_MIN_PRESS_DEPTH
        self.ANG_RELEASE_BACK = cfg.ANG_RELEASE_BACK

        # New: allow taps while moving (non-pointing)
        self.ALLOW_TAP_WHILE_MOVING = getattr(cfg, 'ALLOW_TAP_WHILE_MOVING', True)
        self.MOVING_TAP_TRIGGER_COUNT = getattr(cfg, 'MOVING_TAP_TRIGGER_COUNT', 3)

        # Hand size scaling parameters
        self.REFERENCE_PALM_WIDTH = cfg.REFERENCE_PALM_WIDTH
        self.MIN_SCALE_FACTOR = cfg.MIN_SCALE_FACTOR
        self.MAX_SCALE_FACTOR = cfg.MAX_SCALE_FACTOR
        self.SMALL_HAND_THRESHOLD = cfg.SMALL_HAND_THRESHOLD

    def _compute_hand_size(self, hand_landmarks, width, height):
        """
        Compute hand size metric based on palm width.
        
        The palm width is calculated as the distance between the index MCP (landmark 5)
        and pinky MCP (landmark 17) in pixel space. This metric is used to determine
        the hand's distance from the camera and adjust detection thresholds accordingly.
        
        Args:
            hand_landmarks: MediaPipe hand landmarks
            width (int): Image width in pixels
            height (int): Image height in pixels
            
        Returns:
            float: Palm width in pixels (distance between index MCP and pinky MCP)
        """
        # Index MCP (landmark 5) and Pinky MCP (landmark 17)
        idx_mcp = hand_landmarks.landmark[5]
        pinky_mcp = hand_landmarks.landmark[17]
        
        # Calculate Euclidean distance in pixel space
        dx = (idx_mcp.x - pinky_mcp.x) * width
        dy = (idx_mcp.y - pinky_mcp.y) * height
        palm_width = float(np.sqrt(dx * dx + dy * dy))
        
        return palm_width
    
    def _compute_scale_factor(self, palm_width):
        """
        Compute scaling factor based on hand size.
        
        For small hands (far from camera), we need MORE sensitive detection,
        which means SMALLER thresholds, so we return a scale factor < 1.0.
        
        The scaling is linear between SMALL_HAND_THRESHOLD and REFERENCE_PALM_WIDTH:
        - Palm width >= REFERENCE_PALM_WIDTH (180px): scale = 1.0 (no scaling)
        - Palm width <= SMALL_HAND_THRESHOLD (80px): scale = MIN_SCALE_FACTOR (0.35)
        - In between: linear interpolation
        
        This ensures that distant hands (smaller palm width) get proportionally
        reduced thresholds, making tap detection more sensitive.
        
        Args:
            palm_width (float): Measured palm width in pixels
            
        Returns:
            float: Scale factor in range [MIN_SCALE_FACTOR, MAX_SCALE_FACTOR]
        """
        if palm_width >= self.REFERENCE_PALM_WIDTH:
            # Big hand or reference size: no scaling
            return self.MAX_SCALE_FACTOR
        elif palm_width <= self.SMALL_HAND_THRESHOLD:
            # Very small hand: use minimum scale factor for maximum sensitivity
            return self.MIN_SCALE_FACTOR
        else:
            # Linear interpolation between small and reference
            ratio = (palm_width - self.SMALL_HAND_THRESHOLD) / \
                    (self.REFERENCE_PALM_WIDTH - self.SMALL_HAND_THRESHOLD)
            scale = self.MIN_SCALE_FACTOR + ratio * (self.MAX_SCALE_FACTOR - self.MIN_SCALE_FACTOR)
            return float(scale)
    
    def _get_scaled_thresholds(self, hand_key, palm_width):
        """
        Get scaled thresholds for tap detection based on hand size.
        
        Uses caching to avoid recomputing for each frame when hand size is stable.
        Thresholds are scaled to maintain consistent tap detection across different
        hand distances. Velocity thresholds use aggressive scaling because physical
        tap speed is constant but produces smaller z-velocities when farther away.
        
        Args:
            hand_key (str): Hand identifier ('Left' or 'Right')
            palm_width (float): Current palm width in pixels
            
        Returns:
            dict: Dictionary of scaled threshold values including:
                - scale_factor: Overall scaling factor
                - velocity_scale: Specialized velocity scaling
                - tap_base_delta: Scaled Z-depth press threshold
                - tap_min_press_depth: Scaled minimum press depth
                - tap_max_xy_drift: Scaled maximum XY drift
                - tap_min_vel: Scaled minimum velocity threshold
                - ang_base_delta: Scaled angle press threshold
                - ang_min_press_depth: Scaled minimum angle press depth
        """
        # Check cache
        cache_entry = self._hand_size_cache.get(hand_key)
        if cache_entry is not None:
            cached_width, cached_thresholds = cache_entry
            # Use cached values if hand size hasn't changed significantly (±5%)
            if abs(palm_width - cached_width) / cached_width < 0.05:
                return cached_thresholds
        
        # Compute scale factor
        scale = self._compute_scale_factor(palm_width)
        
        # For velocity thresholds, we need VERY aggressive scaling because:
        # 1. Physical tap speed is constant regardless of distance
        # 2. Z-coordinate velocity scales roughly with distance^2 (perspective effect)
        # 3. Small hands (far away) produce much smaller z-velocities
        # 
        # Use direct linear scaling with very low floor to allow tiny velocities:
        # - scale=1.0 → vel_scale=1.0 (no change for big hands)
        # - scale=0.5 → vel_scale=0.50 (half for medium hands)
        # - scale=0.35 → vel_scale=0.35 (very lenient for small hands)
        # - scale=0.2 → vel_scale=0.20 (extremely lenient for tiny hands)
        velocity_scale = max(0.15, scale)  # Linear scaling, floor at 0.15
        
        # Scale the thresholds (smaller scale = more sensitive)
        thresholds = {
            'scale_factor': scale,
            'palm_width': palm_width,
            'velocity_scale': velocity_scale,  # Track velocity scaling separately
            'tap_base_delta': self.TAP_BASE_DELTA * scale,
            'tap_min_press_depth': self.TAP_MIN_PRESS_DEPTH * scale,
            'tap_max_xy_drift': self.TAP_MAX_XY_DRIFT * scale,
            'tap_min_vel': self.TAP_MIN_VEL * velocity_scale,  # Use linear scaling (1:1 with scale)
            'ang_base_delta': self.ANG_BASE_DELTA * scale,
            'ang_min_press_depth': self.ANG_MIN_PRESS_DEPTH * scale,
        }
        
        # Log scaling info for debugging (only on first computation or significant change)
        if cache_entry is None:
            logger.debug(f"Hand size scaling: palm={palm_width:.1f}px, "
                        f"scale={scale:.2f}, vel_scale={velocity_scale:.2f}, "
                        f"depth_thresh={thresholds['tap_min_press_depth']:.4f}, "
                        f"vel_thresh={thresholds['tap_min_vel']:.3f}")
        
        # Cache the result
        self._hand_size_cache[hand_key] = (palm_width, thresholds)
        
        return thresholds

    def detect(self, image, H, _, processing_scale=0.5, draw=False):
        """
        Detect hand poses and gestures in the image.

        Args:
            image (numpy.ndarray): Input camera frame
            H (numpy.ndarray): Homography matrix for coordinate transformation
            _ : Unused parameter (kept for compatibility)
            processing_scale (float): Scale factor for processing (smaller = faster)
            draw (bool): Whether to draw hand landmarks on the image

        Returns:
            tuple: (index_pos, movement_status, img_out)
                   index_pos: Position of index finger [x, y, z] or None
                   movement_status: 'pointing', 'moving', 'double_tap', etc.
                   img_out: Annotated image if draw=True, else None
        """
        # Step 1: Process image with MediaPipe
        results = self._process_image_with_mediapipe(image, processing_scale)
        
        # Step 2: Cache results for downstream use
        orig_h, orig_w = image.shape[0], image.shape[1]
        self._cache_mediapipe_results(results, orig_w, orig_h)
        
        # Step 3: Initialize output variables
        img_out = image.copy() if draw else None
        index_pos = None
        movement_status = None
        
        # Step 4: Process detected hands
        if results.multi_hand_landmarks:
            index_pos, movement_status = self._process_detected_hands(
                results, orig_w, orig_h, H, draw, img_out
            )
        
        # Step 5: Normalize and return results
        normalized = self._normalize_index_position(index_pos)
        return normalized, movement_status, img_out
    
    def _process_image_with_mediapipe(self, image, processing_scale):
        """
        Process image with MediaPipe hand tracking.
        
        Args:
            image (numpy.ndarray): Input camera frame
            processing_scale (float): Scale factor for processing
            
        Returns:
            MediaPipe results object
        """
        # Downscale image for faster processing
        if processing_scale < 1.0:
            small = cv.resize(image, (0, 0), fx=processing_scale, fy=processing_scale,
                            interpolation=cv.INTER_LINEAR)
        else:
            small = image

        # Convert to RGB for MediaPipe (model expects RGB)
        small_rgb = cv.cvtColor(small, cv.COLOR_BGR2RGB)
        
        # Hint MediaPipe to avoid extra copies
        try:
            small_rgb.flags.writeable = False
        except Exception:
            pass
        
        return self.hands.process(small_rgb)
    
    def _cache_mediapipe_results(self, results, orig_w, orig_h):
        """
        Cache MediaPipe results and frame dimensions for reuse.
        
        Args:
            results: MediaPipe hand tracking results
            orig_w (int): Original image width
            orig_h (int): Original image height
        """
        self._last_mp_results = results
        self._last_frame_dims = (orig_w, orig_h)
    
    def _process_detected_hands(self, results, orig_w, orig_h, H, draw, img_out):
        """
        Process all detected hands and extract gesture information.
        
        Args:
            results: MediaPipe hand tracking results
            orig_w (int): Original image width
            orig_h (int): Original image height
            H (numpy.ndarray): Homography matrix
            draw (bool): Whether to draw landmarks
            img_out (numpy.ndarray): Output image for drawing
            
        Returns:
            tuple: (index_pos, movement_status)
        """
        index_pos = None
        movement_status = None
        
        for h, hand_landmarks in enumerate(results.multi_hand_landmarks):
            # Get hand identifier for state tracking
            hand_key = self._get_hand_key(results, h)
            
            # Detect pointing gesture
            is_pointing = self._detect_pointing_gesture(hand_landmarks, orig_w, orig_h)
            
            # Draw hand landmarks if requested
            if draw:
                self._draw_hand_landmarks(img_out, hand_landmarks)
            
            # Extract index finger position
            pos_x, pos_y, position = self._get_finger_position(
                hand_landmarks, 8, orig_w, orig_h, H
            )
            
            # Update index position (first hand only)
            if index_pos is None:
                index_pos = self._compute_normalized_position(position)
            
            # Update movement status
            if movement_status != 'double_tap':
                movement_status = self._update_movement_status(
                    hand_landmarks, is_pointing, index_pos, position, movement_status
                )
            
            # Detect taps (single and double)
            tap_detected = self._detect_taps(
                hand_landmarks, hand_key, is_pointing, pos_x, pos_y,
                orig_w, orig_h, draw, img_out
            )
            
            # Double tap overrides other statuses
            if tap_detected:
                movement_status = 'double_tap'
                break
        
        return index_pos, movement_status
    
    def _get_hand_key(self, results, hand_index):
        """
        Extract hand identifier from MediaPipe results.
        
        Args:
            results: MediaPipe hand tracking results
            hand_index (int): Index of hand in results
            
        Returns:
            str: Hand identifier ('Left' or 'Right')
        """
        handedness = MessageToDict(results.multi_handedness[hand_index])
        return handedness['classification'][0]['label']
    
    def _compute_normalized_position(self, position):
        """
        Compute normalized position from homography-transformed coordinates.
        
        Args:
            position (numpy.ndarray): Homogeneous coordinates [x', y', w']
            
        Returns:
            numpy.ndarray: Normalized 3D position [x, y, z]
        """
        return np.array([
            position[0] / position[2],  # x' / w'
            position[1] / position[2],  # y' / w'
            0                            # z reserved; not used in current pipeline
        ], dtype=float)

    def _detect_pointing_gesture(self, hand_landmarks, width, height):
        """
        Detect if hand is in pointing gesture (index extended, others curled).

        Args:
            hand_landmarks: MediaPipe hand landmarks
            width (int): Image width
            height (int): Image height

        Returns:
            bool: True if pointing gesture detected
        """
        def L(i):
            """Get landmark position in pixels [x_px, y_px, z_rel]."""
            lm = hand_landmarks.landmark[i]
            return np.array([lm.x * width, lm.y * height, lm.z], dtype=float)

        # Calculate finger extension ratios (1.0 ~ straight; smaller ~ curled)
        ratios = {}
        finger_indices = {
            'thumb': [1, 2, 3, 4],
            'index': [5, 6, 7, 8],
            'middle': [9, 10, 11, 12],
            'ring': [13, 14, 15, 16],
            'little': [17, 18, 19, 20]
        }
        for finger, indices in finger_indices.items():
            coors = np.array([L(idx) for idx in indices])
            ratios[finger] = self.ratio(coors)  # ratio = base->tip straight length / sum of bones

        # Check if other fingers intrude along the index ray (block pointing)
        a = L(5)               # Index MCP
        ab = L(8) - L(5)       # Index direction vector (to tip)
        is_pointing = True
        for finger in ['middle', 'ring', 'little']:
            indices = finger_indices[finger]
            for idx in indices:
                ap = L(idx) - a
                # Project ap onto ab via dot(ap,ab)/dot(ab,ab). If > 0.5, joint lies beyond
                # mid-index ray, likely not a clean pointing pose.
                if np.dot(ap, ab) / np.dot(ab, ab) > 0.5:
                    is_pointing = False

        # Alternative check: index much straighter than other fingers
        overall = ratios['index'] - (
            (ratios['middle'] + ratios['ring'] + ratios['little']) / 3
        )
        is_pointing = is_pointing or overall > 0.1
        return is_pointing

    def _get_finger_position(self, hand_landmarks, landmark_idx, width, height, H):
        """
        Get finger position transformed by homography.

        Args:
            hand_landmarks: MediaPipe hand landmarks
            landmark_idx (int): Landmark index to get position for
            width (int): Image width
            height (int): Image height
            H (numpy.ndarray): Homography matrix

        Returns:
            tuple: (pos_x, pos_y, position) in transformed coordinates
        """
        lm = hand_landmarks.landmark[landmark_idx]
        pos_x = lm.x * width
        pos_y = lm.y * height
        # Homography (3x3) maps image pixel [x, y, 1] to map plane [x', y', y'].
        # The caller must divide by w' to get in-plane coordinates.
        position = np.matmul(H, np.array([pos_x, pos_y, 1]))
        return pos_x, pos_y, position

    def _update_movement_status(self, hand_landmarks, is_pointing, index_pos,
                                position, current_status):
        """
        Update movement status based on hand configuration.

        Returns:
            str: Updated movement status
        """
        # Calculate finger extension ratios to judge "pointing" vs "moving"
        def L(i):
            lm = hand_landmarks.landmark[i]
            return np.array([lm.x, lm.y, lm.z], dtype=float)

        index_coors = np.array([L(i) for i in [5, 6, 7, 8]])
        ratio_index = self.ratio(index_coors)

        middle_coors = np.array([L(i) for i in [9, 10, 11, 12]])
        ratio_middle = self.ratio(middle_coors)

        ring_coors = np.array([L(i) for i in [13, 14, 15, 16]])
        ratio_ring = self.ratio(ring_coors)

        little_coors = np.array([L(i) for i in [17, 18, 19, 20]])
        ratio_little = self.ratio(little_coors)

        # Heuristic: index straight but others not fully straight -> pointing
        if (is_pointing or
            (ratio_index > 0.7 and ratio_middle < 0.95 and
             ratio_ring < 0.95 and ratio_little < 0.95)):
            if current_status != "pointing":
                return "pointing"
            else:
                # Multiple hands pointing (disambiguation flag)
                return "too_many"
        elif current_status != "pointing":
            return "moving"

        return current_status

    def _detect_taps(self, hand_landmarks, hand_key, is_pointing, pos_x, pos_y,
                    width, height, draw, img_out):
        """
        Detect single and double taps using Z-depth and finger angle analysis.

        Args:
            hand_landmarks: MediaPipe hand landmarks
            hand_key (str): Hand identifier ('Left' or 'Right')
            is_pointing (bool): Whether hand is in pointing pose
            pos_x (float): X position of fingertip
            pos_y (float): Y position of fingertip
            width (int): Image width
            height (int): Image height
            draw (bool): Whether to draw annotations
            img_out (numpy.ndarray): Output image for drawing

        Returns:
            bool: True if double tap detected
        """
        try:
            # Get current frame data
            now = time.time()
            lm8_z = float(hand_landmarks.landmark[8].z)
            angle_deg = self._compute_finger_flexion_angle(hand_landmarks, width, height)

            # Get hand size and scaled thresholds
            palm_width = self._compute_hand_size(hand_landmarks, width, height)
            thresholds = self._get_scaled_thresholds(hand_key, palm_width)

            # Get or create tap state for this hand
            state = self._get_tap_state(hand_key, lm8_z, angle_deg, pos_x, pos_y, now)

            # Update state histories
            self._update_tap_histories(state, lm8_z, angle_deg, pos_x, pos_y)

            # Calculate baselines and noise levels
            baseline_z, noise_z, dz_press = self._calculate_z_baseline(state, thresholds)
            baseline_ang, noise_ang, dang_press = self._calculate_angle_baseline(state, thresholds)

            # Calculate velocities
            dt = max(1e-3, now - state['prev_ts'])
            vz = (lm8_z - state['prev_z']) / dt         # inward is negative in MP z
            vang = (angle_deg - state['prev_angle']) / dt  # positive when closing

            # Try to start a press if either Z or angle triggers activate
            if self._try_start_press(state, is_pointing, now, baseline_z, lm8_z,
                                    dz_press, vz, baseline_ang, angle_deg,
                                    dang_press, vang, pos_x, pos_y, thresholds):
                pass  # Press started

            # Check for tap completion (single/double)
            double_tap = self._check_tap_release(state, now, lm8_z, vz, angle_deg,
                                                 vang, pos_x, pos_y, draw, img_out, thresholds)

            # Update state for next frame
            self._update_tap_state_for_next_frame(state, now, lm8_z, angle_deg)

            return double_tap

        except Exception as e:
            logger.debug(f"Error in tap detection: {e}")
            return False

    def _update_tap_histories(self, state, lm8_z, angle_deg, pos_x, pos_y):
        """
        Update history buffers used for robust baseline computation.
        
        Args:
            state (dict): Tap state dictionary
            lm8_z (float): Z-coordinate of fingertip
            angle_deg (float): Flexion angle in degrees
            pos_x (float): X position of fingertip
            pos_y (float): Y position of fingertip
        """
        state['z_history'].append(lm8_z)
        state['xy_history'].append((pos_x, pos_y))
        state['ang_history'].append(angle_deg)

    def _update_tap_state_for_next_frame(self, state, now, lm8_z, angle_deg):
        """
        Update tap state variables for the next frame.
        
        Args:
            state (dict): Tap state dictionary
            now (float): Current timestamp
            lm8_z (float): Z-coordinate of fingertip
            angle_deg (float): Flexion angle in degrees
        """
        state['prev_z'] = lm8_z
        state['prev_ts'] = now
        state['prev_angle'] = angle_deg

    def _compute_finger_flexion_angle(self, hand_landmarks, width, height):
        """Compute the flexion angle of the index finger distal joint."""
        def L(i):
            lm = hand_landmarks.landmark[i]
            return np.array([lm.x * width, lm.y * height], dtype=float)

        pip = L(6)  # Index PIP
        dip = L(7)  # Index DIP
        tip = L(8)  # Index tip

        v1 = dip - pip                     # bone vector PIP->DIP
        v2 = tip - dip                     # bone vector DIP->TIP
        n1 = np.linalg.norm(v1) + 1e-6     # |v1|; epsilon avoids div-by-zero
        n2 = np.linalg.norm(v2) + 1e-6     # |v2|
        # cos(theta) = (v1·v2)/(|v1||v2|); clamp to [-1,1] for numerical safety
        cosang = np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0)
        angle_deg = float(np.degrees(np.arccos(cosang)))  # radians->degrees
        return angle_deg

    def _get_tap_state(self, hand_key, lm8_z, angle_deg, pos_x, pos_y, now):
        """Get or initialize tap state for a hand."""
        if hand_key not in self._tap_state:
            self._tap_state[hand_key] = {
                'pressing': False,
                'prev_z': lm8_z,
                'prev_ts': now,
                'press_start': 0.0,
                'min_z': lm8_z,
                'last_tap': 0.0,
                'z_history': deque(maxlen=self.Z_HISTORY_LEN),
                'xy_history': deque(maxlen=self.XY_HISTORY_LEN),
                'press_start_xy': (pos_x, pos_y),
                'cooldown_until': 0.0,
                'start_baseline': lm8_z,
                'peak_depth': 0.0,
                'ang_history': deque(maxlen=self.ANG_HISTORY_LEN),
                'prev_angle': angle_deg,
                'start_baseline_angle': angle_deg,
                'max_angle': angle_deg,
                'peak_angle_depth': 0.0,
                'press_mode': None
            }
        return self._tap_state[hand_key]

    def _calculate_z_baseline(self, state, thresholds):
        """
        Calculate Z-depth baseline and noise-adaptive threshold.
        
        Uses robust median-based estimation to handle outliers. The baseline represents
        the "resting" Z-coordinate of the fingertip, while noise estimation captures
        frame-to-frame jitter for adaptive thresholding.
        
        Args:
            state (dict): Tap state dictionary with z_history
            thresholds (dict): Scaled thresholds dictionary
            
        Returns:
            tuple: (baseline_z, noise_z, dz_press)
                - baseline_z: Median Z-coordinate from history (robust center)
                - noise_z: Median absolute frame-to-frame difference (jitter estimate)
                - dz_press: Adaptive threshold for press detection
        """
        z_hist = list(state['z_history'])
        # Robust center estimate using median (resistant to outliers)
        baseline_z = np.median(z_hist) if len(z_hist) >= 3 else state['prev_z']
        # Robust jitter estimate using median of absolute differences
        dz_abs = np.abs(np.diff(z_hist)) if len(z_hist) >= 2 else np.array([0.0])
        noise_z = float(np.median(dz_abs)) if dz_abs.size > 0 else 0.0
        # Use scaled BASE_DELTA for better sensitivity with small hands
        # Increase threshold in noisy conditions (NOISE_MULT * jitter)
        dz_press = max(thresholds['tap_base_delta'], self.TAP_NOISE_MULT * noise_z)
        return baseline_z, noise_z, dz_press

    def _calculate_angle_baseline(self, state, thresholds):
        """
        Calculate angle baseline and noise-adaptive threshold.
        
        Similar to Z-baseline but for finger flexion angle at the DIP joint.
        Uses robust statistics to handle tracking noise.
        
        Args:
            state (dict): Tap state dictionary with ang_history
            thresholds (dict): Scaled thresholds dictionary
            
        Returns:
            tuple: (baseline_ang, noise_ang, dang_press)
                - baseline_ang: Median angle from history (robust center)
                - noise_ang: Median absolute frame-to-frame angle change
                - dang_press: Adaptive threshold for angle-based press detection
        """
        ang_hist = list(state['ang_history'])
        # Robust center estimate
        baseline_ang = np.median(ang_hist) if len(ang_hist) >= 3 else state['prev_angle']
        # Robust noise estimate
        dang_abs = np.abs(np.diff(ang_hist)) if len(ang_hist) >= 2 else np.array([0.0])
        noise_ang = float(np.median(dang_abs)) if dang_abs.size > 0 else 0.0
        # Use scaled ANG_BASE_DELTA for better sensitivity with small hands
        dang_press = max(thresholds['ang_base_delta'], self.ANG_NOISE_MULT * noise_ang)
        return baseline_ang, noise_ang, dang_press

    def _try_start_press(self, state, is_pointing, now, baseline_z, lm8_z,
                        dz_press, vz, baseline_ang, angle_deg, dang_press, vang,
                        pos_x, pos_y, thresholds):
        """Try to start a tap press based on Z or angle triggers."""
        # Relaxed gate: allow press start while moving if enabled by config
        if (not state['pressing']) and (is_pointing or self.ALLOW_TAP_WHILE_MOVING) and (now >= state.get('cooldown_until', 0.0)):
            # Z trigger: tip moved inward beyond baseline by dz_press and with sufficient inward speed
            # Use scaled velocity threshold
            z_press = (baseline_z - lm8_z > dz_press) and (vz <= -thresholds['tap_min_vel'])
            
            # Angle trigger: distal joint closing beyond baseline by dang_press and fast enough
            # BUT: disable angle detection for small hands (scale < 0.5) due to unreliability
            # AND: sanity check - reject angle changes > 50 degrees (likely noise/tracking errors)
            angle_delta = angle_deg - baseline_ang
            angle_is_sane = (0 < angle_delta < 50)  # Reasonable flexion range
            scale = thresholds.get('scale_factor', 1.0)
            ang_press = (scale >= 0.5 and  # Only use angles for medium/big hands
                        angle_is_sane and
                        (angle_delta > dang_press) and
                        (vang >= self.ANG_MIN_VEL))

            if z_press or ang_press:
                state['pressing'] = True
                state['press_start'] = now
                state['press_start_xy'] = (pos_x, pos_y)
                state['min_z'] = lm8_z
                state['start_baseline'] = baseline_z
                state['peak_depth'] = max(0.0, baseline_z - lm8_z)
                state['start_baseline_angle'] = baseline_ang
                state['max_angle'] = angle_deg
                state['peak_angle_depth'] = max(0.0, angle_deg - baseline_ang)

                if ang_press and not z_press:
                    state['press_mode'] = 'angle'
                elif z_press and not ang_press:
                    state['press_mode'] = 'z'
                else:
                    state['press_mode'] = 'either'

                return True
        return False

    def _check_tap_release(self, state, now, lm8_z, vz, angle_deg, vang,
                          pos_x, pos_y, draw, img_out, thresholds):
        """
        Check if a press should be released and if it forms a (double) tap.
        
        Args:
            state (dict): Tap state dictionary
            now (float): Current timestamp
            lm8_z (float): Current Z-coordinate
            vz (float): Z-velocity
            angle_deg (float): Current flexion angle
            vang (float): Angular velocity
            pos_x (float): Current X position
            pos_y (float): Current Y position
            draw (bool): Whether to draw annotations
            img_out (numpy.ndarray): Output image
            thresholds (dict): Scaled thresholds
            
        Returns:
            bool: True if double tap detected
        """
        if not state['pressing']:
            return False

        # Update peak values (deepest press and max angle)
        self._update_press_peaks(state, lm8_z, angle_deg)

        # Check if release conditions are met
        if self._should_release_press(state, now, lm8_z, vz, angle_deg, vang, thresholds):
            return self._handle_press_release(state, now, pos_x, pos_y, draw, img_out, thresholds)

        return False

    def _update_press_peaks(self, state, lm8_z, angle_deg):
        """
        Update peak depth and angle values during a press.
        
        Args:
            state (dict): Tap state dictionary
            lm8_z (float): Current Z-coordinate
            angle_deg (float): Current flexion angle
        """
        if lm8_z < state['min_z']:
            state['min_z'] = lm8_z
        state['peak_depth'] = max(state['peak_depth'],
                                 state['start_baseline'] - state['min_z'])

        if angle_deg > state['max_angle']:
            state['max_angle'] = angle_deg
        state['peak_angle_depth'] = max(state['peak_angle_depth'],
                                       state['max_angle'] - state['start_baseline_angle'])

    def _should_release_press(self, state, now, lm8_z, vz, angle_deg, vang, thresholds):
        """
        Determine if press should be released based on movement and timing.
        
        Args:
            state (dict): Tap state dictionary
            now (float): Current timestamp
            lm8_z (float): Current Z-coordinate
            vz (float): Z-velocity
            angle_deg (float): Current flexion angle
            vang (float): Angular velocity
            thresholds (dict): Scaled thresholds
            
        Returns:
            bool: True if press should be released
        """
        # Check Z-depth release conditions
        depth_z = max(0.0, state['peak_depth'])
        back_z = lm8_z - state['min_z']
        enough_back_z = ((depth_z >= thresholds['tap_min_press_depth']) and
                        (back_z >= self.TAP_MAX_RELEASE_BACK * depth_z))
        velocity_release_z = ((vz >= self.TAP_RELEASE_VEL) and
                             ((now - state['press_start']) >= self.TAP_MIN_DURATION))

        # Check angle release conditions
        depth_ang = max(0.0, state['peak_angle_depth'])
        back_ang = state['max_angle'] - angle_deg
        enough_back_ang = ((depth_ang >= thresholds['ang_min_press_depth']) and
                          (back_ang >= self.ANG_RELEASE_BACK * depth_ang))
        velocity_release_ang = ((vang <= self.ANG_RELEASE_VEL) and
                               ((now - state['press_start']) >= self.TAP_MIN_DURATION))

        # Check timeout condition
        too_long = (now - state['press_start'] > self.TAP_MAX_DURATION)

        return (enough_back_z or velocity_release_z or enough_back_ang or
                velocity_release_ang or too_long)

    def _handle_press_release(self, state, now, pos_x, pos_y, draw, img_out, thresholds):
        """
        Handle press release and check if it forms a valid tap.
        
        Args:
            state (dict): Tap state dictionary
            now (float): Current timestamp
            pos_x (float): Current X position
            pos_y (float): Current Y position
            draw (bool): Whether to draw annotations
            img_out (numpy.ndarray): Output image
            thresholds (dict): Scaled thresholds
            
        Returns:
            bool: True if double tap detected
        """
        press_duration = now - state['press_start']
        sx, sy = state['press_start_xy']
        xy_drift = float(np.hypot(pos_x - sx, pos_y - sy))

        depth_z = max(0.0, state['peak_depth'])
        depth_ang = max(0.0, state['peak_angle_depth'])

        # Validate tap with duration, drift, and sufficient excursion
        valid_tap = self._is_valid_tap(press_duration, xy_drift, depth_z, depth_ang, thresholds)

        if valid_tap:
            return self._process_valid_tap(state, now, pos_x, pos_y, press_duration,
                                          depth_z, depth_ang, xy_drift, draw, img_out, thresholds)
        else:
            # Collect negative example when tap validation fails
            reason = self._determine_rejection_reason(press_duration, xy_drift, depth_z, depth_ang, thresholds)
            self._collect_tap_data_negative(state, thresholds, press_duration, xy_drift, 
                                           depth_z, depth_ang, reason)
            state['pressing'] = False

        return False

    def _is_valid_tap(self, duration, drift, depth_z, depth_ang, thresholds):
        """
        Check if press qualifies as a valid tap.
        
        Args:
            duration (float): Press duration in seconds
            drift (float): XY drift during press in pixels
            depth_z (float): Z-depth of press
            depth_ang (float): Angle depth of press
            thresholds (dict): Scaled thresholds
            
        Returns:
            bool: True if tap is valid
        """
        return ((duration >= self.TAP_MIN_DURATION) and
                (drift <= thresholds['tap_max_xy_drift']) and
                ((depth_z >= thresholds['tap_min_press_depth']) or
                 (depth_ang >= thresholds['ang_min_press_depth'])))

    def _process_valid_tap(self, state, now, pos_x, pos_y, duration,
                          depth_z, depth_ang, drift, draw, img_out, thresholds):
        """
        Process a valid tap and check for double-tap.
        
        Args:
            state (dict): Tap state dictionary
            now (float): Current timestamp
            pos_x (float): Current X position
            pos_y (float): Current Y position
            duration (float): Tap duration
            depth_z (float): Z-depth of press
            depth_ang (float): Angle depth of press
            drift (float): XY drift during press
            draw (bool): Whether to draw annotations
            img_out (numpy.ndarray): Output image
            thresholds (dict): Scaled thresholds
            
        Returns:
            bool: True if double tap detected
        """
        logger.info(f"Tap detected: duration={duration:.3f}s, "
                  f"depth={depth_z:.4f}, angleDepth={depth_ang:.1f}, "
                  f"drift={drift:.1f}, scale={thresholds['scale_factor']:.2f}, "
                  f"velScale={thresholds.get('velocity_scale', 1.0):.2f}, "
                  f"palmWidth={thresholds['palm_width']:.1f}px")

        # Collect positive tap example (when tap is confirmed)
        self._collect_tap_data_positive(state, thresholds, duration, drift, depth_z, depth_ang)

        last_tap = state.get('last_tap', 0.0)
        gap = now - last_tap if last_tap > 0.0 else 1e9

        # Check for double tap
        if self._is_double_tap(state, now, last_tap, gap):
            logger.info(f"Double tap detected! Interval={gap:.3f}s")

            if draw and img_out is not None:
                cv.putText(img_out, "DOUBLE TAP",
                         (int(pos_x), int(pos_y) - 10),
                         cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            self._reset_tap_state_after_double_tap(state, now)
            return True
        else:
            state['last_tap'] = now
            state['pressing'] = False

        return False

    def _is_double_tap(self, state, now, last_tap, gap):
        """
        Check if tap qualifies as a double tap.
        
        Args:
            state (dict): Tap state dictionary
            now (float): Current timestamp
            last_tap (float): Timestamp of last tap
            gap (float): Time gap between taps
            
        Returns:
            bool: True if double tap detected
        """
        return ((last_tap > 0.0) and
                (self.TAP_MIN_INTERVAL <= gap <= self.TAP_MAX_INTERVAL) and
                (now >= state.get('cooldown_until', 0.0)))

    def _reset_tap_state_after_double_tap(self, state, now):
        """
        Reset tap state after double-tap detection.
        
        Args:
            state (dict): Tap state dictionary
            now (float): Current timestamp
        """
        state['pressing'] = False
        state['last_tap'] = 0.0
        state['cooldown_until'] = now + self.TAP_COOLDOWN
        state['z_history'].clear()
        state['xy_history'].clear()
        state['ang_history'].clear()

    def _draw_hand_landmarks(self, image, hand_landmarks):
        """Draw hand landmarks on the image."""
        self.mp_drawing.draw_landmarks(
            image,
            hand_landmarks,
            self.mp_hands.HAND_CONNECTIONS,
            self.mp_drawing_styles.get_default_hand_landmarks_style(),
            self.mp_drawing_styles.get_default_hand_connections_style()
        )

    def _normalize_index_position(self, index_pos):
        """Normalize index position to 1D array of length 3."""
        if index_pos is None:
            return None

        arr = np.asarray(index_pos)
        if arr.size == 0:
            return None
        elif arr.size >= 3:
            if arr.size % 3 == 0 and arr.size > 3:
                return arr.reshape(-1, 3)[-1].astype(float)
            else:
                return arr.flatten()[:3].astype(float)
        else:
            return None

    @staticmethod
    def ratio(coors):
        """
        Calculate finger extension ratio.

        Ratio is 1 if points are collinear (extended), lower otherwise (curled).

        Args:
            coors (numpy.ndarray): 4x3 array of finger joint coordinates

        Returns:
            float: Extension ratio (0-1)
        """
        d = np.linalg.norm(coors[0, :] - coors[3, :])  # straight-line base->tip
        a = np.linalg.norm(coors[0, :] - coors[1, :])  # bone 1 length
        b = np.linalg.norm(coors[1, :] - coors[2, :])  # bone 2 length
        c = np.linalg.norm(coors[2, :] - coors[3, :])  # bone 3 length
        return d / (a + b + c + 1e-6)                  # epsilon avoids div-by-zero

    # Add a small accessor to pass cached MP results to the enhanced detector
    def get_cached_mp_results(self):
        """
        Return cached MediaPipe results and frame dimensions from the last detect call.

        Returns:
            tuple: (results, orig_w, orig_h) or (None, None, None) if unavailable
        """
        if self._last_mp_results is None or self._last_frame_dims is None:
            return None, None, None
        ow, oh = self._last_frame_dims[0], self._last_frame_dims[1]
        return self._last_mp_results, ow, oh
    
    # ==================== Data Collection Methods ====================
    
    def _determine_rejection_reason(self, duration, drift, depth_z, depth_ang, thresholds):
        """
        Determine why a tap was rejected for data collection metadata.
        
        Args:
            duration (float): Press duration
            drift (float): XY drift
            depth_z (float): Z-depth
            depth_ang (float): Angle depth
            thresholds (dict): Scaled thresholds
            
        Returns:
            str: Rejection reason
        """
        reasons = []
        
        if duration < self.TAP_MIN_DURATION:
            reasons.append('too_short')
        elif duration > self.TAP_MAX_DURATION:
            reasons.append('too_long')
        
        if drift > thresholds['tap_max_xy_drift']:
            reasons.append('excessive_drift')
        
        if depth_z < thresholds['tap_min_press_depth'] and depth_ang < thresholds['ang_min_press_depth']:
            reasons.append('insufficient_depth')
        
        return '_'.join(reasons) if reasons else 'unknown'
    
    def _collect_tap_data_positive(self, state, thresholds, duration, drift, depth_z, depth_ang):
        """
        Collect positive tap example for training data.
        
        Args:
            state (dict): Tap state dictionary
            thresholds (dict): Scaled thresholds
            duration (float): Tap duration
            drift (float): XY drift
            depth_z (float): Z-depth
            depth_ang (float): Angle depth
        """
        if not self.data_collector.enabled:
            return
        
        logger.debug(f"Collecting positive tap data: depth_z={depth_z:.4f}, "
                    f"depth_ang={depth_ang:.1f}, duration={duration:.3f}")
        
        try:
            # Extract features from base detector state
            features = np.array([
                0.0,  # zrel_depth (not available in base)
                0.0,  # plane_depth (not available in base)
                depth_ang,  # ang_depth
                depth_z,  # z_depth
                drift,  # drift
                0.0,  # vzrel (not available in base)
                0.0,  # vplane (not available in base)
                state.get('peak_angle_depth', 0.0) / duration if duration > 0 else 0.0,  # vang estimate
                depth_z / duration if duration > 0 else 0.0,  # vz estimate
                0.0,  # ray_vel (not available in base)
                duration,  # duration
                thresholds.get('scale_factor', 1.0),  # scale_factor
                thresholds.get('palm_width', 180.0),  # palm_width
                2,  # trigger_count (base uses 2 methods: z and angle)
                0.0,  # depth_ratio (computed by collector)
                0.0,  # vel_consistency (computed by collector)
                0.0,  # spatial_stability (computed by collector)
                0.0,  # temporal_fitness (computed by collector)
            ], dtype=float)
            
            # Collect positive example
            metadata = {
                'detector': 'base',
                'press_mode': state.get('press_mode', 'unknown'),
                'depth_z': float(depth_z),
                'depth_ang': float(depth_ang)
            }
            
            self.data_collector.collect_positive(features, metadata)
            
        except Exception as e:
            logger.debug(f"Failed to collect positive tap data: {e}")
    
    def _collect_tap_data_negative(self, state, thresholds, duration, drift, depth_z, depth_ang, reason):
        """
        Collect negative tap example (rejected gesture) for training data.
        
        Args:
            state (dict): Tap state dictionary
            thresholds (dict): Scaled thresholds
            duration (float): Press duration
            drift (float): XY drift
            depth_z (float): Z-depth
            depth_ang (float): Angle depth
            reason (str): Reason for rejection
        """
        if not self.data_collector.enabled:
            return
        
        logger.debug(f"Collecting negative tap data: reason={reason}, "
                    f"depth_z={depth_z:.4f}, drift={drift:.1f}")
        
        try:
            # Extract features similar to positive collection
            features = np.array([
                0.0,  # zrel_depth (not available in base)
                0.0,  # plane_depth (not available in base)
                depth_ang,  # ang_depth
                depth_z,  # z_depth
                drift,  # drift
                0.0,  # vzrel
                0.0,  # vplane
                depth_ang / duration if duration > 0 else 0.0,  # vang estimate
                depth_z / duration if duration > 0 else 0.0,  # vz estimate
                0.0,  # ray_vel
                duration,  # duration
                thresholds.get('scale_factor', 1.0),  # scale_factor
                thresholds.get('palm_width', 180.0),  # palm_width
                1,  # trigger_count (failed taps typically have fewer triggers)
                0.0,  # depth_ratio
                0.0,  # vel_consistency
                0.0,  # spatial_stability
                0.0,  # temporal_fitness
            ], dtype=float)
            
            # Collect negative example
            metadata = {
                'detector': 'base',
                'reason': reason,
                'depth_z': float(depth_z),
                'depth_ang': float(depth_ang)
            }
            
            self.data_collector.collect_negative(features, metadata)
            
        except Exception as e:
            logger.debug(f"Failed to collect negative tap data: {e}")


class PoseDetectorMPEnhanced(PoseDetectorMP):
    """
    Enhanced MediaPipe-based hand pose detector that adds higher-precision
    tap/double-tap detection signals on top of the existing Z-depth and distal
    flexion-angle logic. Does not modify base class methods.
    """

    def __init__(self, model):
        super().__init__(model)
        # Extra per-hand state
        self._tap_state_plus = {}  # keyed by hand ('Left'/'Right')
        # Load enhanced configuration parameters into instance
        self._load_enhanced_config()
        # Reuse hand size cache from base class

        # Initialize tap classifier
        try:
            self.tap_classifier = TapClassifier(model_path='models/tap_model.json')
            logger.info("TapClassifier initialized successfully")
        except Exception as e:
            logger.warning(f"Could not initialize TapClassifier: {e}. Using fallback.")
            self.tap_classifier = None
        # self._hand_size_cache is inherited

    def _load_enhanced_config(self):
        """Load enhanced tap detection configuration parameters."""
        cfg = TapDetectionConfig
        # Plane-distance thresholds
        self.PLANE_BASE_DELTA = cfg.PLANE_BASE_DELTA
        self.PLANE_NOISE_MULT = cfg.PLANE_NOISE_MULT
        self.PLANE_MIN_PRESS_DEPTH = cfg.PLANE_MIN_PRESS_DEPTH
        self.PLANE_RELEASE_BACK = cfg.PLANE_RELEASE_BACK
        # Relative depth thresholds
        self.ZREL_BASE_DELTA = cfg.ZREL_BASE_DELTA
        self.ZREL_NOISE_MULT = cfg.ZREL_NOISE_MULT
        self.ZREL_MIN_PRESS_DEPTH = cfg.ZREL_MIN_PRESS_DEPTH
        # Smoothing
        self.EWMA_ALPHA = cfg.EWMA_ALPHA
        # Motion/rotation stability gates
        self.STABLE_XY_VEL_MAX = cfg.STABLE_XY_VEL_MAX
        self.STABLE_ROT_MAX = cfg.STABLE_ROT_MAX
        # Confidence/jitter gates
        self.MIN_HAND_SCORE = cfg.MIN_HAND_SCORE
        self.JITTER_MAX_PX = cfg.JITTER_MAX_PX
        # Ray velocity threshold
        self.RAY_MIN_IN_VEL = cfg.RAY_MIN_IN_VEL
        # Strong pointing gate
        self.INDEX_STRONG_MIN = cfg.INDEX_STRONG_MIN
        self.OTHERS_STRONG_MAX = cfg.OTHERS_STRONG_MAX
        # Tiny classifier
        try:
            self.CLS_WEIGHTS = np.array(cfg.CLS_WEIGHTS, dtype=float)
        except Exception:
            # Fallback if already an np.array or other type
            self.CLS_WEIGHTS = np.array([2.0, 1.2, 1.0, -0.8, -0.9, -0.4, 0.6], dtype=float)
        self.CLS_BIAS = cfg.CLS_BIAS
        self.CLS_MIN_PROB = cfg.CLS_MIN_PROB

    def _get_enhanced_scaled_thresholds(self, hand_key, palm_width):
        """
        Get scaled thresholds for enhanced tap detection based on hand size.
        
        Extends base class scaling to include enhanced detector thresholds.
        
        Args:
            hand_key (str): Hand identifier
            palm_width (float): Palm width in pixels
            
        Returns:
            dict: Dictionary of scaled threshold values (includes base + enhanced)
        """
        # Get base thresholds
        thresholds = self._get_scaled_thresholds(hand_key, palm_width)
        scale = thresholds['scale_factor']
        
        # Use same velocity scaling as base class for consistency (linear 1:1)
        velocity_scale = thresholds.get('velocity_scale', max(0.15, scale))
        
        # Add enhanced thresholds
        thresholds.update({
            'plane_base_delta': self.PLANE_BASE_DELTA * scale,
            'plane_min_press_depth': self.PLANE_MIN_PRESS_DEPTH * scale,
            'zrel_base_delta': self.ZREL_BASE_DELTA * scale,
            'zrel_min_press_depth': self.ZREL_MIN_PRESS_DEPTH * scale,
            'ray_min_in_vel': self.RAY_MIN_IN_VEL * velocity_scale,  # Use sqrt scaling for velocity
        })
        
        return thresholds

    # ---------- Geometry helpers ----------

    @staticmethod
    def _Lm(hand_landmarks, i, w=1.0, h=1.0):
        """Return landmark i as [x_px, y_px, z_rel] scaled by frame size."""
        lm = hand_landmarks.landmark[i]
        return np.array([lm.x * w, lm.y * h, float(lm.z)], dtype=float)

    def _palm_plane(self, hand_landmarks, w, h):
        """Palm plane (p0, n) from wrist(0), index MCP(5), pinky MCP(17)."""
        p0 = self._Lm(hand_landmarks, 0, w, h)
        p1 = self._Lm(hand_landmarks, 5, w, h)
        p2 = self._Lm(hand_landmarks, 17, w, h)
        v1 = p1 - p0
        v2 = p2 - p0
        n = np.cross(v1, v2)          # plane normal via cross product of two edges
        n_norm = np.linalg.norm(n) + 1e-9
        n /= n_norm                   # normalize normal to unit length
        return p0, n

    def _plane_signed_distance_tip(self, hand_landmarks, w, h):
        """Signed distance from fingertip to palm plane; sign indicates side of plane."""
        p0, n = self._palm_plane(hand_landmarks, w, h)
        tip = self._Lm(hand_landmarks, 8, w, h)
        return float(np.dot(n, tip - p0)), n  # distance = n · (x - p0)

    def _relative_tip_depth(self, hand_landmarks):
        """Tip Z relative to palm center Z (wrist + MCPs)."""
        idxs = [0, 5, 9, 13, 17]
        zs = [float(hand_landmarks.landmark[i].z) for i in idxs]
        palm_z = float(np.median(zs))      # robust palm depth via median
        tip_z = float(hand_landmarks.landmark[8].z)
        return tip_z - palm_z              # negative => tip closer to camera

    def _index_dir(self, hand_landmarks, w, h):
        """Unit direction from index MCP(5) to tip(8)."""
        mcp = self._Lm(hand_landmarks, 5, w, h)
        tip = self._Lm(hand_landmarks, 8, w, h)
        v = tip - mcp
        n = np.linalg.norm(v) + 1e-9
        return v / n                       # normalize to unit vector

    # ---------- Smoothing / state ----------

    def _get_plus_state(self, hand_key, now, pos_xy, zrel, ang, plane_d, palm_n):
        """Get or initialize enhanced per-hand state (EMA, histories, peaks, timers)."""
        st = self._tap_state_plus.get(hand_key)
        if st is None:
            st = {
                'prev_ts': now,
                'prev_xy': np.array(pos_xy, dtype=float),
                'prev_zrel': zrel,
                'prev_ang': ang,
                'prev_plane': plane_d,
                'ema_zrel': zrel,
                'ema_ang': ang,
                'ema_plane': plane_d,
                'xy_hist': deque(maxlen=10),
                'palm_norm_hist': deque(maxlen=10),
                'plane_hist': deque(maxlen=40),
                'zrel_hist': deque(maxlen=40),
                'score_hist': deque(maxlen=10),
                'pressing': False,
                'press_start': 0.0,
                'press_start_xy': np.array(pos_xy, dtype=float),
                'peak_zrel_depth': 0.0,
                'peak_plane_depth': 0.0,
                'peak_ang_depth': 0.0,
                'min_zrel': zrel,
                'min_plane': plane_d,
                'max_ang': ang,
                'last_tap': 0.0,
                'cooldown_until': 0.0
            }
            self._tap_state_plus[hand_key] = st
        return st

    def _ema(self, prev, x, alpha):
        """Exponential moving average: alpha*x + (1-alpha)*prev (jitter smoothing)."""
        return alpha * x + (1.0 - alpha) * prev

    # ---------- Gating ----------

    def _is_motion_stable(self, st, now, pos_xy, palm_n):
        """Check XY velocity median and palm rotation rate to gate accidental taps."""
        # XY velocity in px/s
        dt = max(1e-3, now - st['prev_ts'])
        vxy = (np.array(pos_xy, dtype=float) - st['prev_xy']) / dt
        # Palm rotation rate: angle = arccos(n_prev · n_curr); divide by dt => rad/s
        if len(st['palm_norm_hist']) >= 1:
            prev_n = st['palm_norm_hist'][-1]
            dot = float(np.clip(np.dot(prev_n, palm_n), -1.0, 1.0))
            rot = float(np.arccos(dot)) / dt
        else:
            rot = 0.0
        # Keep histories for robust median velocity
        st['xy_hist'].append(vxy)
        st['palm_norm_hist'].append(palm_n)
        if len(st['xy_hist']) >= 3:
            v_med = np.median(np.linalg.norm(np.vstack(st['xy_hist']), axis=1))  # median speed
        else:
            v_med = np.linalg.norm(vxy)
        return (v_med <= self.STABLE_XY_VEL_MAX) and (rot <= self.STABLE_ROT_MAX)

    def _confidence_ok(self, score, st):
        """Gate on detector confidence and landmark jitter to avoid low-quality frames."""
        # Landmark jitter ~ median(|vx|)+median(|vy|) over short history
        if len(st['xy_hist']) >= 4:
            xs = [v[0] for v in st['xy_hist']]
            ys = [v[1] for v in st['xy_hist']]
            jitter = float(np.median(np.abs(xs))) + float(np.median(np.abs(ys)))
        else:
            jitter = 0.0
        return (score is None or score >= self.MIN_HAND_SCORE) and (jitter <= self.JITTER_MAX_PX)

    # ---------- Thresholding / baselines ----------

    def _adaptive_baseline(self, hist, fallback):
        """Robust baseline from history using median with fallback when short."""
        if len(hist) >= 5:
            return float(np.median(hist))  # median is robust to outliers
        return fallback

    def _noise_level(self, hist):
        """Robust noise estimate using median of absolute first differences."""
        if len(hist) >= 2:
            diffs = np.abs(np.diff(np.array(hist)))  # frame-to-frame changes
            return float(np.median(diffs))
        return 0.0

    # ---------- Tiny classifier ----------

    def _tiny_cls_prob(self, features):
        """Tiny logistic regression probability on engineered tap features."""
        z = float(np.dot(self.CLS_WEIGHTS, features) + self.CLS_BIAS)  # linear score
        return 1.0 / (1.0 + np.exp(-z))  # sigmoid maps score to [0,1]

    # ---------- Enhanced tap detection ----------

    def detect(self, image, H, _, processing_scale=0.5, draw=False):
        """
        Run base detect, compute enhanced signals, and fuse for safer outputs.
        
        This method processes hand landmarks using enhanced detection algorithms
        that combine multiple signals (Z-depth, palm plane penetration, relative
        depth, ray projection) for more robust tap detection.
        
        Args:
            image (numpy.ndarray): Input camera frame
            H (numpy.ndarray): Homography matrix
            _ : Unused parameter (kept for compatibility)
            processing_scale (float): Scale factor for processing
            draw (bool): Whether to draw annotations
            
        Returns:
            tuple: (final_pos, final_status, final_img)
                - final_pos: Normalized finger position or None
                - final_status: 'double_tap', 'pointing', 'moving', or None
                - final_img: Annotated image if draw=True, else None
        """
        # Use cached base outputs when used in combination wrapper
        base_index_pos, base_status, base_img = self._get_base_outputs()
        
        # Get or process MediaPipe results
        results, ow, oh = self._get_mediapipe_results(image, processing_scale)
        
        # Process hands with enhanced detection
        img_out = image.copy() if draw else None
        index_pos, movement_status = self._process_hands_enhanced(
            results, ow, oh, H, draw, img_out
        )
        
        # Fuse base and enhanced outputs
        return self._fuse_detection_outputs(
            index_pos, movement_status, img_out,
            base_index_pos, base_status, base_img, draw
        )
    
    def _get_base_outputs(self):
        """
        Get cached base detector outputs if available.
        
        Returns:
            tuple: (base_index_pos, base_status, base_img)
        """
        if getattr(self, "_skip_super", False) and hasattr(self, "_base_cache"):
            return self._base_cache
        else:
            # Will process with MediaPipe later
            return None, None, None
    
    def _get_mediapipe_results(self, image, processing_scale):
        """
        Get MediaPipe results from cache or process image.
        
        Args:
            image (numpy.ndarray): Input camera frame
            processing_scale (float): Scale factor for processing
            
        Returns:
            tuple: (results, orig_w, orig_h)
        """
        # Check if CombinedPoseDetector provided results
        provided = getattr(self, "_provided_results", None)
        if provided is not None:
            try:
                results, ow, oh = provided
                if results is not None:
                    return results, ow, oh
            except Exception:
                pass
        
        # Process image with MediaPipe (fallback)
        return self._process_with_mediapipe(image, processing_scale)
    
    def _process_with_mediapipe(self, image, processing_scale):
        """
        Process image with MediaPipe (fallback when no cached results).
        
        Args:
            image (numpy.ndarray): Input camera frame
            processing_scale (float): Scale factor for processing
            
        Returns:
            tuple: (results, orig_w, orig_h)
        """
        if processing_scale < 1.0:
            small = cv.resize(image, (0, 0), fx=processing_scale, fy=processing_scale,
                            interpolation=cv.INTER_LINEAR)
        else:
            small = image
        small_rgb = cv.cvtColor(small, cv.COLOR_BGR2RGB)
        results = self.hands.process(small_rgb)
        oh, ow = image.shape[0], image.shape[1]
        return results, ow, oh
    
    def _process_hands_enhanced(self, results, ow, oh, H, draw, img_out):
        """
        Process detected hands with enhanced algorithms.
        
        Args:
            results: MediaPipe hand tracking results
            ow (int): Original image width
            oh (int): Original image height
            H (numpy.ndarray): Homography matrix
            draw (bool): Whether to draw landmarks
            img_out (numpy.ndarray): Output image for drawing
            
        Returns:
            tuple: (index_pos, movement_status)
        """
        index_pos = None
        movement_status = None
        
        if not (results and results.multi_hand_landmarks):
            return index_pos, movement_status
        
        orig_w, orig_h = (ow, oh) if (ow is not None and oh is not None) else (0, 0)
        
        for h_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
            # Extract hand metadata
            hand_key, score = self._extract_hand_metadata(results, h_idx)
            
            # Detect pointing gestures
            is_pointing_base = self._detect_pointing_gesture(hand_landmarks, orig_w, orig_h)
            is_pointing_strong = self._strong_pointing_gate(hand_landmarks, orig_w, orig_h)
            is_pointing = is_pointing_base and is_pointing_strong
            
            # Draw landmarks
            if draw:
                self._draw_hand_landmarks(img_out, hand_landmarks)
            
            # Get index position
            pos_x, pos_y, position = self._get_finger_position(hand_landmarks, 8, orig_w, orig_h, H)
            if index_pos is None:
                index_pos = np.array([position[0] / position[2], position[1] / position[2], 0.0], dtype=float)
            
            # Compute enhanced signals
            signals = self._compute_enhanced_signals(hand_landmarks, orig_w, orig_h)
            
            # Get hand size and scaled thresholds
            palm_width = self._compute_hand_size(hand_landmarks, orig_w, orig_h)
            thresholds = self._get_enhanced_scaled_thresholds(hand_key, palm_width)
            
            # Process tap detection
            tap_detected = self._process_enhanced_tap_detection(
                hand_key, is_pointing, score, pos_x, pos_y, signals,
                thresholds, draw, img_out
            )
            
            # Update status
            if tap_detected:
                movement_status = 'double_tap'
                break
            elif movement_status != 'double_tap':
                movement_status = 'pointing' if is_pointing else 'moving'
        
        return index_pos, movement_status
    
    def _extract_hand_metadata(self, results, h_idx):
        """
        Extract hand identifier and confidence score.
        
        Args:
            results: MediaPipe results
            h_idx (int): Hand index
            
        Returns:
            tuple: (hand_key, score)
        """
        handedness_msg = MessageToDict(results.multi_handedness[h_idx])['classification'][0]
        hand_key = handedness_msg.get('label', 'Unknown')
        score = handedness_msg.get('score', None)
        return hand_key, score
    
    def _compute_enhanced_signals(self, hand_landmarks, w, h):
        """
        Compute all enhanced detection signals.
        
        Args:
            hand_landmarks: MediaPipe hand landmarks
            w (int): Image width
            h (int): Image height
            
        Returns:
            dict: Dictionary of computed signals
        """
        angle_deg = self._compute_finger_flexion_angle(hand_landmarks, w, h)
        plane_d, palm_n = self._plane_signed_distance_tip(hand_landmarks, w, h)
        zrel = self._relative_tip_depth(hand_landmarks)
        idx_dir = self._index_dir(hand_landmarks, w, h)
        
        return {
            'angle_deg': angle_deg,
            'plane_d': plane_d,
            'palm_n': palm_n,
            'zrel': zrel,
            'idx_dir': idx_dir
        }
    
    def _process_enhanced_tap_detection(self, hand_key, is_pointing, score,
                                       pos_x, pos_y, signals, thresholds,
                                       draw, img_out):
        """
        Process tap detection with enhanced signals.
        
        Args:
            hand_key (str): Hand identifier
            is_pointing (bool): Whether hand is pointing
            score (float): Detection confidence
            pos_x (float): X position
            pos_y (float): Y position
            signals (dict): Computed signals
            thresholds (dict): Scaled thresholds
            draw (bool): Whether to draw
            img_out (numpy.ndarray): Output image
            
        Returns:
            bool: True if double tap detected
        """
        now = time.time()
        
        # Get or create enhanced state
        st = self._get_plus_state(
            hand_key, now, (pos_x, pos_y),
            signals['zrel'], signals['angle_deg'],
            signals['plane_d'], signals['palm_n']
        )
        
        # Apply temporal smoothing
        self._apply_temporal_smoothing(st, signals)
        
        # Update histories
        st['zrel_hist'].append(st['ema_zrel'])
        st['plane_hist'].append(st['ema_plane'])
        
        # Check motion stability and confidence
        stable = self._is_motion_stable(st, now, (pos_x, pos_y), signals['palm_n'])
        conf_ok = self._confidence_ok(score, st)
        
        # Compute velocities and triggers
        dt = max(1e-3, now - st['prev_ts'])
        velocities = self._compute_velocities(st, signals, dt, pos_x, pos_y)
        triggers = self._evaluate_triggers(st, signals, velocities, thresholds)
        
        # Try to start press
        if self._try_start_enhanced_press(st, is_pointing, stable, conf_ok,
                                         triggers, now, pos_x, pos_y, signals, thresholds):
            pass  # Press started
        
        # Check for tap release
        tap_detected = self._check_enhanced_tap_release(
            st, now, signals, velocities, pos_x, pos_y,
            draw, img_out, thresholds
        )
        
        # Update state for next frame
        self._update_enhanced_state(st, now, pos_x, pos_y, signals)
        
        return tap_detected
    
    def _apply_temporal_smoothing(self, st, signals):
        """
        Apply exponential moving average smoothing to signals.
        
        Args:
            st (dict): Enhanced state dictionary
            signals (dict): Current frame signals
        """
        st['ema_zrel'] = self._ema(st['ema_zrel'], signals['zrel'], self.EWMA_ALPHA)
        st['ema_ang'] = self._ema(st['ema_ang'], signals['angle_deg'], self.EWMA_ALPHA)
        st['ema_plane'] = self._ema(st['ema_plane'], signals['plane_d'], self.EWMA_ALPHA)
    
    def _compute_velocities(self, st, signals, dt, pos_x, pos_y):
        """
        Compute all velocity signals.
        
        Args:
            st (dict): Enhanced state
            signals (dict): Current signals
            dt (float): Time delta
            pos_x (float): X position
            pos_y (float): Y position
            
        Returns:
            dict: Velocity components
        """
        vzrel = (st['ema_zrel'] - st['prev_zrel']) / dt
        vang = (st['ema_ang'] - st['prev_ang']) / dt
        vplane = (st['ema_plane'] - st['prev_plane']) / dt
        
        # Ray-projection velocity
        tip_prev = np.array([st['prev_xy'][0], st['prev_xy'][1], st['prev_zrel']], dtype=float)
        tip_curr = np.array([pos_x, pos_y, st['ema_zrel']], dtype=float)
        v_tip = (tip_curr - tip_prev) / dt
        ray_in_v = float(np.dot(v_tip / (np.linalg.norm(v_tip) + 1e-9), -signals['idx_dir']))
        
        return {
            'vzrel': vzrel,
            'vang': vang,
            'vplane': vplane,
            'ray_in_v': ray_in_v
        }
    
    def _evaluate_triggers(self, st, signals, velocities, thresholds):
        """
        Evaluate all press triggers.
        
        Args:
            st (dict): Enhanced state
            signals (dict): Current signals
            velocities (dict): Velocity components
            thresholds (dict): Scaled thresholds
            
        Returns:
            dict: Trigger states
        """
        # Compute baselines
        base_zrel = self._adaptive_baseline(st['zrel_hist'], st['prev_zrel'])
        noise_zrel = self._noise_level(st['zrel_hist'])
        dzrel_press = max(self.ZREL_BASE_DELTA, self.ZREL_NOISE_MULT * noise_zrel)
        
        base_plane = self._adaptive_baseline(st['plane_hist'], st['prev_plane'])
        noise_plane = self._noise_level(st['plane_hist'])
        dplane_press = max(self.PLANE_BASE_DELTA, self.PLANE_NOISE_MULT * noise_plane)
        
        # Evaluate triggers
        zrel_press = (base_zrel - st['ema_zrel'] > dzrel_press) and (velocities['vzrel'] <= -thresholds['tap_min_vel'])
        ang_press = (st['ema_ang'] - st['prev_ang'] > 0) and (velocities['vang'] >= self.ANG_MIN_VEL)
        plane_press = (base_plane - st['ema_plane'] > dplane_press) and (velocities['vplane'] <= -thresholds['tap_min_vel'])
        ray_press = (velocities['ray_in_v'] >= thresholds['ray_min_in_vel'])
        
        trigger_count = sum([zrel_press, ang_press, plane_press, ray_press])
        
        return {
            'zrel_press': zrel_press,
            'ang_press': ang_press,
            'plane_press': plane_press,
            'ray_press': ray_press,
            'trigger_count': trigger_count,
            'base_zrel': base_zrel,
            'base_plane': base_plane
        }
    
    def _fuse_detection_outputs(self, index_pos, enhanced_status, img_out,
                               base_index_pos, base_status, base_img, draw):
        """
        Fuse base and enhanced detection outputs.
        
        Args:
            index_pos: Enhanced index position
            enhanced_status: Enhanced movement status
            img_out: Enhanced output image
            base_index_pos: Base index position
            base_status: Base movement status
            base_img: Base output image
            draw (bool): Whether drawing was requested
            
        Returns:
            tuple: (final_pos, final_status, final_img)
        """
        # Normalize positions
        normalized = self._normalize_index_position(index_pos)
        final_pos = normalized if normalized is not None else base_index_pos
        
        # Fuse statuses (double tap takes priority)
        if (base_status == 'double_tap') or (enhanced_status == 'double_tap'):
            final_status = 'double_tap'
        elif (base_status == 'pointing') or (enhanced_status == 'pointing'):
            final_status = 'pointing'
        else:
            final_status = base_status or enhanced_status
        
        # Choose output image
        final_img = img_out if (draw and img_out is not None) else base_img
        
        return final_pos, final_status, final_img

    # ---------- Enhanced tap detection helpers ----------

    def _try_start_enhanced_press(self, st, is_pointing, stable, conf_ok, triggers,
                                   now, pos_x, pos_y, signals, thresholds):
        """
        Try to start an enhanced press based on multiple triggers.
        
        Args:
            st (dict): Enhanced state dictionary
            is_pointing (bool): Whether hand is pointing
            stable (bool): Whether hand motion is stable
            conf_ok (bool): Whether confidence/quality is acceptable
            triggers (dict): Dictionary of trigger states
            now (float): Current timestamp
            pos_x (float): X position
            pos_y (float): Y position
            signals (dict): Current signals
            thresholds (dict): Scaled thresholds
            
        Returns:
            bool: True if press started
        """
        if st['pressing'] or now < st['cooldown_until']:
            return False
        
        # Determine if start conditions are met
        # Pointing: need >=2 triggers
        start_ok_pointing = is_pointing and stable and conf_ok and (triggers['trigger_count'] >= 2)
        
        # Moving (non-pointing): require stability, confidence, and stronger evidence
        start_ok_moving = (not is_pointing) and getattr(self, 'ALLOW_TAP_WHILE_MOVING', False) and \
                         stable and conf_ok and (triggers['trigger_count'] >= getattr(self, 'MOVING_TAP_TRIGGER_COUNT', 3))
        
        if start_ok_pointing or start_ok_moving:
            st['pressing'] = True
            st['press_start'] = now
            st['press_start_xy'] = np.array([pos_x, pos_y], dtype=float)
            st['min_zrel'] = st['ema_zrel']
            st['min_plane'] = st['ema_plane']
            st['max_ang'] = st['ema_ang']
            st['peak_zrel_depth'] = max(0.0, triggers['base_zrel'] - st['ema_zrel'])
            st['peak_plane_depth'] = max(0.0, triggers['base_plane'] - st['ema_plane'])
            st['peak_ang_depth'] = 0.0
            return True
        
        return False
    
    def _check_enhanced_tap_release(self, st, now, signals, velocities, pos_x, pos_y,
                                     draw, img_out, thresholds):
        """
        Check for enhanced tap release using multiple signals.
        
        Args:
            st (dict): Enhanced state dictionary
            now (float): Current timestamp
            signals (dict): Current signals
            velocities (dict): Velocity components
            pos_x (float): X position
            pos_y (float): Y position
            draw (bool): Whether to draw
            img_out (numpy.ndarray): Output image
            thresholds (dict): Scaled thresholds
            
        Returns:
            bool: True if double tap detected
        """
        if not st['pressing']:
            return False
        
        # Update peaks
        st['min_zrel'] = min(st['min_zrel'], st['ema_zrel'])
        st['min_plane'] = min(st['min_plane'], st['ema_plane'])
        st['max_ang'] = max(st['max_ang'], st['ema_ang'])
        
        # Compute baselines for comparison
        base_zrel = self._adaptive_baseline(st['zrel_hist'], st['prev_zrel'])
        base_plane = self._adaptive_baseline(st['plane_hist'], st['prev_plane'])
        
        st['peak_zrel_depth'] = max(st['peak_zrel_depth'], base_zrel - st['min_zrel'])
        st['peak_plane_depth'] = max(st['peak_plane_depth'], base_plane - st['min_plane'])
        st['peak_ang_depth'] = max(st['peak_ang_depth'], st['max_ang'] - st['prev_ang'])
        
        # Check release conditions
        if not self._should_release_enhanced_press(st, now, velocities, thresholds):
            return False
        
        # Validate tap
        if not self._is_valid_enhanced_tap(st, now, pos_x, pos_y, velocities, thresholds):
            st['pressing'] = False
            return False
        
        # Check for double tap
        return self._check_enhanced_double_tap(st, now, pos_x, pos_y, draw, img_out)
    
    def _should_release_enhanced_press(self, st, now, velocities, thresholds):
        """
        Check if enhanced press should be released.
        
        Args:
            st (dict): Enhanced state
            now (float): Current timestamp
            velocities (dict): Velocity components
            thresholds (dict): Scaled thresholds
            
        Returns:
            bool: True if should release
        """
        # Z-relative release conditions
        back_zrel = st['ema_zrel'] - st['min_zrel']
        enough_back_zrel = (st['peak_zrel_depth'] >= thresholds['zrel_min_press_depth']) and \
                          (back_zrel >= self.TAP_MAX_RELEASE_BACK * st['peak_zrel_depth'])
        vrel_release = (velocities['vzrel'] >= self.TAP_RELEASE_VEL) and \
                      ((now - st['press_start']) >= self.TAP_MIN_DURATION)
        
        # Plane release conditions
        back_plane = st['ema_plane'] - st['min_plane']
        enough_back_plane = (st['peak_plane_depth'] >= thresholds['plane_min_press_depth']) and \
                           (back_plane >= self.PLANE_RELEASE_BACK * st['peak_plane_depth'])
        vplane_release = (velocities['vplane'] >= self.TAP_RELEASE_VEL) and \
                        ((now - st['press_start']) >= self.TAP_MIN_DURATION)
        
        # Angle release conditions
        back_ang = st['max_ang'] - st['ema_ang']
        enough_back_ang = (st['peak_ang_depth'] >= thresholds['ang_min_press_depth']) and \
                         (back_ang >= self.ANG_RELEASE_BACK * st['peak_ang_depth'])
        vang_release = (velocities['vang'] <= self.ANG_RELEASE_VEL) and \
                      ((now - st['press_start']) >= self.TAP_MIN_DURATION)
        
        # Check timeout
        too_long = (now - st['press_start'] > self.TAP_MAX_DURATION)
        
        # Require at least 2 release signals or timeout
        release_votes = sum([enough_back_zrel or vrel_release,
                            enough_back_plane or vplane_release,
                            enough_back_ang or vang_release])
        
        return release_votes >= 2 or too_long
    
    def _is_valid_enhanced_tap(self, st, now, pos_x, pos_y, velocities, thresholds):
        """
        Validate enhanced tap using rules and classifier.
        
        Args:
            st (dict): Enhanced state
            now (float): Current timestamp
            pos_x (float): X position
            pos_y (float): Y position
            velocities (dict): Velocity components
            thresholds (dict): Scaled thresholds
            
        Returns:
            bool: True if valid tap
        """
        duration = now - st['press_start']
        drift = float(np.hypot(pos_x - st['press_start_xy'][0], pos_y - st['press_start_xy'][1]))
        
        # Rule-based validation
        valid_rule = (duration >= self.TAP_MIN_DURATION) and \
                    (drift <= thresholds['tap_max_xy_drift']) and \
                    ((st['peak_zrel_depth'] >= thresholds['zrel_min_press_depth']) or
                     (st['peak_plane_depth'] >= thresholds['plane_min_press_depth']) or
                     (st['peak_ang_depth'] >= thresholds['ang_min_press_depth']))
        
        # Classifier-based validation
        if self.tap_classifier is not None:
            try:
                # Extract features for classifier
                features = self._extract_classifier_features(
                    st, velocities, thresholds, duration, drift
                )

                # Store features for later training (if tap is confirmed)
                st['_last_features'] = features

                # Get classifier prediction
                prob = self.tap_classifier.predict(features)
                valid_classifier = (prob >= self.CLS_MIN_PROB)

                # Log classifier decision for debugging
                logger.debug(f"Tap classifier: prob={prob:.3f}, threshold={self.CLS_MIN_PROB:.3f}, "
                           f"rule_valid={valid_rule}, cls_valid={valid_classifier}")

                # Collect negative example if validation fails
                if not (valid_rule and valid_classifier):
                    reason = self._determine_enhanced_rejection_reason(
                        duration, drift, st, thresholds, valid_rule, valid_classifier
                    )
                    self._collect_enhanced_tap_data_negative(st, features, reason)

                # Use both rule-based and classifier validation
                return valid_rule and valid_classifier

            except Exception as e:
                logger.warning(f"Classifier prediction failed: {e}, falling back to rules")
                # Fallback to original tiny classifier
                feats = np.array([st['peak_zrel_depth'], st['peak_plane_depth'], st['peak_ang_depth'],
                                 drift, abs(velocities['vzrel']), abs(velocities['vplane']), duration], dtype=float)
                prob = self._tiny_cls_prob(feats)
                
                # Collect negative if failed
                if not (valid_rule and (prob >= self.CLS_MIN_PROB)):
                    reason = 'classifier_rejected' if not (prob >= self.CLS_MIN_PROB) else 'rule_rejected'
                    if hasattr(st, '_last_features'):
                        self._collect_enhanced_tap_data_negative(st, st['_last_features'], reason)
                
                return valid_rule and (prob >= self.CLS_MIN_PROB)
        else:
            # Fallback to original tiny classifier if main classifier not available
            feats = np.array([st['peak_zrel_depth'], st['peak_plane_depth'], st['peak_ang_depth'],
                             drift, abs(velocities['vzrel']), abs(velocities['vplane']), duration], dtype=float)
            prob = self._tiny_cls_prob(feats)
            
            # Collect negative if failed
            if not (valid_rule and (prob >= self.CLS_MIN_PROB)):
                reason = 'classifier_rejected' if not (prob >= self.CLS_MIN_PROB) else 'rule_rejected'
                if hasattr(st, '_last_features'):
                    self._collect_enhanced_tap_data_negative(st, st['_last_features'], reason)
            
            return valid_rule and (prob >= self.CLS_MIN_PROB)

    def _extract_classifier_features(self, st, velocities, thresholds, duration, drift):
        """
        Extract features for the tap classifier.

        Args:
            st (dict): Enhanced state
            velocities (dict): Velocity components
            thresholds (dict): Scaled thresholds
            duration (float): Press duration
            drift (float): XY drift

        Returns:
            numpy.ndarray: Feature vector for classifier
        """
        # Create features array matching TapClassifier.extract_features
        features = np.zeros(18, dtype=float)  # 18 features as defined in classifier

        # Depth features
        features[0] = st.get('peak_zrel_depth', 0.0)        # zrel_depth
        features[1] = st.get('peak_plane_depth', 0.0)       # plane_depth
        features[2] = st.get('peak_ang_depth', 0.0)         # ang_depth
        features[3] = 0.0  # z_depth (from base detector, not available here)

        # Spatial features
        features[4] = drift                                  # drift

        # Velocity features
        features[5] = abs(velocities.get('vzrel', 0.0))     # vzrel
        features[6] = abs(velocities.get('vplane', 0.0))    # vplane
        features[7] = velocities.get('vang', 0.0)           # vang
        features[8] = 0.0  # vz (from base detector)
        features[9] = velocities.get('ray_in_v', 0.0)       # ray_vel

        # Temporal features
        features[10] = duration                              # duration

        # Scaling features
        features[11] = thresholds.get('scale_factor', 1.0)   # scale_factor
        features[12] = thresholds.get('palm_width', 180.0)   # palm_width

        # Trigger count (not available in current context, use heuristic)
        trigger_count = sum([
            features[0] > 0.005,  # zrel depth significant
            features[1] > 0.005,  # plane depth significant
            features[2] > 5.0,    # angle depth significant
            features[5] > 0.1     # velocity significant
        ])
        features[13] = trigger_count                         # trigger_count

        # Engineered features (computed by classifier internally, but we can pre-compute)
        # depth_ratio
        features[14] = features[0] / (features[1] + 1e-6) if features[1] > 1e-6 else 0.0

        # vel_consistency (simple heuristic based on available velocities)
        vel_indicators = [-features[5], -features[6], features[7], features[9]]
        features[15] = sum(1 for v in vel_indicators if v > 0.05) / len(vel_indicators)

        # spatial_stability
        max_expected_drift = 150.0
        features[16] = 1.0 / (1.0 + np.exp((drift - max_expected_drift/2) / 30.0))

        # temporal_fitness
        cfg = TapDetectionConfig
        optimal_dur = (cfg.TAP_MIN_DURATION + cfg.TAP_MAX_DURATION) / 2
        sigma = (cfg.TAP_MAX_DURATION - cfg.TAP_MIN_DURATION) / 4
        features[17] = np.exp(-0.5 * ((duration - optimal_dur) / sigma) ** 2)

        return features

    def _check_enhanced_double_tap(self, st, now, pos_x, pos_y, draw, img_out):
        """
        Check for enhanced double tap.
        
        Args:
            st (dict): Enhanced state
            now (float): Current timestamp
            pos_x (float): X position
            pos_y (float): Y position
            draw (bool): Whether to draw
            img_out (numpy.ndarray): Output image
            
        Returns:
            bool: True if double tap detected
        """
        last_tap = st['last_tap']
        gap = now - last_tap if last_tap > 0.0 else 1e9
        
        if (last_tap > 0.0) and (self.TAP_MIN_INTERVAL <= gap <= self.TAP_MAX_INTERVAL) and \
           (now >= st['cooldown_until']):
            if draw and img_out is not None:
                cv.putText(img_out, "DOUBLE TAP", (int(pos_x), int(pos_y) - 10),
                          cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            # Collect positive tap example
            if hasattr(st, '_last_features'):
                self._collect_enhanced_tap_data_positive(st, st['_last_features'])
            
            # Train classifier on successful double tap (positive example)
            if self.tap_classifier is not None and hasattr(st, '_last_features'):
                try:
                    # Train on the features that led to this successful tap
                    self.tap_classifier.train(st['_last_features'], is_tap=True)
                    logger.debug("Classifier trained on successful tap")
                except Exception as e:
                    logger.warning(f"Failed to train classifier: {e}")

            st['last_tap'] = 0.0
            st['cooldown_until'] = now + self.TAP_COOLDOWN
            st['pressing'] = False
            return True
        else:
            st['last_tap'] = now
            st['pressing'] = False
            return False
    
    def _update_enhanced_state(self, st, now, pos_x, pos_y, signals):
        """
        Update enhanced state for next frame.
        
        Args:
            st (dict): Enhanced state
            now (float): Current timestamp
            pos_x (float): X position
            pos_y (float): Y position
            signals (dict): Current signals
        """
        st['prev_ts'] = now
        st['prev_xy'] = np.array([pos_x, pos_y], dtype=float)
        st['prev_zrel'] = st['ema_zrel']
        st['prev_ang'] = st['ema_ang']
        st['prev_plane'] = st['ema_plane']

    # ---------- Stronger pointing gate ----------
    def _strong_pointing_gate(self, hand_landmarks, w, h):
        """Stricter pointing gate using extension ratios of each finger."""
        def L(i):
            lm = hand_landmarks.landmark[i]
            return np.array([lm.x, lm.y, lm.z], dtype=float)
    
    # ==================== Enhanced Data Collection Methods ====================
    
    def _determine_enhanced_rejection_reason(self, duration, drift, st, thresholds, 
                                             valid_rule, valid_classifier):
        """
        Determine why an enhanced tap was rejected.
        
        Args:
            duration (float): Press duration
            drift (float): XY drift
            st (dict): Enhanced state
            thresholds (dict): Scaled thresholds
            valid_rule (bool): Whether rule-based validation passed
            valid_classifier (bool): Whether classifier validation passed
            
        Returns:
            str: Rejection reason
        """
        reasons = []
        
        if not valid_classifier:
            reasons.append('classifier_rejected')
        
        if not valid_rule:
            if duration < self.TAP_MIN_DURATION:
                reasons.append('too_short')
            elif duration > self.TAP_MAX_DURATION:
                reasons.append('too_long')
            
            if drift > thresholds['tap_max_xy_drift']:
                reasons.append('excessive_drift')
            
            all_depths_low = (
                st['peak_zrel_depth'] < thresholds['zrel_min_press_depth'] and
                st['peak_plane_depth'] < thresholds['plane_min_press_depth'] and
                st['peak_ang_depth'] < thresholds['ang_min_press_depth']
            )
            if all_depths_low:
                reasons.append('insufficient_depth')
        
        return '_'.join(reasons) if reasons else 'unknown'
    
    def _collect_enhanced_tap_data_positive(self, st, features):
        """
        Collect positive tap example from enhanced detector.
        
        Args:
            st (dict): Enhanced state
            features (numpy.ndarray): Feature vector
        """
        if not self.data_collector.enabled:
            return
        
        try:
            metadata = {
                'detector': 'enhanced',
                'zrel_depth': float(st.get('peak_zrel_depth', 0.0)),
                'plane_depth': float(st.get('peak_plane_depth', 0.0)),
                'ang_depth': float(st.get('peak_ang_depth', 0.0))
            }
            
            self.data_collector.collect_positive(features, metadata)
            
        except Exception as e:
            logger.debug(f"Failed to collect enhanced positive tap data: {e}")
    
    def _collect_enhanced_tap_data_negative(self, st, features, reason):
        """
        Collect negative tap example from enhanced detector.
        
        Args:
            st (dict): Enhanced state
            features (numpy.ndarray): Feature vector
            reason (str): Rejection reason
        """
        if not self.data_collector.enabled:
            return
        
        try:
            metadata = {
                'detector': 'enhanced',
                'reason': reason,
                'zrel_depth': float(st.get('peak_zrel_depth', 0.0)),
                'plane_depth': float(st.get('peak_plane_depth', 0.0)),
                'ang_depth': float(st.get('peak_ang_depth', 0.0))
            }
            
            self.data_collector.collect_negative(features, metadata)
            
        except Exception as e:
            logger.debug(f"Failed to collect enhanced negative tap data: {e}")
    
    # ---------- Stronger pointing gate (continued) ----------
    def _strong_pointing_gate(self, hand_landmarks, w, h):
        """Stricter pointing gate using extension ratios of each finger."""
        def L(i):
            lm = hand_landmarks.landmark[i]
            return np.array([lm.x, lm.y, lm.z], dtype=float)
        
        idx = np.array([L(i) for i in [5, 6, 7, 8]])
        mid = np.array([L(i) for i in [9, 10, 11, 12]])
        rng = np.array([L(i) for i in [13, 14, 15, 16]])
        ltl = np.array([L(i) for i in [17, 18, 19, 20]])
        r_idx = self.ratio(idx)    # index extension ratio
        r_mid = self.ratio(mid)    # middle extension ratio
        r_rng = self.ratio(rng)    # ring extension ratio
        r_ltl = self.ratio(ltl)    # little extension ratio
        others_max = max(r_mid, r_rng, r_ltl)
        return (r_idx >= self.INDEX_STRONG_MIN) and (others_max <= self.OTHERS_STRONG_MAX)

# ==================== Combination wrapper ====================
class CombinedPoseDetector:
    """
    Combined pose detector that runs both base and enhanced detectors.
    
    This wrapper preserves base behavior while layering enhanced precision on top.
    It runs the base detector first, caches results, then runs the enhanced detector
    using the same MediaPipe results, and finally fuses the outputs.
    
    Benefits:
    - Maximum reliability through fusion of multiple detection methods
    - Efficient processing (MediaPipe runs only once)
    - Backward compatible with base detector behavior
    - Production-ready with comprehensive tap detection
    
    Usage:
        detector = CombinedPoseDetector(model)
        index_pos, status, img = detector.detect(frame, H, None, draw=True)
    """
    
    def __init__(self, model):
        """
        Initialize combined pose detector.
        
        Args:
            model (dict): Map model configuration containing:
                - filename: Path to map image file
                - Other model-specific parameters
        """
        self.base = PoseDetectorMP(model)
        self.enh = PoseDetectorMPEnhanced(model)
        
        # Share the same data collector between both detectors
        # This ensures all collected samples go to one place
        shared_collector = self.enh.data_collector
        self.base.data_collector = shared_collector
        
        # Tell enhanced to use cached base outputs instead of calling super()
        self.enh._skip_super = True
        
        # Propagate image (for downstream tools that may inspect it)
        self.image_map_color = self.base.image_map_color
    
    @property
    def data_collector(self):
        """
        Get the data collector from the enhanced detector.
        
        The enhanced detector collects more comprehensive features,
        so we prioritize its collector. Falls back to base if needed.
        
        Returns:
            TapDataCollector: The data collector instance
        """
        return self.enh.data_collector if hasattr(self.enh, 'data_collector') else self.base.data_collector

    def detect(self, image, H, _, processing_scale=0.5, draw=False):
        """
        Run base pass, cache outputs, then run enhanced and fuse results.
        
        This method orchestrates the detection pipeline:
        1. Run base detector (compute-only, no drawing)
        2. Cache base outputs and MediaPipe results
        3. Run enhanced detector using cached MediaPipe results
        4. Fuse outputs and return (enhanced detector handles drawing)
        
        Args:
            image (numpy.ndarray): Input camera frame
            H (numpy.ndarray): Homography matrix for coordinate transformation
            _ : Unused parameter (kept for compatibility)
            processing_scale (float): Scale factor for processing (smaller = faster)
            draw (bool): Whether to draw hand landmarks and annotations
            
        Returns:
            tuple: (index_pos, movement_status, img_out)
                - index_pos: Normalized position of index finger [x, y, z] or None
                - movement_status: 'pointing', 'moving', 'double_tap', etc.
                - img_out: Annotated image if draw=True, else None
        """
        # Draw only once (in enhanced), keep base compute-only
        base_index_pos, base_status, base_img = self.base.detect(
            image, H, _, processing_scale, draw=False
        )
        
        # Cache base outputs for enhanced detector
        self.enh._base_cache = (base_index_pos, base_status, base_img)
        
        # Share MediaPipe results to avoid reprocessing
        mp_results, ow, oh = self.base.get_cached_mp_results()
        self.enh._provided_results = (mp_results, ow, oh)
        
        # Run enhanced detector with drawing enabled
        return self.enh.detect(image, H, _, processing_scale, draw)
