import serial
import time
import struct
import numpy as np
import sys
import csv
import datetime  # Für Zeitstempel in der CSV

CFG_PORT = '/dev/ttyUSB0'
DATA_PORT = '/dev/ttyUSB1'
CFG_FILE = 'profile.cfg'

RANGE_BINS = 256
# aus profileCfg: 3e8 * 6000 / (2 * 70e6 * 256)
RANGE_RES = 0.0502  # ca. 5 cm pro Bin


# -------------------------------------

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
    print("ready")


def parse_data(data_port):
    MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'
    THRESHOLD = 800

    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    csv_filename = f"radar_log_{timestamp_str}.csv"

    print(f"Schreibe Daten in: {csv_filename}")

    # Datei öffnen
    with open(csv_filename, mode='w', newline='') as csv_file:
        writer = csv.writer(csv_file, delimiter=';')

        # Header schreiben (Spaltennamen)
        writer.writerow(["Timestamp", "Angle_Deg", "Distance_m", "Signal_Strength"])

        with serial.Serial(data_port, 921600, timeout=1) as ser:
            print(f"Start Serial Stream...")
            byte_buffer = b''

            while True:
                new_data = ser.read(ser.in_waiting or 128)
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

                        found_heatmap = False

                        for tlv in range(num_tlvs):
                            try:
                                tlv_type, tlv_len = struct.unpack('2I', packet_data[current_idx: current_idx + 8])
                                current_idx += 8
                                payload = packet_data[current_idx: current_idx + tlv_len]

                                if tlv_type == 4:  # Heatmap
                                    found_heatmap = True
                                    raw_data = np.frombuffer(payload, dtype=np.int16)

                                    total_values = len(raw_data)
                                    azimuth_bins = total_values // RANGE_BINS

                                    if azimuth_bins > 0:
                                        # Matrix wiederherstellen: [Entfernung, Winkel]
                                        heatmap = raw_data.reshape(RANGE_BINS, azimuth_bins)
                                        heatmap = np.abs(heatmap)

                                        # --- NAHBEREICH FILTERN ---
                                        SKIP_BINS = 8  # ca 40cm Blindbereich
                                        heatmap[:SKIP_BINS, :] = 0

                                        # --- WINKEL-SCAN ---
                                        # Nur printen, wenn auch was gefunden wird, sonst flutet das die Konsole
                                        print("-" * 60)

                                        for a_idx in range(azimuth_bins):
                                            # Hole die Spalte für diesen Winkel
                                            angle_col = heatmap[:, a_idx]

                                            # Finde ALLE Indizes über dem Threshold
                                            hits = np.where(angle_col > THRESHOLD)[0]

                                            # ERSTEN (hits[0]) -> Das ist das "nächste" Objekt am Sensor
                                            if len(hits) > 0:
                                                r_idx = hits[0]
                                                dist = r_idx * RANGE_RES

                                                # Hole die Signalstärke
                                                signal_strength = angle_col[r_idx]

                                                w_norm = (2.0 * a_idx / (azimuth_bins - 1)) - 1.0

                                                if abs(w_norm) <= 1.0:
                                                    angle_rad = np.arcsin(w_norm)
                                                    angle_deg = np.degrees(angle_rad)
                                                    angle_deg = -angle_deg  # Vorzeichenkorrektur

                                                    # FOV FILTER
                                                    if abs(angle_deg) > 60.0:
                                                        continue

                                                    # Einfache ASCII-Visualisierung
                                                    bar_len = dist * 10
                                                    strength_bar = "#" * int(dist * 10)

                                                    # 1. Print in Konsole
                                                    print(
                                                        f"Winkel {angle_deg:6.1f}° | Dist: {dist:5.2f}m | Sig: {signal_strength:4} | {strength_bar}")

                                                    # 2. Schreiben in CSV
                                                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                                                    writer.writerow([timestamp, f"{angle_deg:.2f}", f"{dist:.4f}", signal_strength])

                                                    # Puffer leeren, damit Daten sofort auf Platte sind
                                                    csv_file.flush()

                                current_idx += tlv_len
                            except struct.error:
                                break

                    except struct.error:
                        byte_buffer = byte_buffer[8:]


if __name__ == "__main__":
    # Config senden beim Start
    try:
        with serial.Serial(CFG_PORT, 115200, timeout=1) as cfg_ser:
            send_config(cfg_ser, CFG_FILE)
    except Exception as e:
        print(f"Konnte Config nicht senden: {e}")

    try:
        parse_data(DATA_PORT)
    except KeyboardInterrupt:
        print("Ende")