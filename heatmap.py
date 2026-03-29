import serial
import time
import struct
import numpy as np
import threading
import json
from flask import Flask, jsonify, render_template_string

# --- Config ---
CFG_PORT = '/dev/ttyUSB0'
DATA_PORT = '/dev/ttyUSB1'
CFG_FILE = 'profile.cfg'

# muss zur profile.cfg passen
RANGE_BINS = 256
RANGE_RES = 0.0502  # m pro Bin

# Globale Variable
current_heatmap = {
    "data": [],
    "azimuth_bins": 0
}

app = Flask(__name__)


# ---------------------------------------------------------
# RADAR THREAD
# ---------------------------------------------------------
def send_config(ser, cfg_file):
    print(f"Sende Config an {CFG_PORT}...")
    with open(cfg_file, 'r') as f:
        lines = f.readlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith('%'): continue
        ser.write((line + '\n').encode())
        time.sleep(0.05)
    time.sleep(1)
    print("Config ready")


def radar_thread_func():
    global current_heatmap
    MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'

    try:
        with serial.Serial(CFG_PORT, 115200, timeout=1) as cfg_ser:
            send_config(cfg_ser, CFG_FILE)
    except Exception as e:
        print(f"Config Fehler: {e}")

    print("Starte Raw Heatmap Stream...")

    with serial.Serial(DATA_PORT, 921600, timeout=2) as ser:
        byte_buffer = b''

        while True:
            new_data = ser.read(ser.in_waiting or 4096)

            if new_data:
                byte_buffer += new_data

            idx = byte_buffer.find(MAGIC_WORD)
            if idx != -1:
                byte_buffer = byte_buffer[idx:]

                if len(byte_buffer) < 40: continue

                try:
                    header = struct.unpack('8I', byte_buffer[8:40])
                    total_len = header[1]
                    num_tlvs = header[6]

                    if len(byte_buffer) < total_len: continue

                    packet_data = byte_buffer[:total_len]
                    byte_buffer = byte_buffer[total_len:]

                    current_idx = 40

                    for tlv in range(num_tlvs):
                        try:
                            tlv_type, tlv_len = struct.unpack('2I', packet_data[current_idx: current_idx + 8])
                            current_idx += 8
                            payload = packet_data[current_idx: current_idx + tlv_len]

                            if tlv_type == 4:  # Heatmap
                                raw_data = np.frombuffer(payload, dtype=np.int16)
                                total_values = len(raw_data)

                                if total_values > 0:
                                    azimuth_bins = total_values // RANGE_BINS

                                    if azimuth_bins > 0:
                                        heatmap = raw_data.reshape(RANGE_BINS, azimuth_bins)
                                        heatmap = np.abs(heatmap)
                                        heatmap_db = 20 * np.log10(heatmap + 1)
                                        heatmap_db[:8, :] = 0  # Nahbereich löschen
                                        heatmap_int = heatmap_db.astype(int).tolist()

                                        current_heatmap = {
                                            "data": heatmap_int,
                                            "azimuth_bins": azimuth_bins
                                        }

                            current_idx += tlv_len
                        except struct.error:
                            break

                except struct.error:
                    byte_buffer = byte_buffer[8:]


# ---------------------------------------------------------
# WEB UI
# ---------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Radar Dashboard</title>
    <style>
        body, html {
            margin: 0; padding: 0; width: 100%; height: 100%;
            background: #000; color: #ccc; font-family: sans-serif;
            overflow: hidden; display: flex; flex-direction: column;
        }
        .radar-container {
            flex-grow: 1; position: relative; background: #050505;
            width: 100%; overflow: hidden;
        }
        #radarCanvas { display: block; width: 100%; height: 100%; }
        .stats {
            position: absolute; top: 15px; left: 15px; color: #0f0;
            font-family: monospace; font-size: 14px; pointer-events: none;
            background: rgba(0,0,0,0.6); padding: 5px 10px; border-radius: 4px;
        }
        .legend-container {
            position: absolute; right: 15px; top: 20px; bottom: 20px; width: 30px;
            display: flex; flex-direction: column; align-items: center;
            background: rgba(0, 0, 0, 0.5); border-radius: 8px; padding: 5px 0; border: 1px solid #333;
        }
        .legend-bar {
            flex-grow: 1; width: 12px;
            background: linear-gradient(to top, blue, cyan, lime, yellow, red);
            border-radius: 2px;
        }
        .legend-label { font-size: 11px; margin: 4px 0; color: #fff; font-weight: bold;}
        .controls-deck { 
            height: 100px; background: #181818; border-top: 1px solid #333;
            display: flex; justify-content: center; align-items: center; padding: 0 20px;
            box-shadow: 0 -5px 10px rgba(0,0,0,0.5); z-index: 50;
        }
        .control-wrapper { width: 800px; display: flex; justify-content: space-between; gap: 40px; }
        .control-group { text-align: center; flex: 1; }
        label { display: block; font-size: 12px; margin-bottom: 8px; color: #aaa; text-transform: uppercase; letter-spacing: 1px;}
        input[type=range] { width: 100%; cursor: pointer; height: 6px; background: #333; border-radius: 3px; -webkit-appearance: none; }
        input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; width: 18px; height: 18px; background: #fff; border-radius: 50%; cursor: pointer; margin-top: -6px; box-shadow: 0 0 5px rgba(0,0,0,0.5); }
        .val-display { color: #fff; font-weight: bold; font-size: 16px; margin-top: 5px;}
    </style>
</head>
<body>
    <div class="radar-container" id="radarContainer">
        <div class="stats" id="statsDisplay">Verbinde...</div>
        <div class="legend-container">
            <div class="legend-label" id="legendMax">80</div>
            <div class="legend-bar"></div>
            <div class="legend-label" id="legendMin">40</div>
        </div>
        <canvas id="radarCanvas"></canvas>
    </div>
    <div class="controls-deck">
        <div class="control-wrapper">
            <div class="control-group">
                <label>Min dB</label>
                <input type="range" id="minDb" min="10" max="70" value="40" oninput="updateSettings()">
                <div class="val-display">Min: <span id="minVal">45</span> dB</div>
            </div>
            <div class="control-group">
                <label>Max dB</label>
                <input type="range" id="maxDb" min="40" max="100" value="70" oninput="updateSettings()">
                <div class="val-display">Max: <span id="maxVal">75</span> dB</div>
            </div>
        </div>
    </div>

    <script>
        const canvas = document.getElementById('radarCanvas');
        const container = document.getElementById('radarContainer');
        const ctx = canvas.getContext('2d');
        let width, height;

        // Range einstellen hier //  -------------
        const maxRangeMeters = 7.0; 
        const RANGE_RES = 0.0502; // muss zum Python Wert passen

        let minDbDisplay = 40;
        let maxDbDisplay = 70;

        function resize() {
            width = container.clientWidth;
            height = container.clientHeight;
            canvas.width = width;
            canvas.height = height;
        }
        window.addEventListener('resize', resize);
        resize();

        function updateSettings() {
            minDbDisplay = parseInt(document.getElementById('minDb').value);
            maxDbDisplay = parseInt(document.getElementById('maxDb').value);
            document.getElementById('minVal').innerText = minDbDisplay;
            document.getElementById('maxVal').innerText = maxDbDisplay;
            document.getElementById('legendMin').innerText = minDbDisplay;
            document.getElementById('legendMax').innerText = maxDbDisplay;
        }

        function getColor(db) {
            if (db < minDbDisplay) return null;
            let range = maxDbDisplay - minDbDisplay;
            if (range <= 0) range = 1;
            let ratio = (db - minDbDisplay) / range;
            ratio = Math.max(0, Math.min(1, ratio));
            let colorCurve = Math.sqrt(ratio); 
            let hue = (1.0 - colorCurve) * 240;
            return `hsl(${hue}, 100%, 50%)`;
        }

        function updateData() {
            fetch('/data')
                .then(response => response.json())
                .then(json => {
                    if (!json.data || json.data.length === 0) return;

                    ctx.clearRect(0, 0, width, height);
                    const centerX = width / 2;
                    const bottomY = height;
                    const scalePxPerMeter = (height - 10) / maxRangeMeters;
                    const rows = json.data.length;
                    const cols = json.azimuth_bins;
                    let frameMax = 0;

                    for (let r = 0; r < rows; r++) {
                        let dist = r * RANGE_RES;
                        if (dist > maxRangeMeters) continue;
                        let r_px = dist * scalePxPerMeter;

                        for (let a = 0; a < cols; a++) {
                            let val = json.data[r][a];
                            if (val > frameMax) frameMax = val;

                            let color = getColor(val);
                            if (!color) continue;

                            let w_norm = (2.0 * a / (cols - 1)) - 1.0;
                            if (w_norm > 1.0) w_norm = 1.0;
                            if (w_norm < -1.0) w_norm = -1.0;

                            let angleRad = Math.asin(w_norm);

                            let x_offset = r_px * Math.sin(angleRad);
                            let y_offset = r_px * Math.cos(angleRad);

                            let cx = centerX + x_offset;
                            let cy = bottomY - y_offset;

                            let size = Math.max(3, r_px * 0.035) + 1; 

                            ctx.fillStyle = color;
                            ctx.fillRect(cx - size/2, cy - size/2, size + 0.5, size + 0.5);
                        }
                    }

                    // Text Styling
                    ctx.textAlign = "center";
                    ctx.font = "bold 12px sans-serif";
                    ctx.fillStyle = "#fff"; 

                    for(let m=1; m<=maxRangeMeters; m++) {
                        let r_px = m * scalePxPerMeter;

                        // Halbkreis
                        ctx.beginPath();
                        ctx.arc(centerX, bottomY, r_px, Math.PI, 0);
                        ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)'; 
                        ctx.lineWidth = 1;
                        ctx.stroke();

                        // Text mit Outline (Rand) für Lesbarkeit auf buntem Grund
                        let textY = bottomY - r_px - 2;
                        ctx.lineWidth = 3; 
                        ctx.strokeStyle = 'rgba(0, 0, 0, 0.8)'; // Schwarzer Rand
                        ctx.strokeText(m+"m", centerX + 20, textY); 
                        ctx.fillText(m+"m", centerX + 20, textY); // Weißer Text
                    }

                    // Winkel Linien
                    ctx.lineWidth = 1;
                    ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)'; // Auch hier etwas heller
                    const angles = [-60, -30, 0, 30, 60];
                    angles.forEach(deg => {
                        let rad = (deg - 90) * (Math.PI / 180);
                        let lineLen = maxRangeMeters * scalePxPerMeter;
                        let ex = centerX + Math.cos(rad) * lineLen;
                        let ey = bottomY + Math.sin(rad) * lineLen;

                        ctx.beginPath();
                        ctx.moveTo(centerX, bottomY);
                        ctx.lineTo(ex, ey);
                        ctx.stroke();
                    });

                    document.getElementById('statsDisplay').innerText = `Max Peak: ${frameMax} dB`;
                })
                .catch(err => console.log(err));
        }
        setInterval(updateData, 100);
        updateSettings();
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/data')
def get_data():
    return jsonify(current_heatmap)


if __name__ == "__main__":
    t = threading.Thread(target=radar_thread_func)
    t.daemon = True
    t.start()
    app.run(host='0.0.0.0', port=5000, debug=False)