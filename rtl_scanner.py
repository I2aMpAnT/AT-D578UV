#!/usr/bin/env python3
"""
AT-D578UV RTL-SDR Scanner & Monitor
Multi-channel monitoring with DMR decryption, recording, and transcription
For Raspberry Pi deployment

GMRS License: WSKW654
"""

import os
import sys
import json
import time
import wave
import struct
import subprocess
import threading
import queue
import hashlib
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum
import csv

# Optional imports with fallbacks
try:
    from Crypto.Cipher import ARC4
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("Warning: pycryptodome not installed. DMR decryption disabled.")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class ChannelType(Enum):
    ANALOG = "Analog"
    DIGITAL = "Digital"


@dataclass
class Channel:
    """Radio channel configuration"""
    number: int
    name: str
    channel_type: ChannelType
    rx_freq: float  # MHz
    tx_freq: float  # MHz
    bandwidth: str
    encryption: bool = False
    encryption_key_id: Optional[str] = None
    color_code: int = 1
    time_slot: int = 1
    forbid_tx: bool = False

    def __post_init__(self):
        if isinstance(self.channel_type, str):
            self.channel_type = ChannelType(self.channel_type)


@dataclass
class EncryptionKey:
    """DMR Basic Privacy encryption key"""
    key_id: str
    key_hex: str
    key_bytes: bytes = field(init=False)

    def __post_init__(self):
        self.key_bytes = bytes.fromhex(self.key_hex)


@dataclass
class Recording:
    """Audio recording metadata"""
    filename: str
    channel: str
    start_time: datetime
    duration: float = 0.0
    transcription: Optional[str] = None
    is_encrypted: bool = False


class DMRDecryptor:
    """DMR Basic Privacy (ARC4) decryption"""

    def __init__(self, keys: Dict[str, EncryptionKey]):
        self.keys = keys

    def decrypt(self, data: bytes, key_id: str) -> bytes:
        """Decrypt DMR Basic Privacy encrypted data"""
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("pycryptodome required for decryption")

        if key_id not in self.keys:
            raise ValueError(f"Unknown key ID: {key_id}")

        key = self.keys[key_id]
        cipher = ARC4.new(key.key_bytes)
        return cipher.decrypt(data)


class RTLSDRScanner:
    """RTL-SDR based radio scanner"""

    def __init__(self, config_path: str = None):
        self.channels: Dict[int, Channel] = {}
        self.keys: Dict[str, EncryptionKey] = {}
        self.decryptor: Optional[DMRDecryptor] = None
        self.recordings_dir = Path("recordings")
        self.recordings_dir.mkdir(exist_ok=True)

        self.current_channel: Optional[Channel] = None
        self.is_scanning = False
        self.is_recording = False
        self.rtl_process: Optional[subprocess.Popen] = None
        self.audio_queue = queue.Queue()

        # Callbacks for UI updates
        self.on_signal_detected: Optional[Callable] = None
        self.on_recording_complete: Optional[Callable] = None
        self.on_transcription_ready: Optional[Callable] = None

        # Load configuration
        if config_path:
            self.load_config(config_path)

    def load_channels_from_csv(self, csv_path: str):
        """Load channel configuration from exported CSV"""
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    channel = Channel(
                        number=int(row['No.']),
                        name=row['Channel Name'],
                        channel_type=row['Channel Type'],
                        rx_freq=float(row['RX Frequency[MHz]']),
                        tx_freq=float(row['TX Frequency[MHz]']),
                        bandwidth=row['Band Width'],
                        encryption=row['Encryption'] == '1',
                        encryption_key_id=row['Encryption ID'] if row['Encryption ID'] != 'None' else None,
                        color_code=int(row['Color Code']),
                        time_slot=1 if row['Time Slot'] == 'Slot 1' else 2,
                        forbid_tx=row['Forbid TX'] == '1'
                    )
                    self.channels[channel.number] = channel
                except (KeyError, ValueError) as e:
                    print(f"Warning: Could not parse channel row: {e}")

        print(f"Loaded {len(self.channels)} channels")

    def add_encryption_key(self, key_id: str, key_hex: str):
        """Add an encryption key"""
        self.keys[key_id] = EncryptionKey(key_id=key_id, key_hex=key_hex)
        self.decryptor = DMRDecryptor(self.keys)
        print(f"Added encryption key: {key_id}")

    def load_config(self, config_path: str):
        """Load configuration from JSON file"""
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Load encryption keys
        for key_id, key_hex in config.get('encryption_keys', {}).items():
            self.add_encryption_key(key_id, key_hex)

        # Load channels from CSV if specified
        if 'channels_csv' in config:
            self.load_channels_from_csv(config['channels_csv'])

    def get_rtl_devices(self) -> List[str]:
        """List available RTL-SDR devices"""
        try:
            result = subprocess.run(
                ['rtl_test', '-t'],
                capture_output=True,
                text=True,
                timeout=5
            )
            # Parse device info from output
            devices = []
            for line in result.stderr.split('\n'):
                if 'Found' in line and 'device' in line:
                    devices.append(line.strip())
            return devices if devices else ["No RTL-SDR devices found"]
        except FileNotFoundError:
            return ["rtl-sdr tools not installed"]
        except subprocess.TimeoutExpired:
            return ["RTL-SDR detection timed out"]

    def tune_channel(self, channel_num: int) -> bool:
        """Tune to a specific channel"""
        if channel_num not in self.channels:
            print(f"Channel {channel_num} not found")
            return False

        self.current_channel = self.channels[channel_num]
        print(f"Tuned to channel {channel_num}: {self.current_channel.name} ({self.current_channel.rx_freq} MHz)")
        return True

    def tune_frequency(self, freq_mhz: float, audio_callback: Optional[Callable] = None) -> bool:
        """Tune directly to a frequency (MHz) and start monitoring"""
        # Create a temporary channel for direct frequency tuning
        temp_channel = Channel(
            number=0,
            name="Manual Tune",
            channel_type=ChannelType.ANALOG,
            rx_freq=freq_mhz,
            tx_freq=freq_mhz,
            bandwidth="25K",
            forbid_tx=True
        )
        self.current_channel = temp_channel
        self.audio_callback = audio_callback
        print(f"Direct tune to {freq_mhz} MHz")

        # Stop any existing monitoring and start on new frequency
        self.stop_monitoring()
        freq_hz = int(freq_mhz * 1_000_000)

        # Build rtl_fm command - capture stdout for streaming
        cmd = [
            'rtl_fm',
            '-f', str(freq_hz),
            '-M', 'fm',
            '-s', '24000',
            '-g', '40',
            '-l', '10',
            '-'
        ]

        try:
            self.rtl_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            self.is_scanning = True
            print(f"Started monitoring {freq_mhz} MHz")

            # Start audio streaming thread
            if audio_callback:
                threading.Thread(
                    target=self._stream_audio,
                    args=(audio_callback,),
                    daemon=True
                ).start()

            return True
        except Exception as e:
            print(f"Error starting rtl_fm: {e}")
            return False

    def _stream_audio(self, callback: Callable):
        """Stream audio data to callback"""
        import base64
        while self.rtl_process and self.is_scanning:
            try:
                # Read chunks of audio data
                data = self.rtl_process.stdout.read(4096)
                if data and callback:
                    # Send as base64 for WebSocket
                    callback(base64.b64encode(data).decode('ascii'))
            except Exception as e:
                print(f"Audio stream error: {e}")
                break

    def start_monitoring(self, channel_num: int, output_callback: Optional[Callable] = None):
        """Start monitoring a channel using rtl_fm"""
        if not self.tune_channel(channel_num):
            return False

        channel = self.current_channel
        freq_hz = int(channel.rx_freq * 1_000_000)

        # Determine modulation based on channel type
        if channel.channel_type == ChannelType.ANALOG:
            # FM modulation for analog
            modulation = 'fm'
            sample_rate = 24000
        else:
            # For DMR, we need raw IQ and external decoder
            modulation = 'raw'
            sample_rate = 48000

        # Build rtl_fm command
        cmd = [
            'rtl_fm',
            '-f', str(freq_hz),
            '-M', modulation,
            '-s', str(sample_rate),
            '-g', '40',  # Gain
            '-l', '10',  # Squelch level
            '-'
        ]

        try:
            self.rtl_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            self.is_scanning = True

            # Start audio processing thread
            threading.Thread(
                target=self._audio_processor,
                args=(output_callback,),
                daemon=True
            ).start()

            return True
        except Exception as e:
            print(f"Error starting rtl_fm: {e}")
            return False

    def stop_monitoring(self):
        """Stop monitoring"""
        self.is_scanning = False
        if self.rtl_process:
            self.rtl_process.terminate()
            self.rtl_process = None

    def _audio_processor(self, callback: Optional[Callable] = None):
        """Process audio from RTL-SDR"""
        while self.is_scanning and self.rtl_process:
            try:
                # Read audio data
                data = self.rtl_process.stdout.read(4096)
                if not data:
                    break

                # Put in queue for recording/analysis
                self.audio_queue.put(data)

                # Callback for real-time audio
                if callback:
                    callback(data)

            except Exception as e:
                print(f"Audio processing error: {e}")
                break

    def start_recording(self, channel_num: int) -> Optional[str]:
        """Start recording a channel"""
        if not self.tune_channel(channel_num):
            return None

        channel = self.current_channel
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{channel.name}_{timestamp}.wav"
        filepath = self.recordings_dir / filename

        self.is_recording = True

        # Start recording thread
        threading.Thread(
            target=self._record_audio,
            args=(filepath, channel),
            daemon=True
        ).start()

        return str(filepath)

    def _record_audio(self, filepath: Path, channel: Channel):
        """Record audio to WAV file"""
        sample_rate = 24000 if channel.channel_type == ChannelType.ANALOG else 48000

        with wave.open(str(filepath), 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(sample_rate)

            start_time = time.time()

            while self.is_recording:
                try:
                    data = self.audio_queue.get(timeout=1)
                    wav.writeframes(data)
                except queue.Empty:
                    continue

            duration = time.time() - start_time

        # Create recording metadata
        recording = Recording(
            filename=str(filepath),
            channel=channel.name,
            start_time=datetime.now(),
            duration=duration,
            is_encrypted=channel.encryption
        )

        if self.on_recording_complete:
            self.on_recording_complete(recording)

        return recording

    def stop_recording(self):
        """Stop recording"""
        self.is_recording = False

    def scan_channels(self, channel_list: List[int] = None, dwell_time: float = 2.0):
        """Scan through multiple channels"""
        if channel_list is None:
            channel_list = list(self.channels.keys())

        self.is_scanning = True

        while self.is_scanning:
            for ch_num in channel_list:
                if not self.is_scanning:
                    break

                channel = self.channels.get(ch_num)
                if not channel:
                    continue

                print(f"Scanning: {channel.name} ({channel.rx_freq} MHz)")

                # Check for signal
                if self._check_signal(channel):
                    print(f"Signal detected on {channel.name}!")
                    if self.on_signal_detected:
                        self.on_signal_detected(channel)

                time.sleep(dwell_time)

    def _check_signal(self, channel: Channel) -> bool:
        """Quick check for signal presence on a channel"""
        freq_hz = int(channel.rx_freq * 1_000_000)

        try:
            # Use rtl_power for quick signal check
            result = subprocess.run(
                ['rtl_fm', '-f', str(freq_hz), '-M', 'fm', '-s', '24000', '-g', '40', '-'],
                capture_output=True,
                timeout=0.5
            )
            # Check if we got audio data (signal present)
            return len(result.stdout) > 1000
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_channel_list(self) -> List[dict]:
        """Get list of all channels for UI"""
        return [
            {
                'number': ch.number,
                'name': ch.name,
                'type': ch.channel_type.value,
                'frequency': ch.rx_freq,
                'encrypted': ch.encryption,
                'forbid_tx': ch.forbid_tx
            }
            for ch in self.channels.values()
        ]

    def get_encrypted_channels(self) -> List[Channel]:
        """Get list of encrypted channels"""
        return [ch for ch in self.channels.values() if ch.encryption]

    def get_analog_channels(self) -> List[Channel]:
        """Get list of analog channels"""
        return [ch for ch in self.channels.values()
                if ch.channel_type == ChannelType.ANALOG]


class TranscriptionService:
    """Audio transcription using Whisper"""

    def __init__(self, model_size: str = "base"):
        self.model = None
        self.model_size = model_size
        self._load_model()

    def _load_model(self):
        """Load Whisper model"""
        try:
            import whisper
            print(f"Loading Whisper model: {self.model_size}")
            self.model = whisper.load_model(self.model_size)
            print("Whisper model loaded successfully")
        except ImportError:
            print("Warning: openai-whisper not installed. Transcription disabled.")
            self.model = None

    def transcribe(self, audio_path: str) -> Optional[str]:
        """Transcribe audio file"""
        if not self.model:
            return None

        try:
            result = self.model.transcribe(audio_path)
            return result['text']
        except Exception as e:
            print(f"Transcription error: {e}")
            return None


# Configuration for your system
DEFAULT_CONFIG = {
    "encryption_keys": {
        "KEY1": "285DAE5A749DE26BDE6B843892A5C58E",
        "KEY2": "2CF0F5D56777697DADD6C9F0EA980E1D",
        "KEY3": "0DFAC8681EECFC4FFCE88DBAB6EE48ED"
    },
    "channels_csv": "DRN_channels.csv",
    "recordings_dir": "recordings",
    "rtl_device_index": 0,
    "default_gain": 40,
    "squelch_level": 10
}


def create_default_config():
    """Create default configuration file"""
    config_path = Path(__file__).parent / 'scanner_config.json'
    with open(config_path, 'w') as f:
        json.dump(DEFAULT_CONFIG, f, indent=2)
    print(f"Created default config: {config_path}")
    return config_path


if __name__ == '__main__':
    # Create config if it doesn't exist
    config_path = Path(__file__).parent / 'scanner_config.json'
    if not config_path.exists():
        create_default_config()

    # Initialize scanner
    scanner = RTLSDRScanner()

    # Load channels from CSV
    csv_path = Path(__file__).parent / 'DRN_channels.csv'
    if csv_path.exists():
        scanner.load_channels_from_csv(str(csv_path))

    # Add encryption keys
    for key_id, key_hex in DEFAULT_CONFIG['encryption_keys'].items():
        scanner.add_encryption_key(key_id, key_hex)

    # List channels
    print("\n=== Available Channels ===")
    for ch in scanner.get_channel_list():
        enc_marker = "[ENC]" if ch['encrypted'] else ""
        tx_marker = "[RX ONLY]" if ch['forbid_tx'] else ""
        print(f"  {ch['number']:2d}. {ch['name']:12s} {ch['frequency']:9.5f} MHz {ch['type']:7s} {enc_marker} {tx_marker}")

    # Check for RTL-SDR
    print("\n=== RTL-SDR Devices ===")
    for device in scanner.get_rtl_devices():
        print(f"  {device}")

    print("\nScanner initialized. Use the web portal for full control.")
