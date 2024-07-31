import argparse
import time

import cv2
import pyglet.media

from src.audio import AmbientSoundPlayer, CamIOPlayer
from src.frame_processing import PoseDetector, SIFTModelDetector
from src.graph import Coords, Graph
from src.utils import *

# Model loading
parser = argparse.ArgumentParser(description="CamIO, with LLM integration")
parser.add_argument(
    "--model",
    help="Path to model json file.",
    default="models/UkraineMap/UkraineMap.json",
)
args = parser.parse_args()
model = load_map_parameters(args.model)


# Node network graph
graph = Graph(model["graph"])
buffer = Buffer(5)
min_corner, max_corner = graph.bounds

# Frame processing
model_detector = SIFTModelDetector(model["template_image"])
pose_detector = PoseDetector()

# Audio players
camio_player = CamIOPlayer(model)
camio_player.play_welcome()
crickets_player = AmbientSoundPlayer(model["crickets"])
heartbeat_player = AmbientSoundPlayer(model["heartbeat"])
heartbeat_player.set_volume(0.05)

# Video capture
cam_port = select_cam_port()
cap = cv2.VideoCapture(cam_port)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FOCUS, 0)
ok, frame = cap.read()
if not ok:
    print("No camera image returned.")
    exit(0)


camio_player.play_description()

timer = time.time() - 1
while cap.isOpened():

    cv2.imshow("CamIO", cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    ret, frame = cap.read()
    if not ret:
        print("No camera image returned.")
        break
    frame = frame.copy()

    waitkey = cv2.waitKey(1)
    if waitkey == 27 or waitkey == ord("q"):
        break

    # prev_time = timer
    # timer = time.time()
    # elapsed_time = timer - prev_time
    # print("current fps: " + str(1/elapsed_time))

    pyglet.clock.tick()
    pyglet.app.platform_event_loop.dispatch_posted_events()

    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    ok, rotation = model_detector.detect(frame_gray)

    if not ok or rotation is None:
        heartbeat_player.pause_sound()
        crickets_player.play_sound()
        continue
    crickets_player.pause_sound()

    gesture_position, gesture_status, frame = pose_detector.detect(frame, rotation)
    if gesture_position is None:
        heartbeat_player.pause_sound()
        continue
    heartbeat_player.play_sound()

    if gesture_status != "pointing":
        continue

    x = int(gesture_position[0])
    y = int(gesture_position[1])

    if min_corner[0] <= x < max_corner[0] and min_corner[1] <= y < max_corner[1]:
        print("Gesture detected at x: " + str(x) + " y: " + str(y))
        nearest_edge = graph.get_nearest_edge(Coords(x, y))
        buffer.add(nearest_edge)

        print("Nearest edge: " + str(nearest_edge))


cap.release()
cv2.destroyAllWindows()
heartbeat_player.pause_sound()
crickets_player.pause_sound()
camio_player.play_goodbye()
time.sleep(1)
