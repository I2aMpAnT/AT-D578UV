#!/bin/bash
#
# AT-D578UV RTL-SDR Scanner Setup Script
# For Raspberry Pi with NAS storage
# GMRS License: WSKW654
#
# This script sets up the scanner without interfering with existing services
#

set -e

echo "=================================================="
echo "AT-D578UV RTL-SDR Scanner Setup"
echo "=================================================="

# Configuration - MODIFY THESE FOR YOUR SYSTEM
NAS_MOUNT="/mnt/nas4"
RADIO_DIR="${NAS_MOUNT}/radio"
INSTALL_DIR="/opt/at-d578uv-scanner"
SERVICE_USER="pi"  # Change if running as different user

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root for system-level installs
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_warn "Not running as root. Some features may require sudo."
    fi
}

# Check NAS mount
check_nas() {
    log_info "Checking NAS mount..."
    if mountpoint -q "$NAS_MOUNT"; then
        log_info "NAS mounted at $NAS_MOUNT"
    else
        log_error "NAS not mounted at $NAS_MOUNT"
        log_info "Please ensure your NAS is mounted before continuing"
        exit 1
    fi
}

# Create directory structure on NAS
create_directories() {
    log_info "Creating directory structure on NAS..."

    mkdir -p "${RADIO_DIR}/recordings"
    mkdir -p "${RADIO_DIR}/transcriptions"
    mkdir -p "${RADIO_DIR}/logs"
    mkdir -p "${RADIO_DIR}/config"

    # Set permissions
    chown -R ${SERVICE_USER}:${SERVICE_USER} "${RADIO_DIR}" 2>/dev/null || true
    chmod -R 755 "${RADIO_DIR}"

    log_info "Created: ${RADIO_DIR}/"
    log_info "  - recordings/"
    log_info "  - transcriptions/"
    log_info "  - logs/"
    log_info "  - config/"
}

# Install system dependencies
install_dependencies() {
    log_info "Installing system dependencies..."

    sudo apt-get update

    # RTL-SDR tools
    sudo apt-get install -y rtl-sdr librtlsdr-dev

    # Audio processing
    sudo apt-get install -y sox libsox-fmt-all ffmpeg

    # Python
    sudo apt-get install -y python3 python3-pip python3-venv

    # Build tools (for some Python packages)
    sudo apt-get install -y build-essential libffi-dev

    log_info "System dependencies installed"
}

# Set up RTL-SDR permissions
setup_rtlsdr_permissions() {
    log_info "Setting up RTL-SDR permissions..."

    # Create udev rules for RTL-SDR
    sudo tee /etc/udev/rules.d/20-rtlsdr.rules > /dev/null << 'UDEV'
# RTL-SDR rules
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2832", MODE:="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", MODE:="0666"
UDEV

    # Blacklist the kernel DVB driver (conflicts with RTL-SDR)
    sudo tee /etc/modprobe.d/blacklist-rtlsdr.conf > /dev/null << 'BLACKLIST'
# Blacklist DVB-T driver to allow RTL-SDR
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
BLACKLIST

    sudo udevadm control --reload-rules
    sudo udevadm trigger

    log_info "RTL-SDR permissions configured"
    log_warn "You may need to unplug and replug your RTL-SDR device"
}

# Create Python virtual environment
setup_python_env() {
    log_info "Setting up Python virtual environment..."

    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"

    python3 -m venv venv
    source venv/bin/activate

    pip install --upgrade pip
    pip install flask flask-socketio pyserial
    pip install pycryptodome numpy

    # Whisper for transcription (optional, takes time on Pi)
    log_info "Installing Whisper (this may take a while on Pi)..."
    pip install openai-whisper || log_warn "Whisper install failed - transcription will be disabled"

    deactivate

    log_info "Python environment ready at ${INSTALL_DIR}/venv"
}

# Copy application files
copy_application() {
    log_info "Copying application files..."

    # Assuming files are in current directory or specified location
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    cp "${SCRIPT_DIR}/rtl_scanner.py" "${INSTALL_DIR}/"
    cp "${SCRIPT_DIR}/scanner_portal.py" "${INSTALL_DIR}/"
    cp "${SCRIPT_DIR}/scanner_config.json" "${INSTALL_DIR}/"
    cp "${SCRIPT_DIR}/DRN_channels.csv" "${INSTALL_DIR}/"

    mkdir -p "${INSTALL_DIR}/templates"
    cp "${SCRIPT_DIR}/templates/scanner.html" "${INSTALL_DIR}/templates/"

    mkdir -p "${INSTALL_DIR}/static"

    # Update config paths for NAS
    sed -i "s|/mnt/nas4|${NAS_MOUNT}|g" "${INSTALL_DIR}/scanner_config.json"

    log_info "Application files copied to ${INSTALL_DIR}"
}

# Create systemd service (runs on high port, no root needed)
create_service() {
    log_info "Creating systemd service..."

    sudo tee /etc/systemd/system/rtl-scanner.service > /dev/null << SERVICE
[Unit]
Description=AT-D578UV RTL-SDR Scanner Web Portal
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/scanner_portal.py
Restart=on-failure
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICE

    sudo systemctl daemon-reload

    log_info "Service created: rtl-scanner.service"
    log_info "To enable on boot: sudo systemctl enable rtl-scanner"
    log_info "To start now: sudo systemctl start rtl-scanner"
}

# Test RTL-SDR
test_rtlsdr() {
    log_info "Testing RTL-SDR device..."

    if rtl_test -t 2>&1 | grep -q "Found"; then
        log_info "RTL-SDR device detected!"
    else
        log_warn "No RTL-SDR device found. Please check connection."
    fi
}

# Print summary
print_summary() {
    echo ""
    echo "=================================================="
    echo "Setup Complete!"
    echo "=================================================="
    echo ""
    echo "Installation Directory: ${INSTALL_DIR}"
    echo "Data Directory:         ${RADIO_DIR}"
    echo "Web Portal Port:        5001"
    echo ""
    echo "To start manually:"
    echo "  cd ${INSTALL_DIR}"
    echo "  source venv/bin/activate"
    echo "  python scanner_portal.py"
    echo ""
    echo "To run as service:"
    echo "  sudo systemctl enable rtl-scanner"
    echo "  sudo systemctl start rtl-scanner"
    echo ""
    echo "Access the web portal at:"
    echo "  http://<raspberry-pi-ip>:5001"
    echo ""
    echo "=================================================="
}

# Main
main() {
    check_root
    check_nas
    create_directories
    install_dependencies
    setup_rtlsdr_permissions
    setup_python_env
    copy_application
    create_service
    test_rtlsdr
    print_summary
}

# Run with argument handling
case "${1:-}" in
    --deps-only)
        install_dependencies
        ;;
    --service-only)
        create_service
        ;;
    --test)
        test_rtlsdr
        ;;
    *)
        main
        ;;
esac
