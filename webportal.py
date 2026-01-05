#!/usr/bin/env python3
"""
AT-D578UV Repeater Web Portal
A web-based interface for controlling the AnyTone AT-D578UVIII radio
"""

import os
import sys
import json
import time
import threading
import configparser
from datetime import datetime

from flask import Flask, render_template, request, jsonify, Response
from flask_socketio import SocketIO, emit

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("Warning: pyserial not installed. Serial communication disabled.")

# Configuration
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'at-d578uv-webportal-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global state
serial_connection = None
serial_lock = threading.Lock()
connection_status = {
    'connected': False,
    'port': None,
    'last_activity': None,
    'ptt_active': False
}

# Configuration file path
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'd578uv.conf')

# Button hex codes - press and release pairs
BUTTON_CODES = {
    'ptt': {
        'press': b'\x41\x01\x00\x00\x00\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x00\x00\x00\x06'
    },
    '0': {
        'press': b'\x41\x00\x01\x00\x01\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x01\x00\x00\x06'
    },
    '1': {
        'press': b'\x41\x00\x01\x00\x02\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x02\x00\x00\x06'
    },
    '2': {
        'press': b'\x41\x00\x01\x00\x03\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x03\x00\x00\x06'
    },
    '3': {
        'press': b'\x41\x00\x01\x00\x04\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x04\x00\x00\x06'
    },
    '4': {
        'press': b'\x41\x00\x01\x00\x05\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x05\x00\x00\x06'
    },
    '5': {
        'press': b'\x41\x00\x01\x00\x06\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x06\x00\x00\x06'
    },
    '6': {
        'press': b'\x41\x00\x01\x00\x07\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x07\x00\x00\x06'
    },
    '7': {
        'press': b'\x41\x00\x01\x00\x08\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x08\x00\x00\x06'
    },
    '8': {
        'press': b'\x41\x00\x01\x00\x09\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x09\x00\x00\x06'
    },
    '9': {
        'press': b'\x41\x00\x01\x00\x0a\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x0a\x00\x00\x06'
    },
    'star': {  # * button
        'press': b'\x41\x00\x01\x00\x0b\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x0b\x00\x00\x06'
    },
    'hash': {  # # button
        'press': b'\x41\x00\x01\x00\x0c\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x0c\x00\x00\x06'
    },
    'subab': {  # Sub A/B button
        'press': b'\x41\x00\x01\x00\x0d\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x0d\x00\x00\x06'
    },
    'up': {
        'press': b'\x41\x00\x01\x00\x10\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x10\x00\x00\x06'
    },
    'down': {
        'press': b'\x41\x00\x01\x00\x11\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x11\x00\x00\x06'
    },
    'a': {
        'press': b'\x41\x00\x01\x00\x1a\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x1a\x00\x00\x06'
    },
    'a_long': {
        'sequence': [
            b'\x41\x00\x01\x00\x1a\x00\x00\x06',
            b'\x41\x00\x01\x01\x1a\x00\x00\x06',
            b'\x41\x00\x00\x00\x1a\x00\x00\x06'
        ]
    },
    'b': {
        'press': b'\x41\x00\x01\x00\x1b\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x1b\x00\x00\x06'
    },
    'b_long': {
        'sequence': [
            b'\x41\x00\x01\x00\x1b\x00\x00\x06',
            b'\x41\x00\x01\x01\x1b\x00\x00\x06',
            b'\x41\x00\x00\x00\x1b\x00\x00\x06'
        ]
    },
    'c': {
        'press': b'\x41\x00\x01\x00\x1c\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x1c\x00\x00\x06'
    },
    'c_long': {
        'sequence': [
            b'\x41\x00\x01\x00\x1c\x00\x00\x06',
            b'\x41\x00\x01\x01\x1c\x00\x00\x06',
            b'\x41\x00\x00\x00\x1c\x00\x00\x06'
        ]
    },
    'd': {
        'press': b'\x41\x00\x01\x00\x1d\x00\x00\x06',
        'release': b'\x41\x00\x00\x00\x1d\x00\x00\x06'
    },
    'd_long': {
        'sequence': [
            b'\x41\x00\x01\x00\x1d\x00\x00\x06',
            b'\x41\x00\x01\x01\x1d\x00\x00\x06',
            b'\x41\x00\x00\x00\x1d\x00\x00\x06'
        ]
    }
}


def load_config():
    """Load configuration from d578uv.conf file"""
    config = configparser.ConfigParser()

    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    else:
        # Create default configuration
        config['Operator'] = {'callsign': 'NOCALL'}
        config['Serial'] = {
            'port': '/dev/ttyUSB0',
            'baudrate': '115200',
            'bytesize': 'EIGHTBITS',
            'parity': 'PARITY_NONE',
            'stopbits': 'STOPBITS_ONE',
            'timeout': '1',
            'pollinterval': '1',
            'xonxoff': 'FALSE'
        }
        save_config(config)

    return config


def save_config(config):
    """Save configuration to d578uv.conf file"""
    with open(CONFIG_FILE, 'w') as f:
        config.write(f)


def get_serial_params(config):
    """Convert config strings to pyserial parameters"""
    if not SERIAL_AVAILABLE:
        return None

    params = {
        'port': config.get('Serial', 'port', fallback='/dev/ttyUSB0'),
        'baudrate': int(config.get('Serial', 'baudrate', fallback='115200')),
        'timeout': int(config.get('Serial', 'timeout', fallback='1'))
    }

    # Bytesize
    bytesize_map = {
        'FIVEBITS': serial.FIVEBITS,
        'SIXBITS': serial.SIXBITS,
        'SEVENBITS': serial.SEVENBITS,
        'EIGHTBITS': serial.EIGHTBITS
    }
    params['bytesize'] = bytesize_map.get(
        config.get('Serial', 'bytesize', fallback='EIGHTBITS'),
        serial.EIGHTBITS
    )

    # Parity
    parity_map = {
        'PARITY_NONE': serial.PARITY_NONE,
        'PARITY_EVEN': serial.PARITY_EVEN,
        'PARITY_ODD': serial.PARITY_ODD,
        'PARITY_MARK': serial.PARITY_MARK,
        'PARITY_SPACE': serial.PARITY_SPACE
    }
    params['parity'] = parity_map.get(
        config.get('Serial', 'parity', fallback='PARITY_NONE'),
        serial.PARITY_NONE
    )

    # Stopbits
    stopbits_map = {
        'STOPBITS_ONE': serial.STOPBITS_ONE,
        'STOPBITS_ONE_POINT_FIVE': serial.STOPBITS_ONE_POINT_FIVE,
        'STOPBITS_TWO': serial.STOPBITS_TWO
    }
    params['stopbits'] = stopbits_map.get(
        config.get('Serial', 'stopbits', fallback='STOPBITS_ONE'),
        serial.STOPBITS_ONE
    )

    return params


def connect_serial():
    """Establish serial connection"""
    global serial_connection, connection_status

    if not SERIAL_AVAILABLE:
        return False, "pyserial not installed"

    config = load_config()
    params = get_serial_params(config)

    try:
        with serial_lock:
            if serial_connection and serial_connection.is_open:
                serial_connection.close()

            serial_connection = serial.Serial(**params)
            connection_status['connected'] = True
            connection_status['port'] = params['port']
            connection_status['last_activity'] = datetime.now().isoformat()

        # Start keep-alive thread
        threading.Thread(target=keep_alive_thread, daemon=True).start()

        return True, f"Connected to {params['port']}"
    except Exception as e:
        connection_status['connected'] = False
        return False, str(e)


def disconnect_serial():
    """Close serial connection"""
    global serial_connection, connection_status

    with serial_lock:
        if serial_connection and serial_connection.is_open:
            serial_connection.close()
        serial_connection = None
        connection_status['connected'] = False
        connection_status['port'] = None

    return True, "Disconnected"


def keep_alive_thread():
    """Send periodic keep-alive messages to radio"""
    global serial_connection, connection_status

    config = load_config()
    poll_interval = int(config.get('Serial', 'pollinterval', fallback='1'))

    while True:
        if not connection_status['connected']:
            break

        try:
            with serial_lock:
                if serial_connection and serial_connection.is_open:
                    serial_connection.write(b'\x06')
                    serial_connection.timeout = 0.1
                    response = serial_connection.read(1)
                    connection_status['last_activity'] = datetime.now().isoformat()
        except Exception as e:
            print(f"Keep-alive error: {e}")
            connection_status['connected'] = False
            break

        time.sleep(poll_interval)


def send_button_command(button_name, action='click'):
    """Send button command to radio"""
    global serial_connection, connection_status

    if not connection_status['connected']:
        return False, "Not connected"

    if button_name not in BUTTON_CODES:
        return False, f"Unknown button: {button_name}"

    button = BUTTON_CODES[button_name]

    try:
        with serial_lock:
            if not serial_connection or not serial_connection.is_open:
                return False, "Serial port not open"

            # Handle sequence buttons (long press)
            if 'sequence' in button:
                for cmd in button['sequence']:
                    serial_connection.write(cmd)
                    time.sleep(0.1)
                    serial_connection.timeout = 0.1
                    serial_connection.read(1)
            # Handle PTT specially
            elif button_name == 'ptt':
                if action == 'press':
                    serial_connection.write(button['press'])
                    connection_status['ptt_active'] = True
                elif action == 'release':
                    serial_connection.write(button['release'])
                    connection_status['ptt_active'] = False
                else:  # click
                    serial_connection.write(button['press'])
                    time.sleep(0.1)
                    serial_connection.write(button['release'])
                serial_connection.timeout = 0.1
                serial_connection.read(1)
            # Normal button press/release
            else:
                serial_connection.write(button['press'])
                time.sleep(0.1)
                serial_connection.timeout = 0.1
                serial_connection.read(1)
                serial_connection.write(button['release'])
                serial_connection.timeout = 0.1
                serial_connection.read(1)

            connection_status['last_activity'] = datetime.now().isoformat()

        return True, f"Button {button_name} {action}"
    except Exception as e:
        return False, str(e)


# Flask Routes
@app.route('/')
def index():
    """Main web interface"""
    config = load_config()
    callsign = config.get('Operator', 'callsign', fallback='NOCALL')
    return render_template('index.html', callsign=callsign)


@app.route('/api/status')
def api_status():
    """Get current connection status"""
    return jsonify(connection_status)


@app.route('/api/connect', methods=['POST'])
def api_connect():
    """Connect to serial port"""
    success, message = connect_serial()
    socketio.emit('status_update', connection_status)
    return jsonify({'success': success, 'message': message})


@app.route('/api/disconnect', methods=['POST'])
def api_disconnect():
    """Disconnect from serial port"""
    success, message = disconnect_serial()
    socketio.emit('status_update', connection_status)
    return jsonify({'success': success, 'message': message})


@app.route('/api/button/<button_name>', methods=['POST'])
def api_button(button_name):
    """Send button command"""
    action = request.json.get('action', 'click') if request.json else 'click'
    success, message = send_button_command(button_name, action)
    return jsonify({'success': success, 'message': message})


@app.route('/api/ports')
def api_ports():
    """List available serial ports"""
    if not SERIAL_AVAILABLE:
        return jsonify({'ports': [], 'error': 'pyserial not installed'})

    ports = [port.device for port in serial.tools.list_ports.comports()]
    return jsonify({'ports': ports})


@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    """Get or update configuration"""
    if request.method == 'GET':
        config = load_config()
        return jsonify({
            'callsign': config.get('Operator', 'callsign', fallback='NOCALL'),
            'port': config.get('Serial', 'port', fallback='/dev/ttyUSB0'),
            'baudrate': config.get('Serial', 'baudrate', fallback='115200'),
            'bytesize': config.get('Serial', 'bytesize', fallback='EIGHTBITS'),
            'parity': config.get('Serial', 'parity', fallback='PARITY_NONE'),
            'stopbits': config.get('Serial', 'stopbits', fallback='STOPBITS_ONE'),
            'timeout': config.get('Serial', 'timeout', fallback='1'),
            'pollinterval': config.get('Serial', 'pollinterval', fallback='1')
        })
    else:
        data = request.json
        config = load_config()

        if 'callsign' in data:
            config.set('Operator', 'callsign', data['callsign'][:6].upper())
        if 'port' in data:
            config.set('Serial', 'port', data['port'])
        if 'baudrate' in data:
            config.set('Serial', 'baudrate', str(data['baudrate']))
        if 'bytesize' in data:
            config.set('Serial', 'bytesize', data['bytesize'])
        if 'parity' in data:
            config.set('Serial', 'parity', data['parity'])
        if 'stopbits' in data:
            config.set('Serial', 'stopbits', data['stopbits'])
        if 'timeout' in data:
            config.set('Serial', 'timeout', str(data['timeout']))
        if 'pollinterval' in data:
            config.set('Serial', 'pollinterval', str(data['pollinterval']))

        save_config(config)
        return jsonify({'success': True, 'message': 'Configuration saved'})


# WebSocket Events
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    emit('status_update', connection_status)


@socketio.on('button_press')
def handle_button_press(data):
    """Handle button press from WebSocket"""
    button_name = data.get('button')
    action = data.get('action', 'click')
    success, message = send_button_command(button_name, action)
    emit('button_response', {'success': success, 'message': message, 'button': button_name})
    emit('status_update', connection_status)


@socketio.on('ptt_press')
def handle_ptt_press():
    """Handle PTT button press"""
    success, message = send_button_command('ptt', 'press')
    emit('ptt_response', {'success': success, 'message': message, 'active': True})
    emit('status_update', connection_status)


@socketio.on('ptt_release')
def handle_ptt_release():
    """Handle PTT button release"""
    success, message = send_button_command('ptt', 'release')
    emit('ptt_response', {'success': success, 'message': message, 'active': False})
    emit('status_update', connection_status)


# Create templates directory and HTML template
def create_templates():
    """Create the templates directory and index.html"""
    templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

    os.makedirs(templates_dir, exist_ok=True)
    os.makedirs(static_dir, exist_ok=True)

    # The HTML template will be created separately


if __name__ == '__main__':
    create_templates()
    print("=" * 50)
    print("AT-D578UV Repeater Web Portal")
    print("=" * 50)
    print(f"Serial available: {SERIAL_AVAILABLE}")
    print("Starting server on http://0.0.0.0:5000")
    print("=" * 50)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
