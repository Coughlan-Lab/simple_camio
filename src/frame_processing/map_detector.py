# type: ignore
import time
from typing import Optional, Tuple

import cv2
import numpy as np
import numpy.typing as npt

from src.config import config
from src.modules_repository import Module


class MapDetector(Module):
    DETECTION_INTERVAL = 2  # seconds
    RATIO_THRESH = 0.75

    def __init__(self) -> None:
        super().__init__()

        img_template = cv2.imread(config.template_path, cv2.IMREAD_GRAYSCALE)
        self.map_shape = img_template.shape

        self.detector = cv2.SIFT_create()
        self.template_keypoints, self.template_descriptors = (
            self.detector.detectAndCompute(img_template, mask=None)
        )

        self.last_detection = 0.0, np.zeros((3, 3), dtype=np.float32)

    @property
    def homography(self) -> npt.NDArray[np.float32]:
        return self.last_detection[1]

    def detect(
        self, img: npt.NDArray[np.uint8]
    ) -> Tuple[Optional[npt.NDArray[np.float32]], npt.NDArray[np.uint8]]:
        if time.time() - self.last_detection[0] < self.DETECTION_INTERVAL:

            if self.homography is not None and config.debug:
                img = self.__draw_corners(img, self.last_detection[1])

            return self.homography, img

        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        keypoints, descriptors = self.detector.detectAndCompute(img_gray, None)
        matcher = cv2.DescriptorMatcher_create(cv2.DescriptorMatcher_FLANNBASED)

        try:
            knn_matches = matcher.knnMatch(self.template_descriptors, descriptors, 2)
        except:
            return None, img

        good_matches = list()
        for m, n in knn_matches:
            if m.distance < MapDetector.RATIO_THRESH * n.distance:
                good_matches.append(m)

        if len(good_matches) < 4:
            return None, img

        obj = np.empty((len(good_matches), 2), dtype=np.float32)
        scene = np.empty((len(good_matches), 2), dtype=np.float32)
        for i in range(len(good_matches)):
            # -- Get the keypoints from the good matches
            obj[i, 0] = self.template_keypoints[good_matches[i].queryIdx].pt[0]
            obj[i, 1] = self.template_keypoints[good_matches[i].queryIdx].pt[1]
            scene[i, 0] = keypoints[good_matches[i].trainIdx].pt[0]
            scene[i, 1] = keypoints[good_matches[i].trainIdx].pt[1]

        H, _ = cv2.findHomography(
            scene, obj, cv2.RANSAC, ransacReprojThreshold=8.0, confidence=0.995
        )

        self.last_detection = time.time(), H

        if H is not None and config.debug:
            img = self.__draw_corners(img, H)

        return H, img

    def __draw_corners(
        self, img: npt.NDArray[np.uint8], homography: npt.NDArray[np.float32]
    ) -> npt.NDArray[np.uint8]:
        inverted_homography = np.linalg.inv(homography)

        h, w = self.map_shape[:2]
        corners = np.float32([[0, 0], [0, h], [w, h], [w, 0]]).reshape(-1, 1, 2)
        projected_corners = cv2.perspectiveTransform(corners, inverted_homography)

        for i in range(len(projected_corners)):
            x, y = projected_corners[i][0]
            x, y = int(x), int(y)
            cv2.circle(img, (x, y), 8, (255, 255, 255), -1)
            cv2.circle(img, (x, y), 6, (0, 0, 0), -1)

        return img
