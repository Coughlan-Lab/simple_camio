# mypy: ignore-errors
import numpy as np
import time
from .frame_processor import FrameProcessor
from ..simple_camio_mp import PoseDetectorMP, SIFTModelDetectorMP
from ..simple_camio_3d import SIFTModelDetector
from ..simple_camio_2d import CamIOPlayer2D, InteractionPolicy2D
import cv2


class FingerSift2DFP(FrameProcessor):

    def get_audio_player(self):
        return CamIOPlayer2D(self.content.as_dict())

    def get_model_detector(self):
        return SIFTModelDetectorMP(self.content.as_dict())

    def get_interaction_policy(self):
        return InteractionPolicy2D(self.content.as_dict())

    def get_pose_detector(self):
        return PoseDetectorMP(self.content.as_dict())

    def process(self, img: np.ndarray) -> np.ndarray:
        img = super().process(img)
        tic = time.time()
        is_slider = False
        if self.frame_count == 0:
            self.model_detector.requires_homography = True
        self.frame_count = (self.frame_count + 1) % 100
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ok, rotation, translation = self.model_detector.detect(img_gray)
        if not ok:
            self.heartbeat_player.pause_sound()
            self.crickets_player.play_sound()
            return img
        self.crickets_player.pause_sound()


        gesture_loc, gesture_status, img, hand_results = self.pose_detector.detect(
            img, rotation, translation
        )

        for i in range(len(self.model_detector.mask_out)):
            if self.model_detector.mask_out[i]:
                cv2.circle(img, (int(self.model_detector.scene[i, 0]), int(self.model_detector.scene[i, 1])), 2, (0, 255, 0), 2)

        new_hotspot, _ = self.hotspot_constructor.detect(hand_results, img)
        if new_hotspot:
            self.hotspot_constructor.add_hotspot(gesture_loc, self.content)

        # layer_change, dist = self.layered_audio.detect(hand_results, img)
        # if dist:
        #     cv2.putText(img, str(dist), (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 2, cv2.LINE_AA)

        if gesture_loc is None:
            self.heartbeat_player.pause_sound()
            self.finger_count = 0
            return img
        self.heartbeat_player.play_sound()

        self.xlist.append(gesture_loc[0])
        self.ylist.append(gesture_loc[1])
        print(np.std(self.xlist), np.std(self.ylist))
        gesture_loc = gesture_loc / self.interaction[0].model['pixels_per_cm']
        if gesture_status == "too_many":
            zone_id, layer_change = self.interaction[0].push_gesture(gesture_loc)
            zone_id_1, layer_change_1 = self.interaction[1].push_gesture(gesture_loc[3:])
            if layer_change == 1:
                zone_id = zone_id_1
                gesture_status = "pointing"
            if layer_change_1 == 1:
                layer_change = layer_change_1
                gesture_status = "pointing"
            self.finger_count = 2
            if 1 > abs(layer_change) > 0:
                is_slider = True
                zone_id = zone_id_1
                layer_change_1 = layer_change
            if 1 > abs(layer_change_1) > 0 or is_slider:
                is_slider = True
                gesture_status = "pointing"
                if zone_id in self.audio_player.hotspots:
                    if len(self.audio_player.hotspots[zone_id]['points']) > 1:
                        gesture_loc = self.audio_player.interpolate_point(zone_id, abs(layer_change))
                        zone_id = self.audio_player.get_fine_hotspot(zone_id, gesture_loc)
        else:
            if self.finger_count == 2:
                if self.interaction[0].get_distance(gesture_loc) > self.interaction[1].get_distance(gesture_loc):
                    temp_hold = self.interaction[0]
                    self.interaction[0] = self.interaction[1]
                    self.interaction[1] = temp_hold
            zone_id, layer_change = self.interaction[0].push_gesture(gesture_loc)
            self.finger_count = 1

        if not self.slider_flag:
            if is_slider:
                self.slider_flag = True
                self.audio_player.play_enter()
        else:
            if not is_slider:
                self.slider_flag = False
                self.audio_player.play_leave()

        if zone_id in self.audio_player.hotspots:
            text = self.audio_player.hotspots[zone_id]['textDescription'][self.audio_player.audiolayer%len(self.audio_player.hotspots[zone_id]['textDescription'])]
            col = (0, 255, 0)
        else:
            text = str(zone_id)
            col = (0,0,255)
        cv2.putText(img, text, (10, 560), cv2.FONT_HERSHEY_SIMPLEX, 2, col, 2, cv2.LINE_AA)
        self.audio_player.convey(zone_id, gesture_status, layer_change)
        toc = time.time()
        print(f'It took {toc - tic} seconds, with framerate of {1 / (toc - tic)}')
        print(f'big loop was {toc - self.timer}')
        self.timer = toc
        return img
