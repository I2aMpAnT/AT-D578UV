#!/usr/bin/env python3
"""
AT-D578UV RTL-SDR Scanner Web Portal
Web interface for multi-channel monitoring, recording, and transcription
For Raspberry Pi deployment

GMRS License: WSKW654
"""

import os
import sys
import json
import time
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from functools import wraps

from flask import Flask, render_template, request, jsonify, send_file, Response
from flask_socketio import SocketIO, emit

# Import our scanner module
from rtl_scanner import (
    RTLSDRScanner, TranscriptionService, Channel, Recording,
    DEFAULT_CONFIG, ChannelType
)

# Import audio streaming module (based on rtl_fm_python, K0NYC/rtl-fm patterns)
from audio_streamer import AudioManager, Modulation

# Flask app setup
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'drn-scanner-portal-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global scanner instance
scanner: RTLSDRScanner = None
transcriber: TranscriptionService = None
audio_manager: AudioManager = None

# State
state = {
    'scanning': False,
    'recording': False,
    'current_channel': None,
    'signal_detected': False,
    'recordings': [],
    'streaming': False,
    'playback': False
}


def init_scanner():
    """Initialize the scanner with configuration"""
    global scanner, transcriber, audio_manager

    scanner = RTLSDRScanner()

    # Load channels from CSV
    csv_path = Path(__file__).parent / 'DRN_channels.csv'
    if csv_path.exists():
        scanner.load_channels_from_csv(str(csv_path))

    # Add encryption keys
    for key_id, key_hex in DEFAULT_CONFIG['encryption_keys'].items():
        scanner.add_encryption_key(key_id, key_hex)

    # Set up callbacks
    scanner.on_signal_detected = on_signal_detected
    scanner.on_recording_complete = on_recording_complete

    # Initialize audio manager for enhanced streaming
    recordings_path = DEFAULT_CONFIG.get('paths', {}).get('recordings', 'recordings')
    audio_manager = AudioManager({
        'device_index': DEFAULT_CONFIG.get('rtl_sdr', {}).get('device_index', 0),
        'recordings_dir': recordings_path,
        'stream_port': 8080
    })

    # Initialize transcription service (lazy load)
    # transcriber = TranscriptionService(model_size="base")

    print(f"Scanner initialized with {len(scanner.channels)} channels")
    print(f"Audio manager ready (VLC stream port: 8080)")


def on_signal_detected(channel: Channel):
    """Callback when signal is detected"""
    state['signal_detected'] = True
    state['current_channel'] = channel.number
    socketio.emit('signal_detected', {
        'channel': channel.number,
        'name': channel.name,
        'frequency': channel.rx_freq,
        'encrypted': channel.encryption
    })


def on_recording_complete(recording: Recording):
    """Callback when recording is complete"""
    rec_data = {
        'filename': recording.filename,
        'channel': recording.channel,
        'start_time': recording.start_time.isoformat(),
        'duration': recording.duration,
        'encrypted': recording.is_encrypted,
        'transcription': recording.transcription
    }
    state['recordings'].append(rec_data)
    socketio.emit('recording_complete', rec_data)


# Flask Routes
@app.route('/')
def index():
    """Main scanner interface (original)"""
    return render_template('scanner.html')


@app.route('/v2')
def index_v2():
    """Scanner interface v2 (Rdio Scanner style)"""
    return render_template('scanner_v2.html')


@app.route('/api/channels')
def get_channels():
    """Get all channel configurations"""
    if not scanner:
        return jsonify({'error': 'Scanner not initialized'}), 500
    return jsonify(scanner.get_channel_list())


@app.route('/api/channels/encrypted')
def get_encrypted_channels():
    """Get encrypted channels only"""
    if not scanner:
        return jsonify({'error': 'Scanner not initialized'}), 500
    channels = scanner.get_encrypted_channels()
    return jsonify([{
        'number': ch.number,
        'name': ch.name,
        'frequency': ch.rx_freq,
        'key_id': ch.encryption_key_id
    } for ch in channels])


@app.route('/api/channels/analog')
def get_analog_channels():
    """Get analog channels only"""
    if not scanner:
        return jsonify({'error': 'Scanner not initialized'}), 500
    channels = scanner.get_analog_channels()
    return jsonify([{
        'number': ch.number,
        'name': ch.name,
        'frequency': ch.rx_freq
    } for ch in channels])


@app.route('/api/devices')
def get_devices():
    """Get available RTL-SDR devices"""
    if not scanner:
        return jsonify({'error': 'Scanner not initialized'}), 500
    return jsonify({'devices': scanner.get_rtl_devices()})


@app.route('/api/tune/<int:channel_num>', methods=['POST'])
def tune_channel(channel_num):
    """Tune to a specific channel"""
    if not scanner:
        return jsonify({'error': 'Scanner not initialized'}), 500

    success = scanner.tune_channel(channel_num)
    if success:
        state['current_channel'] = channel_num
        socketio.emit('channel_changed', {
            'channel': channel_num,
            'name': scanner.current_channel.name,
            'frequency': scanner.current_channel.rx_freq
        })
        return jsonify({'success': True, 'channel': channel_num})
    return jsonify({'success': False, 'error': 'Channel not found'}), 404


def audio_stream_callback(audio_data):
    """Callback to stream audio data to browser via WebSocket"""
    socketio.emit('audio_data', {'data': audio_data})


@app.route('/api/tune/frequency', methods=['POST'])
def tune_frequency():
    """Tune directly to a frequency in MHz"""
    if not scanner:
        return jsonify({'error': 'Scanner not initialized'}), 500

    data = request.json or {}
    freq_mhz = data.get('frequency')

    if not freq_mhz:
        return jsonify({'error': 'Frequency required'}), 400

    try:
        freq_mhz = float(freq_mhz)
    except ValueError:
        return jsonify({'error': 'Invalid frequency'}), 400

    # Pass callback to stream audio to browser
    success = scanner.tune_frequency(freq_mhz, audio_callback=audio_stream_callback)
    if success:
        socketio.emit('frequency_changed', {
            'frequency': freq_mhz,
            'name': 'Manual Tune'
        })
        return jsonify({'success': True, 'frequency': freq_mhz})
    return jsonify({'success': False, 'error': 'Failed to tune'}), 500


@app.route('/api/monitor/start/<int:channel_num>', methods=['POST'])
def start_monitoring(channel_num):
    """Start monitoring a channel with browser audio streaming"""
    if not scanner:
        return jsonify({'error': 'Scanner not initialized'}), 500

    success = scanner.start_monitoring(channel_num, audio_callback=audio_stream_callback)
    if success:
        state['scanning'] = True
        return jsonify({'success': True, 'message': f'Monitoring channel {channel_num}'})
    return jsonify({'success': False, 'error': 'Failed to start monitoring'}), 500


@app.route('/api/monitor/stop', methods=['POST'])
def stop_monitoring():
    """Stop monitoring"""
    if scanner:
        scanner.stop_monitoring()
        state['scanning'] = False
    return jsonify({'success': True})


@app.route('/api/record/start/<int:channel_num>', methods=['POST'])
def start_recording(channel_num):
    """Start recording a channel"""
    if not scanner:
        return jsonify({'error': 'Scanner not initialized'}), 500

    # First start monitoring if not already
    if not state['scanning']:
        scanner.start_monitoring(channel_num)

    filepath = scanner.start_recording(channel_num)
    if filepath:
        state['recording'] = True
        return jsonify({'success': True, 'filename': filepath})
    return jsonify({'success': False, 'error': 'Failed to start recording'}), 500


@app.route('/api/record/stop', methods=['POST'])
def stop_recording():
    """Stop recording"""
    if scanner:
        scanner.stop_recording()
        state['recording'] = False
    return jsonify({'success': True})


@app.route('/api/scan/start', methods=['POST'])
def start_scan():
    """Start scanning all channels"""
    if not scanner:
        return jsonify({'error': 'Scanner not initialized'}), 500

    data = request.json or {}
    channel_list = data.get('channels')  # Optional specific channel list
    dwell_time = data.get('dwell_time', 2.0)

    # Run scan in background thread
    threading.Thread(
        target=scanner.scan_channels,
        args=(channel_list, dwell_time),
        daemon=True
    ).start()

    state['scanning'] = True
    return jsonify({'success': True, 'message': 'Scan started'})


@app.route('/api/scan/stop', methods=['POST'])
def stop_scan():
    """Stop scanning"""
    if scanner:
        scanner.is_scanning = False
        state['scanning'] = False
    return jsonify({'success': True})


@app.route('/api/recordings')
def get_recordings():
    """Get list of recordings"""
    recordings_dir = Path(__file__).parent / 'recordings'
    recordings = []

    if recordings_dir.exists():
        for f in recordings_dir.glob('*.wav'):
            stat = f.stat()
            recordings.append({
                'filename': f.name,
                'path': str(f),
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat()
            })

    return jsonify(sorted(recordings, key=lambda x: x['created'], reverse=True))


@app.route('/api/recordings/<filename>')
def get_recording(filename):
    """Download a recording"""
    recordings_dir = Path(__file__).parent / 'recordings'
    filepath = recordings_dir / filename

    if filepath.exists() and filepath.suffix == '.wav':
        return send_file(filepath, mimetype='audio/wav')
    return jsonify({'error': 'Recording not found'}), 404


@app.route('/api/recordings/<filename>/transcribe', methods=['POST'])
def transcribe_recording(filename):
    """Transcribe a recording"""
    global transcriber

    if not transcriber:
        try:
            transcriber = TranscriptionService(model_size="base")
        except Exception as e:
            return jsonify({'error': f'Transcription service unavailable: {e}'}), 500

    recordings_dir = Path(__file__).parent / 'recordings'
    filepath = recordings_dir / filename

    if not filepath.exists():
        return jsonify({'error': 'Recording not found'}), 404

    text = transcriber.transcribe(str(filepath))
    if text:
        return jsonify({'success': True, 'transcription': text})
    return jsonify({'success': False, 'error': 'Transcription failed'}), 500


@app.route('/api/status')
def get_status():
    """Get current scanner status"""
    return jsonify({
        'scanning': state['scanning'],
        'recording': state['recording'],
        'current_channel': state['current_channel'],
        'signal_detected': state['signal_detected'],
        'scanner_ready': scanner is not None,
        'channel_count': len(scanner.channels) if scanner else 0
    })


# WebSocket Events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    emit('status', {
        'scanning': state['scanning'],
        'recording': state['recording'],
        'current_channel': state['current_channel']
    })


@socketio.on('tune')
def handle_tune(data):
    """Handle tune request via WebSocket"""
    channel_num = data.get('channel')
    if scanner and channel_num:
        success = scanner.tune_channel(channel_num)
        emit('tune_response', {
            'success': success,
            'channel': channel_num
        })


@socketio.on('monitor_start')
def handle_monitor_start(data):
    """Start monitoring via WebSocket"""
    channel_num = data.get('channel')
    if scanner and channel_num:
        success = scanner.start_monitoring(channel_num)
        state['scanning'] = success
        emit('monitor_response', {'success': success, 'channel': channel_num})


@socketio.on('monitor_stop')
def handle_monitor_stop():
    """Stop monitoring via WebSocket"""
    if scanner:
        scanner.stop_monitoring()
        state['scanning'] = False
    emit('monitor_response', {'success': True, 'stopped': True})


# Audio streaming endpoint (original)
@app.route('/api/audio/stream')
def audio_stream():
    """Stream live audio (experimental)"""
    def generate():
        while state['scanning'] and scanner:
            try:
                data = scanner.audio_queue.get(timeout=1)
                yield data
            except:
                continue

    return Response(
        generate(),
        mimetype='audio/raw',
        headers={'Cache-Control': 'no-cache'}
    )


# Enhanced Audio Streaming API (using audio_streamer module)
@app.route('/api/v2/stream/start/<int:channel_num>', methods=['POST'])
def start_stream(channel_num):
    """Start enhanced audio streaming with VLC"""
    if not scanner or not audio_manager:
        return jsonify({'error': 'Scanner not initialized'}), 500

    channel = scanner.channels.get(channel_num)
    if not channel:
        return jsonify({'error': 'Channel not found'}), 404

    data = request.json or {}
    record = data.get('record', False)
    stream = data.get('stream', True)
    playback = data.get('playback', False)

    # Convert frequency from MHz to Hz
    freq_hz = int(channel.rx_freq * 1_000_000)

    # Determine modulation based on channel type
    modulation = 'fm'  # Default to narrowband FM
    if channel.channel_type == ChannelType.DIGITAL:
        modulation = 'fm'  # DMR uses FM modulation at RF level

    success = audio_manager.start_monitoring(
        frequency=freq_hz,
        channel_name=channel.name,
        modulation=modulation,
        gain=DEFAULT_CONFIG.get('rtl_sdr', {}).get('gain', 40),
        squelch=DEFAULT_CONFIG.get('rtl_sdr', {}).get('squelch_level', 0),
        sample_rate=DEFAULT_CONFIG.get('rtl_sdr', {}).get('sample_rate', 24000),
        record=record,
        stream=stream,
        playback=playback
    )

    if success:
        state['streaming'] = stream
        state['recording'] = record
        state['playback'] = playback
        state['current_channel'] = channel_num

        return jsonify({
            'success': True,
            'channel': channel_num,
            'stream_url': f'http://localhost:8080/stream.ogg' if stream else None,
            'recording': record,
            'playback': playback
        })

    return jsonify({'success': False, 'error': 'Failed to start streaming'}), 500


@app.route('/api/v2/stream/stop', methods=['POST'])
def stop_stream():
    """Stop enhanced audio streaming"""
    if audio_manager:
        recording_info = audio_manager.stop_monitoring()
        state['streaming'] = False
        state['playback'] = False

        if recording_info:
            socketio.emit('recording_complete', recording_info)
            return jsonify({'success': True, 'recording': recording_info})

    return jsonify({'success': True})


@app.route('/api/v2/stream/status')
def stream_status():
    """Get enhanced stream status"""
    if audio_manager:
        status = audio_manager.get_status()
        return jsonify(status)
    return jsonify({'error': 'Audio manager not initialized'}), 500


@app.route('/api/v2/signal')
def get_signal_level():
    """Get current signal level"""
    if audio_manager:
        level = audio_manager.rtl.get_signal_level()
        return jsonify({'signal_level': level})
    return jsonify({'signal_level': 0})


if __name__ == '__main__':
    print("=" * 60)
    print("AT-D578UV RTL-SDR Scanner Web Portal")
    print("GMRS License: WSKW654")
    print("=" * 60)

    # Initialize scanner
    init_scanner()

    print(f"\nStarting server on http://0.0.0.0:5001")
    print(f"  Original UI: http://0.0.0.0:5001/")
    print(f"  Scanner v2:  http://0.0.0.0:5001/v2")
    print(f"  VLC Stream:  http://0.0.0.0:8080/stream.ogg")
    print("=" * 60)

    socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)
