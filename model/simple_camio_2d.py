# mypy: ignore-errors
import os.path
import os
import pyglet
import time
import random
import numpy as np
from scipy import stats
from gtts import gTTS
import cv2 as cv


# The ModelDetector class is responsible for detecting the Aruco markers in
# the image that make up the model, and determining the pose of the model in
# the scene.


class ModelDetectorAruco:
    def __init__(self, model, intrinsic_matrix):
        # Parse the Aruco markers placement positions from the parameter file into a numpy array, and get the associated ids
        self.obj, self.list_of_ids = parse_aruco_codes(
            model["positioningData"]["arucoCodes"]
        )
        # Define aruco marker dictionary and parameters object to include subpixel resolution
        self.aruco_dict_scene = cv.aruco.Dictionary_get(
            get_aruco_dict_id_from_string(model["positioningData"]["arucoType"])
        )
        self.arucoParams = cv.aruco.DetectorParameters_create()
        self.arucoParams.cornerRefinementMethod = cv.aruco.CORNER_REFINE_SUBPIX
        self.intrinsic_matrix = intrinsic_matrix

    def detect(self, frame):
        # Detect the markers in the frame
        (corners, ids, rejected) = cv.aruco.detectMarkers(
            frame, self.aruco_dict_scene, parameters=self.arucoParams
        )
        scene, use_index = sort_corners_by_id(corners, ids, self.list_of_ids)
        if ids is None or not any(use_index):
            print("No markers found.")
            return False, None, None

        # Run solvePnP using the markers that have been observed to determine the pose
        retval, rvec, tvec = cv.solvePnP(
            self.obj[use_index, :], scene[use_index, :], self.intrinsic_matrix, None
        )
        return retval, rvec, tvec


# The InteractionPolicy class takes the position and determines where on the
# map it is, finding the color of the zone, if any, which is decoded into
# zone ID number. This zone ID number is filtered through a ring buffer that
# returns the mode. If the position is near enough to the plane (within 2cm)
# then the zone ID number is returned.
class InteractionPolicy2D:
    def __init__(self, model):
        self.prev_position = None
        self.model = model
        self.audio_level_up_key = model["audio_level_up_color"][0]*256*256+model["audio_level_up_color"][1]*256+model["audio_level_up_color"][2]
        self.scale_dictionary = model["scale_dictionary"]
        self.image_map_color = cv.imread(model["filename"], cv.IMREAD_COLOR)
        self.ZONE_FILTER_SIZE = 5
        self.Z_THRESHOLD = 2.0
        self.zone_filter = -1 * np.ones(self.ZONE_FILTER_SIZE, dtype=int)
        self.zone_filter_cnt = 0
        self.on_key = False

    # Sergio: we are currently returning the zone id also when the ring buffer is not full. Is this the desired behavior?
    # the impact is clearly minor, but conceptually I am not convinced that this is the right behavior.
    # Sergio (2): I have a concern about this function, I will discuss it in an email.
    def push_gesture(self, position):
        self.prev_position = position
        zone_color = self.get_zone(
            position, self.image_map_color, self.model["pixels_per_cm"]
        )
        self.zone_filter[self.zone_filter_cnt] = self.get_dict_idx_from_color(
            zone_color
        )
        self.zone_filter_cnt = (self.zone_filter_cnt + 1) % self.ZONE_FILTER_SIZE
        zone = stats.mode(self.zone_filter).mode
        if isinstance(zone, np.ndarray):
            zone = zone[0]
        if np.abs(position[2]) >= self.Z_THRESHOLD:
            zone = -1
        if str(zone) in self.scale_dictionary:
            return zone, self.scale_dictionary[str(zone)]
        if zone == self.audio_level_up_key:
            if not self.on_key:
                self.on_key = True
                return zone, 1
        else:
            self.on_key = False
        return zone, 0

    #Returns the distance from a position to the previous position
    def get_distance(self, position):
        return np.linalg.norm(self.prev_position[:3]-position)

    # Retrieves the zone of the point of interest on the map
    def get_zone(self, point_of_interest, img_map, pixels_per_cm):
        x = int(point_of_interest[0] * pixels_per_cm)
        y = int(point_of_interest[1] * pixels_per_cm)
        # map_copy = img_map.copy()
        if 0 <= x < img_map.shape[1] and 0 <= y < img_map.shape[0]:
            # cv.line(map_copy, (x-1, y), (x+1, y), (255, 0, 0), 2)
            # cv.line(map_copy, (x,y-1), (x,y+1), (255, 0, 0), 2)
            # cv.circle(map_copy, (x, y), 4, (255, 0, 0), 2)
            return img_map[y, x]  # , map_copy
        else:
            return [0, 0, 0]  # , map_copy

    # Paints an area of the map with the given color
    def make_new_hotspot(self, position, color):
        self.image_map_color = cv.circle(self.image_map_color, (int(position[0]), int(position[1])), 60, color, thickness=-1)
        cv.imwrite(self.model['filename'], self.image_map_color)

    # Returns the key of the dictionary in the dictionary of dictionaries that matches the color given
    def get_dict_idx_from_color(self, color):
        color_idx = 256 * 256 * color[2] + 256 * color[1] + color[0]
        return color_idx


class CamIOPlayer2D:
    def __init__(self, model):
        self.model = model
        self.prev_zone_name = ""
        self.prev_zone_moving = -1
        self.curr_zone_moving = -1
        self.current_zone = -1
        self.sound_files = {}
        self.hotspots = {}
        self.finelevelhotspots = {}
        self.player = pyglet.media.Player()
        self.blip_sound = pyglet.media.load(self.model["blipsound"], streaming=False)
        self.sparkle_sound = pyglet.media.load(self.model["sparkle"], streaming=False)
        self.enter_sound = pyglet.media.load(self.model["enter"], streaming=False)
        self.leave_sound = pyglet.media.load(self.model["leave"], streaming=False)
        self.enable_blips = False
        self.time_of_last_warning = 0
        if "map_description" in self.model:
            self.map_description = pyglet.media.load(
                self.model["map_description"], streaming=False
            )
            self.have_played_description = False
        else:
            self.have_played_description = True
        tts_warning = gTTS("Please use only one hand to point with.")
        with open("warning.mp3", 'wb') as fp:
            tts_warning.write_to_fp(fp)
        self.warning = pyglet.media.load("warning.mp3", streaming=False)
        os.remove("warning.mp3")
        self.welcome_message = pyglet.media.load(
            self.model["welcome_message"], streaming=False
        )
        self.goodbye_message = pyglet.media.load(
            self.model["goodbye_message"], streaming=False
        )
        self.loaded_text_descriptions = {}
        self.audiolayer = 0
        self.max_len_audiodescription = 1
        for hotspot in self.model["hotspots"]:
            key = (
                hotspot["color"][2]
                + hotspot["color"][1] * 256
                + hotspot["color"][0] * 256 * 256
            )
            self.hotspots.update({key: hotspot})
            self.sound_files[key] = list()
            self.max_len_audiodescription = max(self.max_len_audiodescription, len(hotspot["textDescription"]))
            for text_description in hotspot["textDescription"]:
                if text_description in self.loaded_text_descriptions:
                    self.sound_files[key].append(self.loaded_text_descriptions[text_description])
                else:
                    print(text_description)
                    tts = gTTS(text_description)
                    with open("hello.mp3", 'wb') as fp:
                        tts.write_to_fp(fp)
                    self.loaded_text_descriptions[text_description] = pyglet.media.load('hello.mp3', streaming=False)
                    os.remove("hello.mp3")
                    self.sound_files[key].append(self.loaded_text_descriptions[text_description])
        for hotspot in self.model["fine-level hotspots"]:
            key =  ( hotspot["color"][2] + hotspot["color"][1] * 256 + hotspot["color"][0] * 256 * 256)
            new_list = list()
            for streetside in hotspot['buildings']:
                new_dict = dict()
                for text_description in streetside:
                    key_coords = tuple(streetside[text_description])
                    new_color = self.add_new_hotspot(text_description)
                    new_key = new_color[2]*256*256 + new_color[1]*256 + new_color[0]
                    new_dict.update({key_coords:new_key})
                new_list.append(new_dict)
            self.finelevelhotspots.update({key:new_list})

    def get_new_key(self):
        new_color = [random.randint(1,254),random.randint(1,254),random.randint(1,254)]
        new_key = new_color[2] *256*256 + new_color[1] * 256 + new_color[0]
        while new_key in self.sound_files:
            new_color = [random.randint(1,254),random.randint(1,254),random.randint(1,254)]
            new_key = new_color[2] *256*256 + new_color[1] * 256 + new_color[0]
        return new_color, new_key

    def add_new_hotspot(self, text_description):
        new_color, new_key = self.get_new_key()
        new_hotspot = dict()
        new_hotspot['color'] = [new_color[2], new_color[1], new_color[0]]
        new_hotspot['textDescription'] = [text_description]
        self.model['hotspots'].append(new_hotspot)
        self.sound_files[new_key] = list()
        self.hotspots[new_key] = new_hotspot
        if text_description in self.loaded_text_descriptions:
            self.sound_files[new_key].append(self.loaded_text_descriptions[text_description])
        else:
            tts = gTTS(text_description)
            with open("hello.mp3", 'wb') as fp:
                tts.write_to_fp(fp)
            self.loaded_text_descriptions[text_description] = pyglet.media.load('hello.mp3', streaming=False)
            os.remove("hello.mp3")
            self.sound_files[new_key].append(self.loaded_text_descriptions[text_description])
        return new_color

    def get_fine_hotspot(self, zone_id, streetside, gesture_loc):
        best_dist = 10000000
        if zone_id not in self.finelevelhotspots:
            return zone_id
        for key_pair in self.finelevelhotspots[zone_id][streetside]:
            dist = np.sqrt((key_pair[0]-gesture_loc[0])**2+(key_pair[1]-gesture_loc[1])**2)
            if dist < best_dist:
                best_dist = dist
                best_pair = key_pair
        if best_dist < 50:
            return self.finelevelhotspots[zone_id][streetside][best_pair]
        else:
            return -1

    def play_description(self):
        if not self.have_played_description:
            self.player = self.map_description.play()
            self.have_played_description = True

    def pause(self):
        self.player.delete()

    def play_welcome(self):
        self.welcome_message.play()

    def play_goodbye(self):
        self.goodbye_message.play()

    def play_sparkle(self):
        self.sparkle_sound.play()

    def play_enter(self):
        self.enter_sound.play()

    def play_leave(self):
        self.leave_sound.play()

    def play_warning(self):
        if time.time() - self.time_of_last_warning < 2:
            return
        self.time_of_last_warning = time.time()
        self.player.pause()
        self.player.delete()
        self.player = self.warning.play()

    def convey(self, zone, status, layer=0):
        if layer == 1:
            #zone = self.current_zone
            self.audiolayer += layer
            self.player.pause()
            self.player.delete()
            self.player = self.blip_sound.play()
            time.sleep(0.15)
        if status =="too_many":
            #self.play_warning()
            return
        if status == "moving" and not layer == 1:
            if (
                self.curr_zone_moving != zone
                and self.prev_zone_moving == zone
                and self.enable_blips
            ):
                if self.player.playing:
                    self.player.delete()
                try:
                    self.player = self.blip_sound.play()
                except BaseException:
                    print(
                        "Exception raised. Cannot play sound. Please restart the application."
                    )
                self.curr_zone_moving = zone
            self.prev_zone_moving = zone
            # self.prev_zone_name = None
            return
        if zone not in self.hotspots:
            self.prev_zone_name = None
            return
        zone_name = self.hotspots[zone]["textDescription"]
        if self.prev_zone_name != zone_name or layer == 1:
            if not layer:
                self.audiolayer = 0
            self.player.pause()
            self.player.delete()
            if zone in self.sound_files:
                self.current_zone = zone
                sound = self.sound_files[zone][self.audiolayer % len(self.sound_files[zone])]
                try:
                    self.player = sound.play()
                except BaseException:
                    print("Exception raised. Cannot play sound. Please restart the application.")
            self.prev_zone_name = zone_name

    def interpolate_point(self, zone_id, proportion):
        pt1 = self.hotspots[zone_id]['points'][0]
        pt2 = self.hotspots[zone_id]['points'][1]
        if pt1[0] == pt2[0]:
            if pt1[1] > pt2[1]:
                pt_hold = pt2
                pt2 = pt1
                pt1 = pt_hold
        elif pt1[0] > pt2[0]:
            pt_hold = pt2
            pt2 = pt1
            pt1 = pt_hold
        delta_x = pt2[0] - pt1[0]
        delta_y = pt2[1] - pt1[1]
        interpolated_pt = np.zeros((3,1), dtype=np.float32)
        interpolated_pt[0] = pt1[0] + proportion * delta_x
        interpolated_pt[1] = pt1[1] + proportion * delta_y
        return interpolated_pt

# Function to sort corners by id based on the order specified in the id_list,
# such that the scene array matches the obj array in terms of aruco marker ids
# and the appropriate corners.
def sort_corners_by_id(corners, ids, id_list):
    use_index = np.zeros(len(id_list) * 4, dtype=bool)
    scene = np.empty((len(id_list) * 4, 2), dtype=np.float32)
    for i in range(len(corners)):
        id = ids[i, 0]
        if id in id_list:
            corner_num = id_list.index(id)
            for j in range(4):
                use_index[4 * corner_num + j] = True
                scene[4 * corner_num + j, :] = corners[i][0][j]
    return scene, use_index


# Parses the list of aruco codes and returns the 2D points and ids
def parse_aruco_codes(list_of_aruco_codes):
    obj_array = np.empty((len(list_of_aruco_codes) * 4, 3), dtype=np.float32)
    ids = []
    for cnt, aruco_code in enumerate(list_of_aruco_codes):
        for i in range(4):
            obj_array[cnt * 4 + i, :] = aruco_code["position"][i]
        ids.append(aruco_code["id"])
    return obj_array, ids


# Returns the dictionary code for the given string
def get_aruco_dict_id_from_string(aruco_dict_string):
    if aruco_dict_string == "DICT_4X4_50":
        return cv.aruco.DICT_4X4_50
    elif aruco_dict_string == "DICT_4X4_100":
        return cv.aruco.DICT_4X4_100
    elif aruco_dict_string == "DICT_4X4_250":
        return cv.aruco.DICT_4X4_250
    elif aruco_dict_string == "DICT_4X4_1000":
        return cv.aruco.DICT_4X4_1000
    elif aruco_dict_string == "DICT_5X5_50":
        return cv.aruco.DICT_5X5_50
    elif aruco_dict_string == "DICT_5X5_100":
        return cv.aruco.DICT_5X5_100
    elif aruco_dict_string == "DICT_5X5_250":
        return cv.aruco.DICT_5X5_250
