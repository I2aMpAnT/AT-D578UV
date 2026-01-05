# AT-D578UV Software Mic & RTL-SDR Scanner

Software microphone emulator and RTL-SDR monitoring portal for the AnyTone AT-D578UVIII dual-band radio.

## Overview

This project provides two main components:

1. **Software Microphone** - Desktop GUI that emulates the physical hand microphone via serial/DigiRig
2. **RTL-SDR Scanner Portal** - Web-based multi-channel monitoring, recording, and transcription system

## Features

### Software Microphone (Desktop)
- Full button emulation (PTT, 0-9, *, #, A-D, UP/DOWN)
- Serial connection via DigiRig or compatible interface
- Configurable COM port and serial parameters
- Callsign display overlay

### RTL-SDR Scanner Portal (Web)
- Multi-channel monitoring with RTL-SDR
- Support for analog FM and DMR digital modes
- DMR Basic Privacy (ARC4) decryption
- Audio recording with automatic file management
- Whisper-based transcription
- Real-time signal detection
- Channel scanning with configurable dwell time
- NAS storage integration for recordings

## Hardware Requirements

### For Software Microphone
- AnyTone AT-D578UVIII radio
- DigiRig or compatible USB-serial interface
- Windows/Linux/Mac computer

### For RTL-SDR Scanner
- RTL-SDR USB dongle (RTL2832U-based)
- Raspberry Pi 4 (recommended) or similar SBC
- Antenna suitable for your frequencies
- Optional: NAS for recording storage

## Quick Start

### Software Microphone (Windows)
```bash
# Download the pre-built executable from dist/
d578uv-win-x64.exe
```

### RTL-SDR Scanner (Raspberry Pi)

1. **Clone the repository:**
```bash
git clone https://github.com/I2aMpAnT/AT-D578UV.git
cd AT-D578UV
```

2. **Run the setup script:**
```bash
chmod +x setup_scanner.sh
./setup_scanner.sh
```

3. **Start the scanner:**
```bash
cd /opt/at-d578uv-scanner
source venv/bin/activate
python scanner_portal.py
```

4. **Access the web portal:**
```
http://<raspberry-pi-ip>:5001
```

## Configuration

### Channel Configuration
Export your codeplug channels to CSV from AnyTone CPS software. The scanner reads `DRN_channels.csv` by default.

### Encryption Keys
Configure encryption keys in `scanner_config.json`:
```json
{
  "encryption_keys": {
    "KEY1": "YOUR_128BIT_HEX_KEY",
    "KEY2": "YOUR_128BIT_HEX_KEY"
  }
}
```

### Storage Paths (NAS)
Modify paths in `scanner_config.json` for your NAS setup:
```json
{
  "paths": {
    "recordings": "/mnt/nas4/radio/recordings",
    "transcriptions": "/mnt/nas4/radio/transcriptions",
    "logs": "/mnt/nas4/radio/logs"
  }
}
```

## Web Portal Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main scanner interface |
| `/api/channels` | GET | List all channels |
| `/api/channels/encrypted` | GET | List encrypted channels |
| `/api/tune/<num>` | POST | Tune to channel |
| `/api/monitor/start/<num>` | POST | Start monitoring |
| `/api/monitor/stop` | POST | Stop monitoring |
| `/api/record/start/<num>` | POST | Start recording |
| `/api/record/stop` | POST | Stop recording |
| `/api/scan/start` | POST | Start channel scan |
| `/api/recordings` | GET | List recordings |
| `/api/recordings/<file>/transcribe` | POST | Transcribe recording |

## File Structure

```
AT-D578UV/
├── d578uv-gui.py          # Desktop GUI application
├── d578uv-console.py      # Console testing tool
├── webportal.py           # DigiRig control web portal
├── rtl_scanner.py         # RTL-SDR scanner backend
├── scanner_portal.py      # Scanner web portal
├── scanner_config.json    # Scanner configuration
├── setup_scanner.sh       # Raspberry Pi setup script
├── DRN_channels.csv       # Channel configuration
├── DRN.data               # Codeplug binary (encryption keys)
├── templates/
│   ├── index.html         # DigiRig portal interface
│   └── scanner.html       # Scanner portal interface
├── requirements-webportal.txt
└── requirements-scanner.txt
```

## Running as a Service

Enable the scanner to start on boot:
```bash
sudo systemctl enable rtl-scanner
sudo systemctl start rtl-scanner
```

Check status:
```bash
sudo systemctl status rtl-scanner
```

View logs:
```bash
journalctl -u rtl-scanner -f
```

## Dependencies

### System (Raspberry Pi)
```bash
sudo apt-get install rtl-sdr librtlsdr-dev sox ffmpeg python3-pip
```

### Python
```bash
pip install -r requirements-scanner.txt
```

### Optional (Transcription)
```bash
pip install openai-whisper
```
Note: Whisper is resource-intensive. Use 'tiny' or 'base' model on Raspberry Pi.

## Keyboard Shortcuts (Scanner Portal)

| Key | Action |
|-----|--------|
| 0-9 | Tune to channel |
| Space | Toggle monitor |
| R | Toggle record |
| S | Toggle scan |

## Troubleshooting

### RTL-SDR Not Detected
```bash
# Check device
rtl_test -t

# Blacklist kernel driver
echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/blacklist-rtlsdr.conf
sudo modprobe -r dvb_usb_rtl28xxu
```

### Permission Denied
```bash
# Add udev rule
sudo tee /etc/udev/rules.d/20-rtlsdr.rules << 'EOF'
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", MODE:="0666"
EOF
sudo udevadm control --reload-rules
```

### Audio Issues
```bash
# Test audio capture
rtl_fm -f 146.52M -M fm -s 24000 -g 40 - | play -r 24000 -t raw -e signed -b 16 -c 1 -
```

## Version History

### v2.0.0 - RTL-SDR Scanner Portal
- Added RTL-SDR multi-channel monitoring
- DMR Basic Privacy decryption support
- Web-based scanner interface
- Recording and transcription features
- Raspberry Pi deployment support
- NAS storage integration

### v1.0.3
- Fixed bug with B button

### v1.0.2
- Added configuration file support
- Settings window for serial parameters
- IOCTL improvements for button responsiveness

### v1.0.1
- Fixed image paths
- Windows executable release

### v1.0.0
- Initial release

## Legal Notice

This software is intended for monitoring your own radio systems and frequencies you are licensed to use. Ensure compliance with all applicable regulations including FCC Part 95 (GMRS), Part 97 (Amateur), and local laws regarding radio communications.

## License

MIT License - See LICENSE file for details.

## Contributing

Issues and pull requests welcome at: https://github.com/I2aMpAnT/AT-D578UV
