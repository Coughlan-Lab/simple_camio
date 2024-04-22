# mypy: ignore-errors
import os.path
import pyglet
import numpy as np
from scipy import stats
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
        self.model = model
        self.image_map_color = cv.imread(model["filename"], cv.IMREAD_COLOR)
        self.ZONE_FILTER_SIZE = 10
        self.Z_THRESHOLD = 2.0
        self.zone_filter = -1 * np.ones(self.ZONE_FILTER_SIZE, dtype=int)
        self.zone_filter_cnt = 0

    # Sergio: we are currently returning the zone id also when the ring buffer is not full. Is this the desired behavior?
    # the impact is clearly minor, but conceptually I am not convinced that this is the right behavior.
    # Sergio (2): I have a concern about this function, I will discuss it in an email.
    def push_gesture(self, position):
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
        if np.abs(position[2]) < self.Z_THRESHOLD:
            return zone
        else:
            return -1

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
        self.sound_files = {}
        self.hotspots = {}
        self.player = pyglet.media.Player()
        self.blip_sound = pyglet.media.load(self.model["blipsound"], streaming=False)
        self.enable_blips = False
        if "map_description" in self.model:
            self.map_description = pyglet.media.load(
                self.model["map_description"], streaming=False
            )
            self.have_played_description = False
        else:
            self.have_played_description = True
        self.welcome_message = pyglet.media.load(
            self.model["welcome_message"], streaming=False
        )
        self.goodbye_message = pyglet.media.load(
            self.model["goodbye_message"], streaming=False
        )
        for hotspot in self.model["hotspots"]:
            key = (
                hotspot["color"][2]
                + hotspot["color"][1] * 256
                + hotspot["color"][0] * 256 * 256
            )
            self.hotspots.update({key: hotspot})
            self.sound_files[key] = list()
            for audio_description in hotspot["audioDescription"]:
                if os.path.exists(audio_description):
                    self.sound_files[key].append(pyglet.media.load(
                        audio_description, streaming=False
                    )
                    )
            else:
                print("warning. file not found:" + hotspot["audioDescription"])

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

    def convey(self, zone, status, layer=0):
        if status == "moving":
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
        if self.prev_zone_name != zone_name:
            # if self.player.playing:
            #     self.player.pause()
            self.player.pause()
            self.player.delete()
            if zone in self.sound_files:
                sound = self.sound_files[zone][min(layer, len(self.sound_files[zone])-1)]
                try:
                    self.player = sound.play()
                except BaseException:
                    print(
                        "Exception raised. Cannot play sound. Please restart the application."
                    )
            self.prev_zone_name = zone_name


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
