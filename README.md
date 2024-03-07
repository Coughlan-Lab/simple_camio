Simple CamIO

Requirements: To run Simple CamIO, one needs to set up several things. 

- Firstly, in 2D mode, we require a printed map with Aruco markers in the corners, as in map_with_aruco.pdf. The markers should be from the DICT_4X4_50 dictionary, with ids 0-3, placed in positions as specified by the position element of the arucoCodes list in positioningData as defined by the input json file.  

- Secondly, in 2D mode, a digital version of the map that represents zones with a unique index, as in zone_map.png, and this filename should be specified in the element "filename" of the model dictionary of the input json file. The precise resolution of the map should be specified in the element pixels_per_cm (in units of pixels per cm) in the model dictionary, such that it matches the printed version. 

- In 3D mode, we require a physical 3D map and the wavefront OBJ file that describes it, as well as a template image of the surrounding features to the physical 3D map, and the relation between them.
  
- The camera should be calibrated and the calibration parameters should be saved in the camera_parameters.json file created by using simple_calibration.py. Otherwise they are specified in simple_camio.py by the variables focal_length_x, focal_length_y, camera_center_x, camera_center_y. Calibration parameters can be estimated using simple_calibration.py (described below).  Distortion parameters are also settable via the variable distortion (although these can safely be left to zero, assuming little distortion). 

- For regular 2D and 3D mode (non-mediapipe version), a pointer needs to be printed and cut out, using the pattern found in marker_pointer.pdf (printed at 300 dpi, such that the Aruco marker is exactly 3cm).

- Sound files, as named in the hotspots dictionary in the supplied json file, should be placed in the MP3 folder. The hotspots dictionary maps the zone index (from the zone map) to the sound file in the 2D case, and in the 3D case there is a mapping between the zone label from the wavefront OBJ file to the sound file in the CSV file specified by "soundfile_mapping" in the supplied json file.

- Python 3.8 installed with opencv, numpy, scipy, mediapipe, and pyglet libraries (most of which can be installed through Anaconda, except mediapipe and pyglet which need to be installed via pip). The required library versions are specified in the requirements.txt file.

For best performance, we recommend the camera sit above the map to get a fronto-parallel view as much as possible. The camera should have an unobstructed view of the 4 Aruco markers on the map, and the pointer should be held such that the camera can clearly view the marker.

To run, simply run the simple_camio.py script as "python simple_camio.py --input1 \<json file\>" where \<json file\> is the location of the json file containing the model parameters, such as models/UkraineMap/UkraineMap.json. 

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
12. Again, from the terminal type and enter "pip install --user mediapipe".


--------------------------------------------------
How to estimate calibration parameters using simple_calibration.py:

1. Print the pattern from map_with_aruco.pdf. Should be printed at 300dpi.
2. Plug in the camera (if using external camera).
3. Run "python simple_calibration.py --input1 models/UkraineMap/UkraineMap.json".
4. Place the target pattern in front of the camera, so all markers are visible by the camera. Hold the paper against a flat surface, if possible, and hold at an angle as shown in the template image overlay on the screen. Try to match the orientation of the template image.
5. When all markers are visible and approximately matching the template image, press the 'g' key.  The calibration info should then be printed to the console. It includes focal_length_x, focal_length_y, camera_center_x, and camera_center_y.
6. Calibration info will be saved to file: camera_parameters.json.


--------------------------------------------------
In case the code won't run from PyCharm, try running it through the Anaconda terminal:

1. Open Anaconda, select Environments tab.
2. From the camio environment, click the green circle and select Open Terminal.
3. Navigate to where simple_camio was installed.
4. Run "python simple_camio.py".
