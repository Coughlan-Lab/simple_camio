"""
Configuration module for Simple CamIO.

This module contains all configuration parameters and constants used throughout the application.
Centralizing configuration makes it easier to tune parameters and understand system behavior.

PERFORMANCE TUNING:
- For best FPS: Set DEFAULT_WIDTH=640, DEFAULT_HEIGHT=480, USE_THREADED_CAPTURE=True
- For quality: Set DEFAULT_WIDTH=1920, DEFAULT_HEIGHT=1080, but expect lower FPS
- If camera is slow: Enable USE_THREADED_CAPTURE and try BACKEND=cv.CAP_MSMF
"""
import os
import cv2 as cv


# ==================== Camera Configuration ====================
class CameraConfig:
    """Camera capture configuration parameters."""

    # Default camera resolution (lower = faster)
    # Try 640x480 for best FPS, 1280x720 for balance, 1920x1080 for quality
    DEFAULT_WIDTH = 1920
    DEFAULT_HEIGHT = 1080

    # Camera buffer size (reduce latency)
    BUFFER_SIZE = 1

    # Auto-focus setting
    FOCUS = 0

    # Processing scale for pose detection (smaller = faster but less accurate)
    POSE_PROCESSING_SCALE = 0.35
    
    # Target FPS for camera (actual may vary by camera capability)
    TARGET_FPS = 30
    
    # Use threaded camera capture (can improve FPS significantly)
    USE_THREADED_CAPTURE = True
    
    # Use threaded display (non-blocking cv.imshow for smoother rendering)
    # Highly recommended for high FPS systems
    USE_THREADED_DISPLAY = True
    
    # Display frame skip - show every Nth frame to improve smoothness
    # Higher = smoother but lower display FPS (processing still happens on all frames)
    # 1 = show all frames, 2 = show every other frame, etc.
    # Recommended: 3-5 for high FPS cameras to avoid cv.imshow() blocking
    # NOTE: Less important when USE_THREADED_DISPLAY=True
    DISPLAY_FRAME_SKIP = 4
    
    # Camera backend to use (None for default, or cv.CAP_DSHOW, cv.CAP_MSMF, cv.CAP_ANY)
    # DSHOW: DirectShow (good compatibility, may be slower)
    # MSMF: Media Foundation (faster, Windows 10+)
    # None: Let OpenCV choose
    # use BACKEND = None for Windows default and BACKEND = cv.CAP_V4L2 for Linux
    if os.name == 'nt':  # Windows
        BACKEND = None  # Change to cv.CAP_MSMF for potentially better performance
    else:  # Linux/Mac
        BACKEND = cv.CAP_V4L2
    
    # Headless mode (no display window) - useful for Raspberry Pi daemon mode
    # When True, disables all cv.imshow() and display thread operations
    # Enables running as a background service without X11/display server
    HEADLESS = False


# ==================== Movement Filter Configuration ====================
class MovementFilterConfig:
    """Configuration for movement filtering algorithms."""

    # Exponential smoothing factor for simple filter
    BETA = 0.5

    # Maximum queue length for median filter
    MAX_QUEUE_LENGTH = 30

    # Time window for averaging positions (seconds)
    AVERAGING_TIME = 0.7


# ==================== Gesture Detection Configuration ====================
class GestureDetectorConfig:
    """Configuration for gesture recognition."""

    # Maximum queue length for position history
    MAX_QUEUE_LENGTH = 30

    # Time threshold for dwell detection (seconds)
    DWELL_TIME_THRESH = 0.75

    # Movement thresholds for still/moving detection
    X_MVMNT_THRESH = 0.95
    Y_MVMNT_THRESH = 0.95
    Z_MVMNT_THRESH = 4.0


# ==================== Tap Detection Configuration ====================
class TapDetectionConfig:
    """
    Configuration for single and double-tap detection.
    
    This configuration supports adaptive tap detection that scales thresholds based on
    hand size (distance from camera). Smaller hands (farther away) use more sensitive
    thresholds to maintain consistent detection across all distances.
    
    The system uses multiple detection methods:
    1. Z-depth analysis (finger tip depth changes)
    2. Angle-based analysis (finger flexion at DIP joint)
    3. Enhanced analysis (palm plane penetration, relative depth, ray projection)
    """

    # ==================== Hand Size Scaling ====================
    # Adaptive scaling ensures consistent tap detection regardless of hand distance
    REFERENCE_PALM_WIDTH = 180.0    # Reference palm width for "big hand" at close range (pixels)
    MIN_SCALE_FACTOR = 0.35         # Minimum scale factor for very small/distant hands (more sensitive)
    MAX_SCALE_FACTOR = 1.0          # Maximum scale factor (no scaling beyond reference)
    SMALL_HAND_THRESHOLD = 80.0     # Palm width below which we apply aggressive scaling

    # ==================== Z-Depth Tap Detection ====================
    # Primary method: detects taps based on fingertip Z-coordinate changes
    # All thresholds marked (SCALED) are adjusted based on hand size
    
    # Press detection thresholds
    TAP_BASE_DELTA = 0.025          # Base z delta vs baseline to start a press (SCALED)
    TAP_NOISE_MULT = 3.0            # Multiplier on median |dz| to raise threshold in noisy conditions
    TAP_MIN_VEL = 0.2               # Min negative z velocity to start a press (SCALED, inward motion)
    
    # Release detection thresholds
    TAP_RELEASE_VEL = 0.15          # Min positive z velocity to consider release (outward motion)
    TAP_MAX_RELEASE_BACK = 0.45     # Fraction of press depth required for release (0.45 = 45% return)
    
    # Temporal constraints
    TAP_MIN_DURATION = 0.05         # Minimum tap duration in seconds (reject accidental touches)
    TAP_MAX_DURATION = 0.50         # Maximum tap duration in seconds (reject prolonged presses)
    TAP_MIN_INTERVAL = 0.05         # Minimum interval between taps in seconds (debounce)
    TAP_MAX_INTERVAL = 1.00         # Maximum interval for double-tap recognition in seconds
    
    # Spatial constraints
    TAP_MIN_PRESS_DEPTH = 0.010     # Minimal press depth needed to consider a tap (SCALED)
    TAP_MAX_XY_DRIFT = 180.0        # Maximum XY drift during a tap in pixels (SCALED)
    
    # History buffer sizes for robust baseline computation
    Z_HISTORY_LEN = 7               # Number of frames to track Z-coordinate history
    XY_HISTORY_LEN = 7              # Number of frames to track XY-position history

    # Cooldown periods to prevent rapid re-triggering
    TAP_COOLDOWN = 0.7              # Cooldown after double-tap detection (seconds)
    DOUBLE_TAP_COOLDOWN_MAIN = 0.7  # Main cooldown period (seconds)

    # ==================== Angle-Based Tap Detection ====================
    # Secondary method: detects taps based on finger flexion angle at DIP joint
    # Useful for detecting taps when Z-depth is unreliable
    
    ANG_HISTORY_LEN = 7             # Number of frames to track angle history
    
    # Press detection thresholds
    ANG_BASE_DELTA = 12.0           # Min angle rise above baseline to start a press in degrees (SCALED)
    ANG_NOISE_MULT = 3.0            # Noise-adaptive margin multiplier
    ANG_MIN_VEL = 120.0             # Deg/s minimum rising angular velocity (finger closing)
    
    # Release detection thresholds
    ANG_RELEASE_VEL = -120.0        # Deg/s negative velocity for release (finger opening)
    ANG_MIN_PRESS_DEPTH = 10.0      # Degrees min peak flexion over baseline (SCALED)
    ANG_RELEASE_BACK = 0.5          # Fraction of peak angle to return for release (50%)

    # ==================== Enhanced Detection Parameters ====================
    # Used by PoseDetectorMPEnhanced for higher-precision tap detection
    # Combines multiple geometric and kinematic signals for robust detection
    
    # Palm plane penetration detection (signed distance from tip to palm plane)
    PLANE_BASE_DELTA = 0.010        # Base threshold for plane penetration (SCALED)
    PLANE_NOISE_MULT = 4.0          # Noise multiplier for adaptive threshold
    PLANE_MIN_PRESS_DEPTH = 0.008   # Minimum penetration depth for valid tap (SCALED)
    PLANE_RELEASE_BACK = 0.45       # Fraction of depth to return for release (45%)

    # Relative depth detection (tip Z relative to palm center Z)
    ZREL_BASE_DELTA = 0.010         # Base threshold for relative depth change (SCALED)
    ZREL_NOISE_MULT = 4.0           # Noise multiplier for adaptive threshold
    ZREL_MIN_PRESS_DEPTH = 0.010    # Minimum relative depth change for valid tap (SCALED)

    # Temporal smoothing via Exponential Moving Average
    EWMA_ALPHA = 0.35               # Smoothing factor (0.35 = 35% new, 65% old) - reduces jitter

    # Motion stability gates (prevent false positives during hand movement)
    STABLE_XY_VEL_MAX = 50.0        # Maximum XY velocity for stable hand (px/s)
    STABLE_ROT_MAX = 0.25           # Maximum palm rotation rate for stable hand (rad/s)

    # Landmark quality gates (reject low-quality tracking data)
    MIN_HAND_SCORE = 0.65           # Minimum MediaPipe hand detection confidence (0-1)
    JITTER_MAX_PX = 3.0             # Maximum landmark jitter in pixels

    # Ray-projection velocity (velocity along index finger pointing direction)
    RAY_MIN_IN_VEL = 0.10           # Minimum inward velocity along finger ray (SCALED, norm units/s)

    # Stronger pointing gesture gate (stricter extension ratio requirements)
    INDEX_STRONG_MIN = 0.78         # Minimum extension ratio for index finger (0.78 = 78% extended)
    OTHERS_STRONG_MAX = 0.92        # Maximum extension ratio for other fingers (must be curled)

    # Tiny classifier for final tap validation
    # Linear classifier weights for engineered features: [zrel_depth, plane_depth, ang_depth, drift, vzrel, vplane, duration]
    CLS_WEIGHTS = [2.0, 1.2, 1.0, -0.8, -0.9, -0.4, 0.6]  # Feature weights (positive = tap indicator)
    CLS_BIAS = -2.0                 # Classifier bias term
    CLS_MIN_PROB = 0.65             # Minimum probability threshold for tap classification (0-1)

    # ==================== Tap While Moving ====================
    # Allow tap detection even when hand is not in strict pointing pose
    ALLOW_TAP_WHILE_MOVING = True   # Enable tap detection during non-pointing gestures
    MOVING_TAP_TRIGGER_COUNT = 3    # Require more concurrent triggers when not pointing (stricter)

    # ==================== Data Collection ====================
    # Automatic dataset collection during runtime for classifier training
    COLLECT_TAP_DATA = False        # Enable/disable automatic data collection
    TAP_DATA_DIR = 'data/tap_dataset'  # Directory to save collected tap data
    MAX_COLLECTED_SAMPLES = 10000   # Maximum number of samples to collect per session


# ==================== Interaction Policy Configuration ====================
class InteractionConfig:
    """Configuration for 2D interaction policy."""

    # Size of the zone filter buffer
    ZONE_FILTER_SIZE = 10

    # Z-axis threshold for touch detection (cm)
    Z_THRESHOLD = 2.0


# ==================== SIFT Detection Configuration ====================
class SIFTConfig:
    """Configuration for SIFT-based model detection."""

    # SIFT feature extraction parameters
    SIFT_N_FEATURES = 2000
    SIFT_CONTRAST_THRESHOLD = 0.03
    SIFT_EDGE_THRESHOLD = 15

    # ORB feature extraction parameters (fallback)
    ORB_N_FEATURES = 2000
    ORB_SCALE_FACTOR = 1.2
    ORB_N_LEVELS = 12

    # Corner detection parameters
    CORNER_MAX_CORNERS = 500
    CORNER_QUALITY_LEVEL = 0.01
    CORNER_MIN_DISTANCE = 10

    # Matching parameters
    FLANN_TREES = 8
    FLANN_CHECKS = 100
    RATIO_THRESH = 0.8              # Lowe's ratio test threshold

    # Homography computation
    MIN_INLIER_COUNT = 10
    RANSAC_REPROJ_THRESHOLD = 5.0
    RANSAC_CONFIDENCE = 0.99
    RANSAC_MAX_ITERS = 5000

    # Tracking quality monitoring
    REDETECT_INTERVAL = 150         # Force validation every N frames
    MIN_TRACKING_QUALITY = 8        # Minimum inliers to maintain tracking

    # Quick validation parameters
    VALIDATION_INTERVAL = 2.0       # Seconds between validation checks
    VALIDATION_MIN_MATCHES = 6
    VALIDATION_POSITION_THRESHOLD = 40  # Pixels


# ==================== MediaPipe Hand Detection Configuration ====================
class MediaPipeConfig:
    """Configuration for MediaPipe hand tracking."""

    # Hand detection parameters
    MODEL_COMPLEXITY = 1
    MIN_DETECTION_CONFIDENCE = 0.75
    MIN_TRACKING_CONFIDENCE = 0.75
    MAX_NUM_HANDS = 2


# ==================== Audio Configuration ====================
class AudioConfig:
    """Configuration for audio playback."""

    # Ambient sound volume levels (0.0 to 1.0)
    # 0.05 = 5%, 0.10 = 10%, 0.25 = 25%, 0.5 = 50%, 1.0 = 100%
    HEARTBEAT_VOLUME = 0.02  # White noise when hand detected (very quiet)
    CRICKETS_VOLUME = 0.20   # Ambient crickets (quiet)
    ZONE_DESCRIPTION_VOLUME = 1.0  # Full volume for location descriptions
    
    # Map description playback mode
    # If True: Play map description only once (first hand detection)
    # If False: Play map description every time a hand appears (supports multiple users)
    PLAY_DESCRIPTION_ONCE = False


# ==================== UI Configuration ====================
class UIConfig:
    """Configuration for user interface elements."""

    # Rectangle flash when homography updates
    RECT_FLASH_FRAMES = 10

    # Colors (BGR format)
    COLOR_GREEN = (0, 255, 0)
    COLOR_YELLOW = (0, 255, 255)
    COLOR_CYAN = (255, 255, 0)
    COLOR_BLUE = (255, 0, 0)

    # Text display
    FONT = 1  # cv2.FONT_HERSHEY_SIMPLEX
    FONT_SCALE = 0.6
    FONT_THICKNESS = 2


# ==================== Worker Thread Configuration ====================
class WorkerConfig:
    """Configuration for background worker threads."""

    # Queue sizes
    POSE_QUEUE_MAXSIZE = 1
    SIFT_QUEUE_MAXSIZE = 1

    # Queue timeout (seconds)
    QUEUE_TIMEOUT = 0.1
    QUEUE_GET_TIMEOUT = 0.2

    # SIFT worker retry attempts
    SIFT_RETRY_ATTEMPTS = 3

    # Thread shutdown timeout (seconds)
    THREAD_SHUTDOWN_TIMEOUT = 2.0
