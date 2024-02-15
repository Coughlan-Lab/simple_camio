Simple CamIO

Requirements: To run Simple CamIO, one needs to set up several things. 

-Firstly, a printed map with Aruco markers in the corners, as in map_with_aruco.pdf. The markers should be from the DICT_4X4_50 dictionary, with ids 0-3, placed in positions as specified in map_parameters.py.  

-Secondly, a digital version of the map that represents zones with a different index, as in zone_map.png, and this filename should be specified in the argument as input1. The precise resolution of the map should be specified in the variable pixels_per_cm_obj (in units of pixels per cm) in simple_camio.py, such that it matches the printed version. 

-The camera should be calibrated and the calibration parameters should be saved in the camera_parameters.pkl file created by using simple_calibration.py. Otherwise they are specified in simple_camio.py by the variables focal_length_x, focal_length_y, camera_center_x, camera_center_y. Calibration parameters can be estimated using simple_calibration.py (described below).  Distortion parameters are also settable via the variable distortion (although these can safely be left to zero, assuming little distortion). 

-A pointer needs to be printed and cut out, using the pattern found in marker_pointer.pdf (printed at 300 dpi, such that the Aruco marker is exactly 3cm).

-Sound files, as named in the sound_dict dictionary in map_parameters.py, should be placed in the sound_files folder. The dictionary maps the zone index (from the zone map) to the sound file.

-Setting the camera: if an external webcam is to be used, set use_external_cam to 1, otherwise use 0 for the laptop's internal camera (or if you get a camera out of bounds error).

-Python 3.8 installed with opencv, numpy, scipy, and pyglet libraries (most of which can be installed through Anaconda, except pyglet which needs to be installed via pip)

For best performance, we recommend the camera sit above the map to get a fronto-parallel view as much as possible. The camera should have an unobstructed view of the 4 Aruco markers on the map, and the pointer should be held such that the camera can clearly view the marker.

To run, simply run the simple_camio.py script.

__________________________________________________
How to install Python via Anaconda.
1. Download and install the Anaconda Navigator from https://www.anaconda.com/download.
2. Once opened, select Environments, and then create a new environment.
3. Call the new environment "camio" and select Package Python 3.8.17. Hit Create.
4. From the pulldown menu select All.
5. Search for 'opencv', select 'opencv' and 'py-opencv', version 4.6.0 and hit Apply.
7. Do the same for 'scipy' (1.10.1) and 'numpy' (1.24.3).
8. Then hit Home on the Anaconda Navigator and Launch (or Install) PyCharm Community.
9. In the Welcome to PyCharm window, select 'Get from VCS', make sure Git is selected for Version control and paste URL: https://github.com/rcrabb-ski/simple_camio.git. Proceed to check out the project.
10. In the bottom right of the window, it should say the version of Python and the environment name which should be Python 3.8 (camio).  If it is not, click it and hit "Interpreter settings" and under Python Interpreter select Python 3.8 (camio)--if there is not an option for Python 3.8 (camio) select Show All... (if there is still not an option for Python 3.8 (camio) then go back to step 2).
11. Select Terminal from the bottom row of tabs and here type and enter "pip install --upgrade --user pyglet==2.0.9".


--------------------------------------------------
How to estimate calibration parameters using simple_calibration.py:

1. Print the pattern from map_with_aruco.pdf. Should be printed at 300dpi.
2. Plug in the camera (if using external camera). If using an external camera, make sure to set value of use_external_camera to 1 on line 91 of simple_calibration.py.
3. Run simple_calibration.py.
4. Place the target pattern in front of the camera, so all markers are visible by the camera. Hold the paper against a flat surface, if possible, and hold at an angle as shown in the template image overlay on the screen. Try to match the orientation of the template image.
5. When all markers are visible and matching the template image, press the 'g' key.  The calibration info should then be printed to the console. It includes focal_length_x, focal_length_y, camera_center_x, and camera_center_y.
6. Calibration info will be saved to file: camera_parameters.json.


--------------------------------------------------
In case the code won't run from PyCharm, try running it through the Anaconda terminal:

1. Open Anaconda, select Environments tab.
2. From the camio environment, click the green circle and select Open Terminal.
3. Navigate to where simple_camio was installed.
4. Run "python simple_camio.py".
