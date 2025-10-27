"""
SIFT-based model detection and tracking for Simple CamIO.

This module handles detecting and tracking the physical map in camera frames
using SIFT feature matching and homography estimation.
"""

import numpy as np
import cv2 as cv
import logging
from config import SIFTConfig

logger = logging.getLogger(__name__)


class SIFTModelDetectorMP:
    """
    SIFT-based detector for tracking a physical map template.

    This class uses SIFT and ORB feature matching to detect and track
    a template image in camera frames, computing the homography transformation
    between template and camera coordinates.
    """

    def __init__(self, model):
        """
        Initialize the SIFT detector with a template image.

        Args:
            model (dict): Map model configuration containing template image path
        """
        self.model = model
        img_object = cv.imread(model["template_image"], cv.IMREAD_GRAYSCALE)
        self.img_object = img_object

        # Initialize feature detectors
        self.sift_detector = cv.SIFT_create(
            nfeatures=SIFTConfig.SIFT_N_FEATURES,
            contrastThreshold=SIFTConfig.SIFT_CONTRAST_THRESHOLD,
            edgeThreshold=SIFTConfig.SIFT_EDGE_THRESHOLD
        )
        self.orb_detector = cv.ORB_create(
            nfeatures=SIFTConfig.ORB_N_FEATURES,
            scaleFactor=SIFTConfig.ORB_SCALE_FACTOR,
            nlevels=SIFTConfig.ORB_N_LEVELS
        )

        # Reusable matchers (avoid per-call allocations)
        try:
            FLANN_INDEX_KDTREE = 1
            self._flann_params_main = dict(algorithm=FLANN_INDEX_KDTREE, trees=SIFTConfig.FLANN_TREES)
            self._search_params_main = dict(checks=SIFTConfig.FLANN_CHECKS)
            self.flann_sift = cv.FlannBasedMatcher(self._flann_params_main, self._search_params_main)
            # Quick-validation matcher with lighter params
            self._flann_params_quick = dict(algorithm=FLANN_INDEX_KDTREE, trees=6)
            self._search_params_quick = dict(checks=50)
            self.flann_sift_quick = cv.FlannBasedMatcher(self._flann_params_quick, self._search_params_quick)
        except Exception:
            self.flann_sift = None
            self.flann_sift_quick = None
        self.bf_orb = cv.BFMatcher(cv.NORM_HAMMING, crossCheck=False)

        # Extract template features
        self._extract_template_features(img_object)

        # Store template shape and precompute corners
        self.template_shape = img_object.shape[:2]  # (h, w)
        h_t, w_t = self.template_shape
        self.obj_corners = np.array([[0, 0], [w_t, 0], [w_t, h_t], [0, h_t]],
                                    dtype=np.float32).reshape(-1, 1, 2)

        # Tracking state
        self.requires_homography = True
        self.H = None
        self.MIN_INLIER_COUNT = SIFTConfig.MIN_INLIER_COUNT
        self.frames_since_last_detection = 0
        self.REDETECT_INTERVAL = SIFTConfig.REDETECT_INTERVAL
        self.last_inlier_count = 0
        self.tracking_quality_history = []
        self.MIN_TRACKING_QUALITY = SIFTConfig.MIN_TRACKING_QUALITY

        # Visualization state
        self.homography_updated = False
        self.last_rect_pts = None  # Projected rectangle corners in camera coords
        self.debug = False

        logger.info(f"Template features: SIFT={len(self.keypoints_sift)}, "
                   f"ORB={len(self.keypoints_orb)}")

    def _extract_template_features(self, img_object):
        """Extract SIFT and ORB features from the template image."""
        # SIFT features
        keypoints_sift, descriptors_sift = self.sift_detector.detectAndCompute(
            img_object, mask=None
        )
        keypoints_sift = list(keypoints_sift)

        # ORB features (fallback)
        self.keypoints_orb, self.descriptors_orb = self.orb_detector.detectAndCompute(
            img_object, mask=None
        )

        # Add corner features to SIFT keypoints for better edge detection
        corners = cv.goodFeaturesToTrack(
            img_object,
            maxCorners=SIFTConfig.CORNER_MAX_CORNERS,
            qualityLevel=SIFTConfig.CORNER_QUALITY_LEVEL,
            minDistance=SIFTConfig.CORNER_MIN_DISTANCE
        )

        if corners is not None:
            corner_kps = [
                cv.KeyPoint(x=float(c[0][0]), y=float(c[0][1]), size=20)
                for c in corners
            ]
            keypoints_sift.extend(corner_kps)
            keypoints_sift, descriptors_sift = self.sift_detector.compute(
                img_object, keypoints_sift
            )

        self.keypoints_sift = keypoints_sift
        self.descriptors_sift = descriptors_sift

    def detect(self, frame, force_redetect=False):
        """
        Detect the template in a camera frame.

        Args:
            frame (numpy.ndarray): Grayscale camera frame
            force_redetect (bool): Force re-detection even if tracking is good

        Returns:
            tuple: (success, H, None) where success is bool and H is homography matrix
        """
        # Handle manual re-detection trigger
        if force_redetect:
            logger.info("Manual re-detection triggered")
            self.requires_homography = True
            self.H = None
            self.tracking_quality_history.clear()

        # Automatic re-detection triggers
        if not self.requires_homography:
            self.frames_since_last_detection += 1

            # Periodic validation
            if self.frames_since_last_detection >= self.REDETECT_INTERVAL:
                logger.debug(f"Periodic validation after {self.frames_since_last_detection} frames")
                self._validate_tracking(frame)

            # Quality degradation check
            if len(self.tracking_quality_history) >= 3:
                avg_quality = np.mean(self.tracking_quality_history[-3:])
                if avg_quality < self.MIN_TRACKING_QUALITY:
                    logger.warning(f"Tracking degraded (avg: {avg_quality:.1f}), re-detecting")
                    self.requires_homography = True
                    self.H = None
                    self.tracking_quality_history.clear()

        # Return existing homography if tracking is good
        if not self.requires_homography:
            return True, self.H, None

        # Try SIFT matching first
        success, H = self._match_sift(frame)
        if success:
            self.frames_since_last_detection = 0
            return True, H, None

        # Fallback to ORB matching
        success, H = self._match_orb(frame)
        if success:
            self.frames_since_last_detection = 0
            return True, H, None

        # Return last known homography if available
        if self.H is not None:
            return True, self.H, None
        else:
            return False, None, None

    def _validate_tracking(self, frame):
        """Validate current homography quality using feature matching."""
        keypoints_scene, descriptors_scene = self.sift_detector.detectAndCompute(frame, None)

        if descriptors_scene is None or len(keypoints_scene) < 4:
            self.requires_homography = True
            self.H = None
            return

        try:
            # Reuse FLANN matcher
            if self.flann_sift is None:
                FLANN_INDEX_KDTREE = 1
                matcher = cv.FlannBasedMatcher(dict(algorithm=FLANN_INDEX_KDTREE, trees=SIFTConfig.FLANN_TREES),
                                               dict(checks=SIFTConfig.FLANN_CHECKS))
            else:
                matcher = self.flann_sift
            knn_matches = matcher.knnMatch(self.descriptors_sift, descriptors_scene, k=2)

            # Lowe's ratio test
            good_matches = []
            for match_pair in knn_matches:
                if len(match_pair) == 2:
                    m, n = match_pair
                    if m.distance < SIFTConfig.RATIO_THRESH * n.distance:
                        good_matches.append(m)

            match_count = len(good_matches)
            self.tracking_quality_history.append(match_count)
            if len(self.tracking_quality_history) > 10:
                self.tracking_quality_history.pop(0)

            if self.debug:
                logger.debug(f"Validation: {match_count} matches")

            if match_count < self.MIN_TRACKING_QUALITY:
                logger.warning("Validation failed: triggering re-detection")
                self.requires_homography = True
                self.H = None
            else:
                self.frames_since_last_detection = 0

        except Exception as e:
            logger.error(f"Validation error: {e}")
            self.requires_homography = True
            self.H = None

    def _match_sift(self, frame):
        """SIFT-based feature matching."""
        keypoints_scene, descriptors_scene = self.sift_detector.detectAndCompute(frame, None)

        if descriptors_scene is None or len(keypoints_scene) < 4:
            return False, None

        # Reuse FLANN matcher
        if self.flann_sift is None:
            FLANN_INDEX_KDTREE = 1
            matcher = cv.FlannBasedMatcher(dict(algorithm=FLANN_INDEX_KDTREE, trees=SIFTConfig.FLANN_TREES),
                                           dict(checks=SIFTConfig.FLANN_CHECKS))
        else:
            matcher = self.flann_sift
        knn_matches = matcher.knnMatch(self.descriptors_sift, descriptors_scene, k=2)

        # Lowe's ratio test
        good_matches = []
        for match_pair in knn_matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < SIFTConfig.RATIO_THRESH * n.distance:
                    good_matches.append(m)

        if self.debug:
            logger.debug(f"SIFT good matches: {len(good_matches)}")

        if len(good_matches) < 4:
            return False, None

        return self._compute_homography(good_matches, self.keypoints_sift,
                                       keypoints_scene, "SIFT")

    def _match_orb(self, frame):
        """ORB-based feature matching as fallback."""
        keypoints_scene, descriptors_scene = self.orb_detector.detectAndCompute(frame, None)

        if descriptors_scene is None or len(keypoints_scene) < 4:
            return False, None

        # Reuse BF matcher
        matcher = self.bf_orb
        matches = matcher.knnMatch(self.descriptors_orb, descriptors_scene, k=2)

        # Ratio test
        good_matches = []
        for match_pair in matches:
            if len(match_pair) == 2:
                m, n = match_pair
                if m.distance < 0.75 * n.distance:
                    good_matches.append(m)

        if self.debug:
            logger.debug(f"ORB good matches: {len(good_matches)}")

        if len(good_matches) < 4:
            return False, None

        return self._compute_homography(good_matches, self.keypoints_orb,
                                       keypoints_scene, "ORB")

    def _compute_homography(self, good_matches, keypoints_obj, keypoints_scene,
                           method_name):
        """Compute homography from matched keypoints."""
        obj = np.empty((len(good_matches), 2), dtype=np.float32)
        scene = np.empty((len(good_matches), 2), dtype=np.float32)

        for i in range(len(good_matches)):
            obj[i, 0] = keypoints_obj[good_matches[i].queryIdx].pt[0]
            obj[i, 1] = keypoints_obj[good_matches[i].queryIdx].pt[1]
            scene[i, 0] = keypoints_scene[good_matches[i].trainIdx].pt[0]
            scene[i, 1] = keypoints_scene[good_matches[i].trainIdx].pt[1]

        # MAGSAC++ for robust homography estimation
        H, mask_out = cv.findHomography(
            scene, obj, cv.USAC_MAGSAC,
            ransacReprojThreshold=SIFTConfig.RANSAC_REPROJ_THRESHOLD,
            confidence=SIFTConfig.RANSAC_CONFIDENCE,
            maxIters=SIFTConfig.RANSAC_MAX_ITERS
        )

        if H is None:
            return False, None

        total = int(np.sum(mask_out))
        if self.debug:
            logger.debug(f'{method_name} inlier count: {total}')

        if total >= self.MIN_INLIER_COUNT:
            self._update_homography(H, total, method_name)
            return True, H

        return False, None

    def _update_homography(self, H, inlier_count, method_name):
        """Update stored homography and compute projected rectangle."""
        self.H = H
        self.last_inlier_count = inlier_count
        self.requires_homography = False
        self.tracking_quality_history.append(inlier_count)
        if len(self.tracking_quality_history) > 10:
            self.tracking_quality_history.pop(0)

        # Compute projected rectangle corners (reuse precomputed template corners)
        try:
            H_inv = np.linalg.inv(self.H)
            pts = cv.perspectiveTransform(self.obj_corners, H_inv)
            self.last_rect_pts = pts
        except Exception as e:
            logger.error(f"Could not compute projected rectangle: {e}")
            self.last_rect_pts = None

        self.homography_updated = True
        if self.debug:
            logger.info(f"Homography locked using {method_name}")

    def quick_validate_position(self, scene_gray, min_matches=None, position_threshold=None):
        """
        Quick validation by checking if template position has changed.

        Args:
            scene_gray (numpy.ndarray): Grayscale camera frame
            min_matches (int): Minimum matches required (uses config default if None)
            position_threshold (float): Max position drift in pixels (uses config default if None)

        Returns:
            bool: True if position still valid, False if re-detection needed
        """
        if min_matches is None:
            min_matches = SIFTConfig.VALIDATION_MIN_MATCHES
        if position_threshold is None:
            position_threshold = SIFTConfig.VALIDATION_POSITION_THRESHOLD

        if self.last_rect_pts is None or self.H is None:
            return False

        # Run lightweight SIFT match
        keypoints_scene, descriptors_scene = self.sift_detector.detectAndCompute(
            scene_gray, None
        )

        if descriptors_scene is None or len(keypoints_scene) < 4:
            if self.debug:
                logger.debug("quick_validate_position: not enough scene keypoints")
            self.requires_homography = True
            self.last_rect_pts = None
            return False

        try:
            # Reuse quick FLANN matcher
            matcher = self.flann_sift_quick if self.flann_sift_quick is not None else self.flann_sift
            if matcher is None:
                FLANN_INDEX_KDTREE = 1
                matcher = cv.FlannBasedMatcher(dict(algorithm=FLANN_INDEX_KDTREE, trees=6),
                                               dict(checks=50))
            knn_matches = matcher.knnMatch(self.descriptors_sift, descriptors_scene, k=2)

            good_matches = []
            for pair in knn_matches:
                if len(pair) == 2:
                    m, n = pair
                    if m.distance < SIFTConfig.RATIO_THRESH * n.distance:
                        good_matches.append(m)

            match_count = len(good_matches)
            if self.debug:
                logger.debug(f"quick_validate_position: found {match_count} matches")

            if match_count < min_matches:
                if self.debug:
                    logger.debug("quick_validate_position: insufficient matches")
                self.requires_homography = True
                self.last_rect_pts = None
                return False

            # Compute test homography
            obj = np.empty((len(good_matches), 2), dtype=np.float32)
            scene = np.empty((len(good_matches), 2), dtype=np.float32)

            for i in range(len(good_matches)):
                obj[i, 0] = self.keypoints_sift[good_matches[i].queryIdx].pt[0]
                obj[i, 1] = self.keypoints_sift[good_matches[i].queryIdx].pt[1]
                scene[i, 0] = keypoints_scene[good_matches[i].trainIdx].pt[0]
                scene[i, 1] = keypoints_scene[good_matches[i].trainIdx].pt[1]

            H_test, _ = cv.findHomography(scene, obj, cv.RANSAC,
                                         ransacReprojThreshold=8.0)

            if H_test is None:
                if self.debug:
                    logger.debug("quick_validate_position: could not compute test homography")
                self.requires_homography = True
                self.last_rect_pts = None
                return False

            # Compare projected corners (reuse precomputed)
            h_t, w_t = self.template_shape  # kept if needed elsewhere
            H_test_inv = np.linalg.inv(H_test)
            new_pts = cv.perspectiveTransform(self.obj_corners, H_test_inv)

            old_pts = self.last_rect_pts.reshape(-1, 2)
            new_pts_flat = new_pts.reshape(-1, 2)

            distances = np.linalg.norm(old_pts - new_pts_flat, axis=1)
            avg_distance = np.mean(distances)
            max_distance = np.max(distances)

            if self.debug:
                logger.debug(f"quick_validate_position: corner movement - "
                           f"avg: {avg_distance:.1f}px, max: {max_distance:.1f}px")

            if max_distance > position_threshold:
                if self.debug:
                    logger.debug("quick_validate_position: template position changed")
                self.requires_homography = True
                self.last_rect_pts = None
                return False

            if self.debug:
                logger.debug("quick_validate_position: validation PASSED")
            return True

        except Exception as e:
            logger.error(f"quick_validate_position error: {e}")
            self.requires_homography = True
            self.last_rect_pts = None
            return False

    def get_tracking_status(self):
        """Get tracking status string for display."""
        if self.requires_homography:
            return "SEARCHING FOR MAP"
        else:
            avg_quality = (np.mean(self.tracking_quality_history)
                          if self.tracking_quality_history
                          else self.last_inlier_count)
            return f"TRACKING (Q:{avg_quality:.0f} Age:{self.frames_since_last_detection})"

