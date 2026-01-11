# AT-D578UV Software Mic & RTL-SDR Scanner

Software microphone emulator and RTL-SDR monitoring portal for the AnyTone AT-D578UVIII dual-band radio.

## Overview

This project provides two main components:

1. **Software Microphone** - Desktop GUI that emulates the physical hand microphone via serial/DigiRig
2. **RTL-SDR Scanner Portal** - Web-based multi-channel monitoring, recording, and transcription system

---

## Codeplug Configuration

### AT-D578UV (Base Station / Repeater)

The AT-D578UV codeplug is in `codeplug/` folder. Import CSVs into AnyTone CPS software.

**Files:**
| File | Description |
|------|-------------|
| `channels.csv` | 38 channels (High power) |
| `zones.csv` | Zone definitions |
| `scanlist.csv` | Scan list configuration |
| `contacts.csv` | DMR contacts |
| `radioid.csv` | Radio IDs (I2Base, MrSI2) |
| `encryption_keys.csv` | AES-256 keys |
| `CPS_MANUAL_SETTINGS.txt` | Settings that must be configured manually in CPS |

**Import Order:**
1. Tool > Import > Channel > `channels.csv`
2. Tool > Import > Zone > `zones.csv`
3. Tool > Import > Scan List > `scanlist.csv`
4. Manual: Add Radio IDs, Encryption Keys, P-Key assignments (see `CPS_MANUAL_SETTINGS.txt`)
5. Program > Write to Radio

### DM-32UV Handhelds

The DM-32UV HTs have a **firmware bug** that blocks channels with matching RX frequencies. Workaround uses TX-only channels.

**HT Codeplug Files:**
| File | DMR ID | Power |
|------|--------|-------|
| `DRN.csv` | I2 | Low |
| `DJN.csv` | MrSI2 | Low |
| `EJD.csv` | LiLI21 | Low |
| `JGN.csv` | LiLI22 | Low |
| `MAN.csv` | LiLI23 | Low |

**HT Channel Structure (42 channels):**
- Main channels (RX): TimeSlot 2, normal RX/TX
- TX-only channels: TimeSlot 1, NO RX frequency (firmware bug workaround)

**HT Operation:**
1. Set Channel B to main channel (e.g., "ENCRYPTED 1") - RX on TS2
2. Set Channel A to TX channel (e.g., "ENCRYPTED 1 TX") - TX on TS1
3. PTT transmits on TS1 → Repeater receives and retransmits on TS2
4. Channel B receives repeater output on TS2

---

## DMR Channels

### Encrypted Channels

| Channel | Frequency | Color Code | Encryption |
|---------|-----------|------------|------------|
| ENCRYPTED 1 | 451.01250 | 2 | KEY1 |
| ENCRYPTED 2 | 456.08750 | 4 | KEY2 |
| ENCRYPTED 3 | 462.11250 | 6 | KEY3 |
| FRS 22 | 462.72500 | 10 | None |

### Encryption Keys (AES-256)

| Key | Value |
|-----|-------|
| KEY1 | `285DAE5A749DE26BDE6B843892A5C58EE935FFE0660C6A19327F05D28B064920` |
| KEY2 | `2CF0F5D56777697DADD6C9F0EA980E1D100D9709AE172AF3C76CC9EE8E444234` |
| KEY3 | `0DFAC8681EECFC4FFCE88DBAB6EE48EDF9445DDEE24F7B3FA734D4841BF7BEA0` |

### Radio IDs

| ID | Name | Used By |
|----|------|---------|
| 100 | I2Base | AT-D578UV base |
| 101 | I2 | DRN HT |
| 102 | MrSI2 | AT-D578UV / DJN HT |
| 1 | LiLI21 | EJD HT |
| 2 | LiLI22 | JGN HT |
| 3 | LiLI23 | MAN HT |

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
├── d578uv-gui.py              # Desktop GUI application
├── d578uv-console.py          # Console testing tool
├── webportal.py               # DigiRig control web portal
├── rtl_scanner.py             # RTL-SDR scanner backend
├── scanner_portal.py          # Scanner web portal
├── audio_streamer.py          # Modular audio streaming
├── scanner_config.json        # Scanner configuration
├── setup_scanner.sh           # Raspberry Pi setup script
├── codeplug/                  # AT-D578UV codeplug (base station)
│   ├── channels.csv           # 38 channels, High power
│   ├── zones.csv              # Zone definitions
│   ├── scanlist.csv           # Scan list configuration
│   ├── contacts.csv           # DMR contacts
│   ├── radioid.csv            # Radio IDs
│   ├── encryption_keys.csv    # AES-256 keys
│   ├── CPS_MANUAL_SETTINGS.txt # Manual CPS settings
│   └── CodeplugSample.rdt     # Sample compiled codeplug
├── DRN.csv                    # DM-32UV HT codeplug (I2)
├── DJN.csv                    # DM-32UV HT codeplug (MrSI2)
├── EJD.csv                    # DM-32UV HT codeplug (LiLI21)
├── JGN.csv                    # DM-32UV HT codeplug (LiLI22)
├── MAN.csv                    # DM-32UV HT codeplug (LiLI23)
├── templates/
│   ├── index.html             # DigiRig portal interface
│   ├── scanner.html           # Scanner portal interface
│   └── scanner_v2.html        # Scanner v2 interface
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

### v2.2.0 - Codeplug Organization
- Separated AT-D578UV and DM-32UV codeplugs
- AT-D578UV: Standard channels, High power, no TX-only workaround needed
- DM-32UV HTs: TX-only channels for firmware bug workaround, Low power
- Complete codeplug CSVs with zones, scanlists, contacts, radio IDs

### v2.1.0 - Enhanced Audio Streaming
- Added `audio_streamer.py` module
- VLC network streaming support
- Real-time signal level monitoring
- Scanner v2 UI inspired by Rdio Scanner

### v2.0.0 - RTL-SDR Scanner Portal
- RTL-SDR multi-channel monitoring
- DMR Basic Privacy decryption
- Web-based scanner interface
- Recording and transcription

### v1.0.0 - Initial Release
- Software microphone emulator
- Serial connection via DigiRig

---

## Legal Notice

This software is intended for monitoring your own radio systems and frequencies you are licensed to use. Ensure compliance with all applicable regulations including FCC Part 95 (GMRS), Part 97 (Amateur), and local laws regarding radio communications.

## License

MIT License - See LICENSE file for details.

## Contributing

Issues and pull requests welcome at: https://github.com/I2aMpAnT/AT-D578UV
