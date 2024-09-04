import time
from typing import Optional

import cv2
import numpy as np
import numpy.typing as npt


class SIFTModelDetector:
    DETECTION_INTERVAL = 2  # seconds

    def __init__(self, template_filename: str) -> None:
        # Load the template image
        img_template = cv2.imread(template_filename, cv2.IMREAD_GRAYSCALE)

        # Detect SIFT keypoints
        self.detector = cv2.SIFT_create()
        self.keypoints_obj, self.descriptors_obj = self.detector.detectAndCompute(
            img_template, mask=None
        )

        self.last_detection = 0.0, np.zeros((3, 3), dtype=np.float32)

    def detect(self, frame: npt.NDArray[np.uint8]) -> Optional[npt.NDArray[np.float32]]:
        if time.time() - self.last_detection[0] < self.DETECTION_INTERVAL:
            return self.last_detection[1]

        keypoints_scene, descriptors_scene = self.detector.detectAndCompute(frame, None)
        matcher = cv2.DescriptorMatcher_create(cv2.DescriptorMatcher_FLANNBASED)
        try:
            knn_matches = matcher.knnMatch(self.descriptors_obj, descriptors_scene, 2)
        except:
            return None

        RATIO_THRESH = 0.75
        good_matches = list()
        for m, n in knn_matches:
            if m.distance < RATIO_THRESH * n.distance:
                good_matches.append(m)
        # print("There were {} good matches".format(len(good_matches)))

        # -- Localize the object
        if len(good_matches) < 4:
            return None

        obj = np.empty((len(good_matches), 2), dtype=np.float32)
        scene = np.empty((len(good_matches), 2), dtype=np.float32)
        for i in range(len(good_matches)):
            # -- Get the keypoints from the good matches
            obj[i, 0] = self.keypoints_obj[good_matches[i].queryIdx].pt[0]
            obj[i, 1] = self.keypoints_obj[good_matches[i].queryIdx].pt[1]
            scene[i, 0] = keypoints_scene[good_matches[i].trainIdx].pt[0]
            scene[i, 1] = keypoints_scene[good_matches[i].trainIdx].pt[1]

        # Compute homography and find inliers
        H, _ = cv2.findHomography(
            scene, obj, cv2.RANSAC, ransacReprojThreshold=8.0, confidence=0.995
        )

        self.last_detection = time.time(), H
        return H
