# Running Simple CamIO as a Daemon on Raspberry Pi

This guide explains how to run Simple CamIO in headless mode as a system daemon on Raspberry Pi or other Linux systems.

## Important: Headless Audio Setup

When running without X11 (no display server), Pyglet audio needs special configuration. Choose one of these methods:

### Method 1: Using xvfb (Virtual Display - Recommended)

Install xvfb (X virtual framebuffer):
```bash
sudo apt-get update
sudo apt-get install -y xvfb
```

Run with xvfb:
```bash
xvfb-run python simple_camio.py --headless
```

### Method 2: Set DISPLAY Environment Variable

If you have X11 running or PulseAudio configured:
```bash
export DISPLAY=:0
python simple_camio.py --headless
```

### Method 3: Use PulseAudio (Best for Production)

Ensure PulseAudio is running:
```bash
# Install PulseAudio if not present
sudo apt-get install -y pulseaudio

# Start PulseAudio for your user
pulseaudio --start

# Verify it's running
pulseaudio --check && echo "PulseAudio is running"
```

Then run with DISPLAY set:
```bash
export DISPLAY=:0
python simple_camio.py --headless
```

## Headless Mode

Simple CamIO now supports headless mode, which disables the display window and allows the application to run as a background service without requiring a display server (X11).

### Command Line Usage

Run Simple CamIO in headless mode:

```bash
python simple_camio.py --headless
```

Run with a specific map in headless mode:

```bash
python simple_camio.py --headless --input1 models/UkraineMap/UkraineMap.json
```

### Features in Headless Mode

- **No Display Window**: All cv.imshow() calls are skipped
- **No Display Thread**: Display thread is not created
- **Full Functionality**: Hand tracking, tap detection, and audio feedback work normally
- **Lower Resource Usage**: Reduced CPU/GPU usage without rendering
- **Daemon Compatible**: Can run as a systemd service

### Stopping Headless Mode

When running in headless mode:
- Press `Ctrl+C` to stop (SIGINT)
- Or send SIGTERM: `kill <pid>`
- The application will perform graceful shutdown

## Running as a Systemd Service

### 1. Installation

First, ensure Simple CamIO is installed and working:

```bash
# Clone the repository (if not already done)
cd /home/pi
git clone https://github.com/Coughlan-Lab/simple_camio.git
cd simple_camio

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Test headless mode
python simple_camio.py --headless
# Press Ctrl+C to stop
```

### 2. Configure the Service File

Edit the provided `simple_camio.service` file to match your installation:

```bash
nano simple_camio.service
```

Key settings to adjust:

- **User/Group**: Change from `pi` to your username if different
- **WorkingDirectory**: Update path if installed elsewhere
- **ExecStart**: Update paths to match your installation
- **Map Configuration**: Change `--input1` parameter to use your map

Example for user `myuser` with installation in `/opt/simple_camio`:

```ini
User=myuser
Group=myuser
WorkingDirectory=/opt/simple_camio
ExecStart=/opt/simple_camio/venv/bin/python /opt/simple_camio/simple_camio.py --headless --input1 /opt/simple_camio/models/UkraineMap/UkraineMap.json
```

### 3. Install the Service

Copy the service file to systemd directory:

```bash
sudo cp simple_camio.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/simple_camio.service
```

Reload systemd to recognize the new service:

```bash
sudo systemctl daemon-reload
```

### 4. Enable and Start the Service

Enable the service to start at boot:

```bash
sudo systemctl enable simple_camio.service
```

Start the service:

```bash
sudo systemctl start simple_camio.service
```

### 5. Managing the Service

Check service status:

```bash
sudo systemctl status simple_camio.service
```

View logs:

```bash
# Recent logs
sudo journalctl -u simple_camio.service -n 50

# Follow logs in real-time
sudo journalctl -u simple_camio.service -f

# Logs since last boot
sudo journalctl -u simple_camio.service -b
```

Stop the service:

```bash
sudo systemctl stop simple_camio.service
```

Restart the service:

```bash
sudo systemctl restart simple_camio.service
```

Disable auto-start:

```bash
sudo systemctl disable simple_camio.service
```

### 6. Troubleshooting

#### Pyglet Display Error (Cannot connect to "None")

**Error message:**
```
pyglet.display.xlib.NoSuchDisplayException: Cannot connect to "None"
```

**Cause:** Pyglet is trying to connect to X11 display for audio, but no display is available.

**Solution 1 - Use xvfb (Recommended):**
```bash
# Install xvfb
sudo apt-get install -y xvfb

# Run with xvfb
xvfb-run python simple_camio.py --headless
```

**Solution 2 - Set DISPLAY environment variable:**
```bash
export DISPLAY=:0
python simple_camio.py --headless
```

**Solution 3 - For systemd service:**
The provided `simple_camio.service` file already includes `xvfb-run`. Make sure xvfb is installed:
```bash
sudo apt-get install -y xvfb
```

#### Camera Access Issues

If the service can't access the camera, add your user to the `video` group:

```bash
sudo usermod -a -G video pi
# Reboot for changes to take effect
sudo reboot
```

#### Audio Issues

If audio doesn't work, ensure PulseAudio is running and the user has access:

```bash
# Check PulseAudio status
systemctl --user status pulseaudio

# Ensure PULSE_RUNTIME_PATH is correct in service file
# It should point to /run/user/$(id -u)/pulse/
```

For systems without PulseAudio, you may need to use ALSA directly or modify the audio configuration.

#### Permission Issues

If you get permission errors, check file ownership:

```bash
# Make sure your user owns the files
sudo chown -R pi:pi /home/pi/simple_camio

# Ensure execute permissions on Python script
chmod +x /home/pi/simple_camio/simple_camio.py
```

#### Python Environment Issues

If the virtual environment doesn't work in the service:

```bash
# Option 1: Use system Python instead
ExecStart=/usr/bin/python3 /home/pi/simple_camio/simple_camio.py --headless ...

# Option 2: Install packages system-wide
sudo pip3 install -r requirements.txt
```

#### Viewing Debug Logs

Enable debug logging by modifying `src/config.py`:

```python
# In simple_camio.py or config.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

Then restart the service and check logs:

```bash
sudo systemctl restart simple_camio.service
sudo journalctl -u simple_camio.service -f
```

## Configuration for Daemon Mode

When running as a daemon, you may want to adjust these settings in `src/config.py`:

```python
class CameraConfig:
    # Lower resolution for better performance on Raspberry Pi
    DEFAULT_WIDTH = 640
    DEFAULT_HEIGHT = 480
    
    # Disable threaded display (not needed in headless mode)
    USE_THREADED_DISPLAY = False
    
    # Enable threaded capture for better camera performance
    USE_THREADED_CAPTURE = True
    
    # Headless mode (set automatically by --headless flag)
    HEADLESS = False  # Will be True when using --headless
```

## Performance Optimization for Raspberry Pi

For best performance on Raspberry Pi:

1. **Use Lower Resolution**: 640x480 or 1280x720
2. **Enable Camera Threading**: `USE_THREADED_CAPTURE = True`
3. **Reduce Pose Processing Scale**: `POSE_PROCESSING_SCALE = 0.3` (or lower)
4. **Disable Unnecessary Features**: Turn off data collection if not needed

Example config for Raspberry Pi:

```python
class CameraConfig:
    DEFAULT_WIDTH = 640
    DEFAULT_HEIGHT = 480
    POSE_PROCESSING_SCALE = 0.3
    USE_THREADED_CAPTURE = True
    USE_THREADED_DISPLAY = False  # Not needed in headless

class TapDetectionConfig:
    COLLECT_TAP_DATA = False  # Disable unless actively training
```

## Automatic Startup

The service will automatically start at boot once enabled. To test:

```bash
# Reboot the system
sudo reboot

# After reboot, check if service is running
sudo systemctl status simple_camio.service
```

## Security Considerations

For production deployment, consider:

1. **Running as a dedicated user** (not root)
2. **Enabling security restrictions** in the service file:
   ```ini
   NoNewPrivileges=true
   PrivateTmp=true
   ReadOnlyDirectories=/
   ReadWriteDirectories=/home/pi/simple_camio/data
   ```
3. **Limiting camera access** to only the necessary user
4. **Using a firewall** if exposing any services

## Monitoring

To monitor the service health:

```bash
# Create a simple monitoring script
cat > /home/pi/check_camio.sh << 'EOF'
#!/bin/bash
if ! systemctl is-active --quiet simple_camio.service; then
    echo "Simple CamIO service is not running!"
    # Optionally: send notification or restart
    # sudo systemctl restart simple_camio.service
fi
EOF

chmod +x /home/pi/check_camio.sh

# Add to crontab to check every 5 minutes
crontab -e
# Add line:
# */5 * * * * /home/pi/check_camio.sh
```

## Alternative: Running with Screen or Tmux

If you prefer not to use systemd, you can use `screen` or `tmux`:

```bash
# Using screen
screen -dmS camio bash -c "cd /home/pi/simple_camio && source venv/bin/activate && python simple_camio.py --headless"

# Attach to see output
screen -r camio

# Detach: Press Ctrl+A then D

# Using tmux
tmux new -d -s camio "cd /home/pi/simple_camio && source venv/bin/activate && python simple_camio.py --headless"

# Attach to see output
tmux attach -t camio

# Detach: Press Ctrl+B then D
```

## Support

For issues specific to Raspberry Pi deployment:

1. Check the logs: `sudo journalctl -u simple_camio.service -n 100`
2. Test in foreground first: `python simple_camio.py --headless`
3. Verify camera access: `ls -l /dev/video*`
4. Check audio setup: `aplay -l` and `pactl info`

For general Simple CamIO issues, refer to the main [README.md](README.md) and [ARCHITECTURE.md](ARCHITECTURE.md).
