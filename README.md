# CamIO with LLM integration

## Environment setup:

This version of CamIO runs with Python 3.8. Once installed, the required packages can be set up with the following commands.</br>
If you are on an Apple Silicon machine, please follow the [Apple Silicon-specific instructions](#for-apple-silicon-machines) before running these commands.

```bash
# Required for the PyAudio library
brew install portaudio

# Create and activate a Python virtual environment
python3.8 -m venv camio-llm    # or python3, depending on your setup
cd camio-llm
source bin/activate

# Clone the repository
git clone https://github.com/Coughlan-Lab/simple_camio.git
mv simple_camio src
cd src
git switch llm

# Install Python libraries
pip install -r requirements.txt
```

### For Apple Silicon machines:

On Apple Silicon machines, the PyAudio library may not work natively and will throw an exception when imported. Therefore, it’s necessary to use the Intel version of Python.</br>
Here's how to set it up:

1. Verify if Rosetta is installed:

```bash
pkgutil --pkg-info com.apple.pkg.RosettaUpdateAuto
```

2. If Rosetta is not installed, run the following command to install it:

```bash
softwareupdate --install-rosetta
```

3. Enable Rosetta for your terminal:
   Go to Finder > Applications, make a copy of your preferred terminal (e.g., Terminal or iTerm), rename the copy, then right-click and select "Get Info". Check the box for "Open using Rosetta". Use this new terminal to run the following commands.

4. Install the Intel version of Homebrew:

```bash
arch -x86_64 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

(echo; echo 'eval "$(/usr/local/bin/brew shellenv)"') >> /Users/<YOUR USERNAME>/.zprofile
eval "$(/usr/local/bin/brew shellenv)"
```

5. Create an alias for Intel Homebrew:

```bash
echo 'alias ibrew="/usr/local/bin/brew"' >> ~/.zshrc
source ~/.zshrc
```

6. Install the Intel version of Python 3.8:

```bash
ibrew install python@3.8
```

7. Create an alias for Intel Python 3.8:

```bash
echo 'alias ipython3.8="/usr/local/bin/python3.8"' >> ~/.zshrc
source ~/.zshrc
```

Now, proceed with the general setup instructions from [Environment Setup](#environment-setup), replacing `python3.8` with `ipython3.8` and `brew` with `ibrew`.

## Running the code:

To run the code, simply run the following command:

```bash
python3.8 camio.py --model <path_to_model>
```

Root privileges may be required to run the code.

For a list of all available command line arguments, run:

```bash
python3.8 camio.py --help
```

## Keyboard shortcuts:

-   `q`: Quit the application
-   `Space`: Start/Stop LLM question recording
-   `Escape`: Stop TTS
-   `Enter`: Pause/Resume TTS
-   `n`: Disable navigation mode
-   `d`: Play map description
