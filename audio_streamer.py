#!/usr/bin/env python3
"""
RTL-SDR Audio Streamer
Based on rtl_fm_python and K0NYC/rtl-fm patterns
Provides real-time audio streaming via web interface

References:
- https://github.com/th0ma5w/rtl_fm_python
- https://github.com/K0NYC/rtl-fm
- https://github.com/chuot/rdio-scanner
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
import signal
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Generator
from dataclasses import dataclass
from enum import Enum

# Audio processing
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class Modulation(Enum):
    """Supported modulation modes (rtl_fm compatible)"""
    FM = 'fm'      # Narrowband FM
    WBFM = 'wbfm'  # Wideband FM (broadcast)
    AM = 'am'      # AM
    LSB = 'lsb'    # Lower sideband
    USB = 'usb'    # Upper sideband
    RAW = 'raw'    # Raw IQ


@dataclass
class AudioConfig:
    """Audio configuration"""
    sample_rate: int = 24000
    channels: int = 1
    bit_depth: int = 16
    buffer_size: int = 4096


class RTLFMProcess:
    """
    Wrapper for rtl_fm process
    Inspired by rtl_fm_python API design
    """

    def __init__(self, device_index: int = 0):
        self.device_index = device_index
        self.process: Optional[subprocess.Popen] = None
        self.frequency: int = 0
        self.modulation: Modulation = Modulation.FM
        self.gain: int = 40
        self.squelch: int = 0
        self.sample_rate: int = 24000
        self.ppm_correction: int = 0

        self._audio_queue = queue.Queue(maxsize=100)
        self._is_running = False
        self._reader_thread: Optional[threading.Thread] = None

        # Signal level monitoring
        self._signal_level: float = 0.0
        self._signal_lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._is_running and self.process is not None

    def get_signal_level(self) -> float:
        """Get current signal level (RMS)"""
        with self._signal_lock:
            return self._signal_level

    def _calculate_signal_level(self, data: bytes) -> float:
        """Calculate RMS signal level from audio data"""
        if not NUMPY_AVAILABLE or len(data) < 2:
            return 0.0

        try:
            samples = np.frombuffer(data, dtype=np.int16)
            rms = np.sqrt(np.mean(samples.astype(np.float64) ** 2))
            # Normalize to 0-100 scale
            return min(100.0, (rms / 32768.0) * 100.0 * 3)
        except:
            return 0.0

    def start(self, frequency: int, modulation: Modulation = Modulation.FM,
              gain: int = 40, squelch: int = 0, sample_rate: int = 24000) -> bool:
        """
        Start rtl_fm process

        Args:
            frequency: Frequency in Hz
            modulation: Demodulation mode
            gain: RF gain (0-50, or 'auto')
            squelch: Squelch level (0 = off)
            sample_rate: Audio sample rate
        """
        if self.is_running:
            self.stop()

        self.frequency = frequency
        self.modulation = modulation
        self.gain = gain
        self.squelch = squelch
        self.sample_rate = sample_rate

        # Build rtl_fm command
        cmd = [
            'rtl_fm',
            '-d', str(self.device_index),
            '-f', str(frequency),
            '-M', modulation.value,
            '-s', str(sample_rate),
            '-g', str(gain),
            '-p', str(self.ppm_correction),
        ]

        if squelch > 0:
            cmd.extend(['-l', str(squelch)])

        # Output raw audio to stdout
        cmd.append('-')

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0
            )
            self._is_running = True

            # Start reader thread
            self._reader_thread = threading.Thread(
                target=self._audio_reader,
                daemon=True
            )
            self._reader_thread.start()

            return True

        except FileNotFoundError:
            print("Error: rtl_fm not found. Install rtl-sdr package.")
            return False
        except Exception as e:
            print(f"Error starting rtl_fm: {e}")
            return False

    def stop(self):
        """Stop rtl_fm process"""
        self._is_running = False

        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

        # Clear audio queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

    def _audio_reader(self):
        """Read audio data from rtl_fm process"""
        while self._is_running and self.process:
            try:
                data = self.process.stdout.read(4096)
                if not data:
                    break

                # Calculate signal level
                level = self._calculate_signal_level(data)
                with self._signal_lock:
                    self._signal_level = level

                # Add to queue (non-blocking)
                try:
                    self._audio_queue.put_nowait(data)
                except queue.Full:
                    # Drop oldest if queue is full
                    try:
                        self._audio_queue.get_nowait()
                        self._audio_queue.put_nowait(data)
                    except queue.Empty:
                        pass

            except Exception as e:
                if self._is_running:
                    print(f"Audio reader error: {e}")
                break

        self._is_running = False

    def get_audio_chunk(self, timeout: float = 1.0) -> Optional[bytes]:
        """Get audio chunk from queue"""
        try:
            return self._audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def audio_stream(self) -> Generator[bytes, None, None]:
        """Generator for streaming audio data"""
        while self._is_running:
            chunk = self.get_audio_chunk(timeout=0.5)
            if chunk:
                yield chunk

    def set_frequency(self, frequency: int) -> bool:
        """Change frequency (requires restart)"""
        if self.is_running:
            return self.start(
                frequency,
                self.modulation,
                self.gain,
                self.squelch,
                self.sample_rate
            )
        self.frequency = frequency
        return True

    def set_gain(self, gain: int) -> bool:
        """Change gain (requires restart)"""
        if self.is_running:
            return self.start(
                self.frequency,
                self.modulation,
                gain,
                self.squelch,
                self.sample_rate
            )
        self.gain = gain
        return True

    def set_squelch(self, level: int) -> bool:
        """Change squelch level (requires restart)"""
        if self.is_running:
            return self.start(
                self.frequency,
                self.modulation,
                self.gain,
                level,
                self.sample_rate
            )
        self.squelch = level
        return True


class AudioRecorder:
    """
    Records audio to WAV files
    Inspired by trunk-recorder's call recording
    """

    def __init__(self, output_dir: str = "recordings"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._recording = False
        self._current_file: Optional[wave.Wave_write] = None
        self._current_path: Optional[Path] = None
        self._start_time: Optional[datetime] = None
        self._sample_rate = 24000
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start_recording(self, channel_name: str, sample_rate: int = 24000) -> str:
        """Start recording to a new WAV file"""
        with self._lock:
            if self._recording:
                self.stop_recording()

            self._sample_rate = sample_rate
            self._start_time = datetime.now()

            # Create filename: CHANNELNAME_YYYYMMDD_HHMMSS.wav
            timestamp = self._start_time.strftime('%Y%m%d_%H%M%S')
            safe_name = "".join(c if c.isalnum() else '_' for c in channel_name)
            filename = f"{safe_name}_{timestamp}.wav"
            self._current_path = self.output_dir / filename

            # Open WAV file
            self._current_file = wave.open(str(self._current_path), 'wb')
            self._current_file.setnchannels(1)
            self._current_file.setsampwidth(2)  # 16-bit
            self._current_file.setframerate(sample_rate)

            self._recording = True
            return str(self._current_path)

    def write_audio(self, data: bytes):
        """Write audio data to current recording"""
        with self._lock:
            if self._recording and self._current_file:
                self._current_file.writeframes(data)

    def stop_recording(self) -> Optional[dict]:
        """Stop recording and return metadata"""
        with self._lock:
            if not self._recording:
                return None

            self._recording = False

            if self._current_file:
                self._current_file.close()
                self._current_file = None

            if self._current_path and self._start_time:
                duration = (datetime.now() - self._start_time).total_seconds()
                result = {
                    'filename': self._current_path.name,
                    'path': str(self._current_path),
                    'start_time': self._start_time.isoformat(),
                    'duration': duration,
                    'sample_rate': self._sample_rate
                }
                self._current_path = None
                self._start_time = None
                return result

            return None


class VLCStreamer:
    """
    VLC-based network audio streaming
    Based on K0NYC/rtl-fm streaming approach
    """

    def __init__(self, port: int = 8080):
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running and self.process is not None

    @property
    def stream_url(self) -> str:
        return f"http://localhost:{self.port}/stream.ogg"

    def start(self, sample_rate: int = 24000) -> bool:
        """
        Start VLC streaming server

        This creates an HTTP stream that can be accessed from any browser
        or media player at http://localhost:PORT/stream.ogg
        """
        if self.is_running:
            self.stop()

        # VLC command to read raw audio from stdin and stream as OGG
        cmd = [
            'cvlc',
            '--quiet',
            # Input: raw audio from stdin
            'fd://0',
            f'--demux=rawaud',
            f'--rawaud-channels=1',
            f'--rawaud-samplerate={sample_rate}',
            # Transcode to OGG Vorbis
            '--sout',
            f'#transcode{{acodec=vorb,ab=128}}:http{{mux=ogg,dst=:{self.port}/stream.ogg}}',
            '--sout-keep'
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self._is_running = True
            return True
        except FileNotFoundError:
            print("Warning: VLC not found. Install vlc package for network streaming.")
            return False
        except Exception as e:
            print(f"Error starting VLC: {e}")
            return False

    def write_audio(self, data: bytes):
        """Write audio data to VLC stdin"""
        if self.is_running and self.process and self.process.stdin:
            try:
                self.process.stdin.write(data)
                self.process.stdin.flush()
            except (BrokenPipeError, OSError):
                self._is_running = False

    def stop(self):
        """Stop VLC streaming"""
        self._is_running = False
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None


class SoxAudioPlayer:
    """
    Local audio playback using sox
    Alternative to VLC for direct speaker output
    """

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running and self.process is not None

    def start(self, sample_rate: int = 24000) -> bool:
        """Start audio playback via sox/play"""
        if self.is_running:
            self.stop()

        # Sox play command for raw audio input
        cmd = [
            'play',
            '-q',                    # Quiet
            '-t', 'raw',             # Raw input
            '-r', str(sample_rate),  # Sample rate
            '-e', 'signed',          # Signed integers
            '-b', '16',              # 16-bit
            '-c', '1',               # Mono
            '-'                      # Read from stdin
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self._is_running = True
            return True
        except FileNotFoundError:
            print("Warning: sox not found. Install sox package for audio playback.")
            return False
        except Exception as e:
            print(f"Error starting sox: {e}")
            return False

    def write_audio(self, data: bytes):
        """Write audio data to sox stdin"""
        if self.is_running and self.process and self.process.stdin:
            try:
                self.process.stdin.write(data)
                self.process.stdin.flush()
            except (BrokenPipeError, OSError):
                self._is_running = False

    def stop(self):
        """Stop audio playback"""
        self._is_running = False
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None


class AudioManager:
    """
    Manages RTL-SDR audio capture, recording, and streaming
    Combines all components into unified interface
    """

    def __init__(self, config: dict = None):
        config = config or {}

        self.rtl = RTLFMProcess(device_index=config.get('device_index', 0))
        self.recorder = AudioRecorder(output_dir=config.get('recordings_dir', 'recordings'))
        self.vlc_streamer = VLCStreamer(port=config.get('stream_port', 8080))
        self.player = SoxAudioPlayer()

        self._processing_thread: Optional[threading.Thread] = None
        self._is_processing = False

        # Options
        self.enable_recording = False
        self.enable_streaming = False
        self.enable_playback = False

    def start_monitoring(self, frequency: int, channel_name: str = "Unknown",
                         modulation: str = "fm", gain: int = 40,
                         squelch: int = 0, sample_rate: int = 24000,
                         record: bool = False, stream: bool = False,
                         playback: bool = False) -> bool:
        """
        Start monitoring a frequency with optional recording/streaming

        Args:
            frequency: Frequency in Hz
            channel_name: Name for recording files
            modulation: fm, wbfm, am, lsb, usb, raw
            gain: RF gain
            squelch: Squelch level
            sample_rate: Audio sample rate
            record: Enable recording to file
            stream: Enable VLC network streaming
            playback: Enable local audio playback
        """
        # Stop any existing monitoring
        self.stop_monitoring()

        # Parse modulation
        try:
            mod = Modulation(modulation.lower())
        except ValueError:
            mod = Modulation.FM

        # Start RTL-SDR
        if not self.rtl.start(frequency, mod, gain, squelch, sample_rate):
            return False

        self.enable_recording = record
        self.enable_streaming = stream
        self.enable_playback = playback

        # Start recording if enabled
        if record:
            self.recorder.start_recording(channel_name, sample_rate)

        # Start VLC streaming if enabled
        if stream:
            self.vlc_streamer.start(sample_rate)

        # Start local playback if enabled
        if playback:
            self.player.start(sample_rate)

        # Start audio processing thread
        self._is_processing = True
        self._processing_thread = threading.Thread(
            target=self._process_audio,
            daemon=True
        )
        self._processing_thread.start()

        return True

    def stop_monitoring(self) -> Optional[dict]:
        """Stop all monitoring and return recording info if any"""
        self._is_processing = False

        self.rtl.stop()
        self.vlc_streamer.stop()
        self.player.stop()

        recording_info = None
        if self.enable_recording:
            recording_info = self.recorder.stop_recording()

        return recording_info

    def _process_audio(self):
        """Process audio from RTL-SDR and route to outputs"""
        while self._is_processing and self.rtl.is_running:
            chunk = self.rtl.get_audio_chunk(timeout=0.5)
            if not chunk:
                continue

            # Route to recording
            if self.enable_recording and self.recorder.is_recording:
                self.recorder.write_audio(chunk)

            # Route to VLC streaming
            if self.enable_streaming and self.vlc_streamer.is_running:
                self.vlc_streamer.write_audio(chunk)

            # Route to local playback
            if self.enable_playback and self.player.is_running:
                self.player.write_audio(chunk)

    def get_status(self) -> dict:
        """Get current status"""
        return {
            'monitoring': self.rtl.is_running,
            'frequency': self.rtl.frequency,
            'modulation': self.rtl.modulation.value,
            'gain': self.rtl.gain,
            'squelch': self.rtl.squelch,
            'signal_level': self.rtl.get_signal_level(),
            'recording': self.recorder.is_recording,
            'streaming': self.vlc_streamer.is_running,
            'stream_url': self.vlc_streamer.stream_url if self.vlc_streamer.is_running else None,
            'playback': self.player.is_running
        }


# Test/demo
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='RTL-SDR Audio Streamer')
    parser.add_argument('-f', '--frequency', type=float, required=True,
                        help='Frequency in MHz (e.g., 146.52)')
    parser.add_argument('-m', '--modulation', default='fm',
                        choices=['fm', 'wbfm', 'am', 'lsb', 'usb', 'raw'],
                        help='Modulation mode')
    parser.add_argument('-g', '--gain', type=int, default=40,
                        help='RF gain (0-50)')
    parser.add_argument('-s', '--squelch', type=int, default=0,
                        help='Squelch level')
    parser.add_argument('-r', '--record', action='store_true',
                        help='Record to file')
    parser.add_argument('--stream', action='store_true',
                        help='Enable VLC network streaming')
    parser.add_argument('-p', '--playback', action='store_true',
                        help='Enable local audio playback')

    args = parser.parse_args()

    freq_hz = int(args.frequency * 1_000_000)

    print(f"Starting monitoring: {args.frequency} MHz ({args.modulation})")

    manager = AudioManager()

    def signal_handler(sig, frame):
        print("\nStopping...")
        info = manager.stop_monitoring()
        if info:
            print(f"Recording saved: {info['path']}")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    manager.start_monitoring(
        frequency=freq_hz,
        channel_name=f"test_{args.frequency}",
        modulation=args.modulation,
        gain=args.gain,
        squelch=args.squelch,
        record=args.record,
        stream=args.stream,
        playback=args.playback
    )

    print("Monitoring... Press Ctrl+C to stop")

    if args.stream:
        print(f"Stream available at: {manager.vlc_streamer.stream_url}")

    # Status updates
    while True:
        status = manager.get_status()
        level = status['signal_level']
        bar = '=' * int(level / 2) + ' ' * (50 - int(level / 2))
        print(f"\rSignal: [{bar}] {level:.1f}%", end='', flush=True)
        time.sleep(0.2)
