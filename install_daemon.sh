#!/bin/bash
# Quick installation script for Simple CamIO daemon on Raspberry Pi
# Usage: sudo bash install_daemon.sh

set -e  # Exit on error

echo "========================================"
echo "Simple CamIO Daemon Installation Script"
echo "========================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Error: This script must be run as root (use sudo)"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER="${SUDO_USER:-$USER}"
if [ "$ACTUAL_USER" = "root" ]; then
    echo "Warning: Running as root user. Consider running as a regular user with sudo."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Get installation directory
INSTALL_DIR="/home/${ACTUAL_USER}/simple_camio"
read -p "Installation directory [${INSTALL_DIR}]: " input_dir
if [ ! -z "$input_dir" ]; then
    INSTALL_DIR="$input_dir"
fi

# Check if directory exists
if [ ! -d "$INSTALL_DIR" ]; then
    echo "Error: Directory ${INSTALL_DIR} does not exist"
    echo "Please ensure Simple CamIO is installed first"
    exit 1
fi

# Check if service file exists
SERVICE_FILE="${INSTALL_DIR}/simple_camio.service"
if [ ! -f "$SERVICE_FILE" ]; then
    echo "Error: Service file not found at ${SERVICE_FILE}"
    exit 1
fi

echo ""
echo "Configuration:"
echo "  Installation directory: ${INSTALL_DIR}"
echo "  User: ${ACTUAL_USER}"
echo "  Service file: ${SERVICE_FILE}"
echo ""

# Confirm
read -p "Proceed with installation? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation cancelled"
    exit 0
fi

echo ""
echo "Step 1: Updating service file with correct paths..."

# Create a temporary service file with updated paths
TEMP_SERVICE="/tmp/simple_camio.service"
sed -e "s|/home/pi|/home/${ACTUAL_USER}|g" \
    -e "s|User=pi|User=${ACTUAL_USER}|g" \
    -e "s|Group=pi|Group=${ACTUAL_USER}|g" \
    "$SERVICE_FILE" > "$TEMP_SERVICE"

echo "Step 2: Unmasking service (if previously masked)..."
systemctl unmask simple_camio.service 2>/dev/null || true

echo "Step 3: Installing service file..."
cp "$TEMP_SERVICE" /etc/systemd/system/simple_camio.service
chmod 644 /etc/systemd/system/simple_camio.service
rm "$TEMP_SERVICE"

echo "Step 4: Reloading systemd daemon..."
systemctl daemon-reload

echo "Step 5: Enabling service for auto-start on boot..."
systemctl enable simple_camio.service

echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "The Simple CamIO service has been installed and enabled."
echo ""
echo "Useful commands:"
echo "  Start service:    sudo systemctl start simple_camio.service"
echo "  Stop service:     sudo systemctl stop simple_camio.service"
echo "  Restart service:  sudo systemctl restart simple_camio.service"
echo "  Check status:     sudo systemctl status simple_camio.service"
echo "  View logs:        sudo journalctl -u simple_camio.service -f"
echo "  Disable auto-start: sudo systemctl disable simple_camio.service"
echo ""
read -p "Would you like to start the service now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Starting Simple CamIO service..."
    systemctl start simple_camio.service
    sleep 2
    echo ""
    echo "Service status:"
    systemctl status simple_camio.service --no-pager
    echo ""
    echo "To view live logs, run: sudo journalctl -u simple_camio.service -f"
else
    echo ""
    echo "Service installed but not started."
    echo "Start it manually with: sudo systemctl start simple_camio.service"
fi

echo ""
echo "Installation complete!"
