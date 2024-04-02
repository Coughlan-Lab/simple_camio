# Simple CamIO GUI

Python graphical interface to CamIO.

## System requirements:

The application has currently been tested only on Windows; Mac support will be added in the future.

## Install:

Just run from the terminal:

```console
pip install -r requirements.txt
```

Python 3.8.19 is required.

## Usage:

```console
python main.py
```

## Differences with the main branch:

-   Here models are called "content", because the term is more user friendly.
-   All contents are stored in the content folder, that will be shipped with the gui executable: adding a content to this folder makes it available through the GUI.
-   Paths in the content json files must be relative to the content directory.
-   Each content json must have a name, a description and a preview fields; the preview is the 2D map for 2D contents or a rendering of the mesh for 3D contents.
-   Each content folder must contain a toPrint file that the user should print before using the model. For 2D contents it's a pdf, for 3Ds an obj file.
-   A calibration map is used only for calibration, to avoid doing the calibration with a 2D content even if the user has selected a 3D content.
-   The revised branch main code is stored in the model folder.

## How to build:

For Windows:

```console
pyinstaller --noconfirm --onefile --windowed --add-data "C:/Users/<USER NAME>/AppData/Local/Programs/Python/Python38/Lib/site-packages/mediapipe/modules/hand_landmark;mediapipe/modules/hand_landmark/" --add-data "C:/Users/<USER NAME>/AppData/Local/Programs/Python/Python38/Lib/site-packages/mediapipe/modules/palm_detection;mediapipe/modules/palm_detection/" --add-data "res;res/" main.py
```
