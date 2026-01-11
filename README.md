# AT-D578UV Software Mic & RTL-SDR Scanner

Software microphone emulator and RTL-SDR monitoring portal for the AnyTone AT-D578UVIII dual-band radio.

## Overview

This project provides two main components:

1. **Software Microphone** - Desktop GUI that emulates the physical hand microphone via serial/DigiRig
2. **RTL-SDR Scanner Portal** - Web-based multi-channel monitoring, recording, and transcription system

---

## DMR Repeater System Configuration

### Firmware Bug Workaround

The DM-32UV handheld firmware has a bug that **blocks channels with matching RX frequencies**. To work around this, we use a split channel approach:

- **Main channels (RX)** - For receiving on TimeSlot 2
- **TX-only channels** - For transmitting on TimeSlot 1 (NO RX frequency to avoid the bug)

### Channel Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    MOBILE RADIO (AT-D578UV)                     │
├─────────────────────────────────────────────────────────────────┤
│  Channel A (TX Mode)     │  Channel B (RX Mode)                 │
│  ────────────────────    │  ────────────────────                │
│  TX-only channel         │  Main channel                        │
│  TimeSlot 1              │  TimeSlot 2                          │
│  No RX freq (bug fix)    │  RX/TX freq (same)                   │
│  → Keys into repeater    │  ← Receives from repeater            │
│                          │  ← Also receives direct HT TX        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         REPEATER                                 │
├─────────────────────────────────────────────────────────────────┤
│  RX: TimeSlot 1 (from HTs and mobile)                           │
│  TX: TimeSlot 2 (to all radios)                                 │
│  RX Scan: All 4 frequencies on TS1                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    WEB PORTAL (RTL-SDR)                          │
├─────────────────────────────────────────────────────────────────┤
│  RX Scan: All 4 frequencies on TimeSlot 2                       │
│  Catches: Repeater TX + Direct HT TX (if on TS2)                │
└─────────────────────────────────────────────────────────────────┘
```

### Radio Operation

1. **Set Channel B** to the main channel (e.g., "ENCRYPTED 1") - this is your RX channel on TS2
2. **Set Channel A** to the corresponding TX channel (e.g., "ENC 1 TX") - this is your TX channel on TS1
3. PTT transmits on Channel A (TS1) → Repeater receives and retransmits on TS2
4. Channel B receives the repeater's transmission on TS2

### Repeater Configuration

The repeater must be configured to:
- **RX Scan**: All 4 frequencies on TimeSlot 1
- **TX**: Same frequency, TimeSlot 2
- This creates a TS1→TS2 crossband-style operation on the same frequency

---

## Encrypted DMR Channels

### Channel Pairs

| Main Channel (RX/TS2) | TX Channel (TX/TS1) | Frequency | Color Code | Encryption |
|-----------------------|---------------------|-----------|------------|------------|
| ENCRYPTED 1           | ENC 1 TX            | 451.01250 | 2          | KEY1       |
| ENCRYPTED 2           | ENC 2 TX            | 456.08750 | 4          | KEY2       |
| ENCRYPTED 3           | ENC 3 TX            | 462.11250 | 6          | KEY3       |
| FRS 22                | FRS 22 TX           | 462.72500 | 10         | None       |

### Encryption Keys (AES-256)

| Key Name | Key (Hex)                                                        |
|----------|------------------------------------------------------------------|
| KEY1     | `285DAE5A749DE26BDE6B843892A5C58EE935FFE0660C6A19327F05D28B064920` |
| KEY2     | `2CF0F5D56777697DADD6C9F0EA980E1D100D9709AE172AF3C76CC9EE8E444234` |
| KEY3     | `0DFAC8681EECFC4FFCE88DBAB6EE48EDF9445DDEE24F7B3FA734D4841BF7BEA0` |

### TimeSlot Summary

| Channel Type | TimeSlot | Purpose |
|--------------|----------|---------|
| Main (RX)    | TS2      | Receive from repeater or direct HT |
| TX-only      | TS1      | Transmit to repeater input |

---

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

---

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

---

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

---

## Configuration

### Channel Configuration
Export your codeplug channels to CSV from AnyTone CPS software. The scanner reads `DRN_channels.csv` by default.

### Encryption Keys
Configure encryption keys in `scanner_config.json`:
```json
{
  "encryption_keys": {
    "KEY1": "285DAE5A749DE26BDE6B843892A5C58EE935FFE0660C6A19327F05D28B064920",
    "KEY2": "2CF0F5D56777697DADD6C9F0EA980E1D100D9709AE172AF3C76CC9EE8E444234",
    "KEY3": "0DFAC8681EECFC4FFCE88DBAB6EE48EDF9445DDEE24F7B3FA734D4841BF7BEA0"
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

---

## Web Portal Endpoints

### Main Interfaces
| Endpoint | Description |
|----------|-------------|
| `/` | Original scanner interface |
| `/v2` | Scanner v2 - Rdio Scanner style UI |

### Channel API
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/channels` | GET | List all channels |
| `/api/channels/encrypted` | GET | List encrypted channels |
| `/api/channels/analog` | GET | List analog channels |
| `/api/tune/<num>` | POST | Tune to channel |
| `/api/monitor/start/<num>` | POST | Start monitoring |
| `/api/monitor/stop` | POST | Stop monitoring |
| `/api/record/start/<num>` | POST | Start recording |
| `/api/record/stop` | POST | Stop recording |
| `/api/scan/start` | POST | Start channel scan |
| `/api/scan/stop` | POST | Stop channel scan |

### Recordings API
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/recordings` | GET | List recordings |
| `/api/recordings/<file>` | GET | Download recording |
| `/api/recordings/<file>/transcribe` | POST | Transcribe recording |

### Enhanced Streaming API (v2)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v2/stream/start/<num>` | POST | Start VLC streaming (options: record, stream, playback) |
| `/api/v2/stream/stop` | POST | Stop streaming |
| `/api/v2/stream/status` | GET | Get stream status |
| `/api/v2/signal` | GET | Get real-time signal level |

### Streaming Ports
| Port | Service |
|------|---------|
| 5001 | Web Portal |
| 8080 | VLC Audio Stream (`http://host:8080/stream.ogg`) |

---

## File Structure

```
AT-D578UV/
├── d578uv-gui.py          # Desktop GUI application
├── d578uv-console.py      # Console testing tool
├── webportal.py           # DigiRig control web portal
├── rtl_scanner.py         # RTL-SDR scanner backend
├── scanner_portal.py      # Scanner web portal
├── audio_streamer.py      # Modular audio streaming (VLC, sox, recording)
├── scanner_config.json    # Scanner configuration
├── setup_scanner.sh       # Raspberry Pi setup script
├── codeplug/
│   ├── channels.csv       # Channel configuration with TX-only channels
│   ├── encryption_keys.csv # AES-256 encryption keys
│   ├── zones.csv          # Zone definitions
│   ├── scanlist.csv       # Scan list configuration
│   ├── contacts.csv       # DMR contacts
│   └── radioid.csv        # Radio ID configuration
├── DRN_channels.csv       # Legacy channel configuration
├── DRN.data               # Codeplug binary (encryption keys)
├── templates/
│   ├── index.html         # DigiRig portal interface
│   ├── scanner.html       # Scanner portal interface (original)
│   └── scanner_v2.html    # Scanner portal interface (Rdio Scanner style)
├── requirements-webportal.txt
└── requirements-scanner.txt
```

---

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

---

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

---

## Keyboard Shortcuts (Scanner Portal)

| Key | Action |
|-----|--------|
| 0-9 | Tune to channel |
| Space | Toggle monitor |
| R | Toggle record |
| S | Toggle scan |

---

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

---

## Version History

### v2.2.0 - DMR Repeater Timeslot Split
- Added TX-only channels for repeater operation
- Implemented DM-32UV firmware bug workaround (no matching RX frequencies)
- Main channels set to TimeSlot 2 for RX
- TX channels set to TimeSlot 1 for repeater input
- Changed DMR MODE from "DCDM TS Split" to "Simplex" for manual timeslot control

### v2.1.0 - Enhanced Audio Streaming
- Added `audio_streamer.py` module based on rtl_fm_python, K0NYC/rtl-fm patterns
- VLC network streaming support (access audio from any device)
- Real-time signal level monitoring
- Scanner v2 UI inspired by Rdio Scanner project
- Professional scanner-style interface with:
  - Large frequency display with green LED aesthetic
  - 25-bar signal meter with color gradients
  - Channel filtering (All/Encrypted/Analog/DMR)
  - Activity feed and recording management

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

---

## Legal Notice

This software is intended for monitoring your own radio systems and frequencies you are licensed to use. Ensure compliance with all applicable regulations including FCC Part 95 (GMRS), Part 97 (Amateur), and local laws regarding radio communications.

## License

MIT License - See LICENSE file for details.

## Contributing

Issues and pull requests welcome at: https://github.com/I2aMpAnT/AT-D578UV
