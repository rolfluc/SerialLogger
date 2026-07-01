import argparse
import datetime
import json
import os
import signal
import sys
import time
import re
import serial

# Global structures for continuous capture
raw_stream = ""
collected_timestamps = []

# High-resolution baseline reference time
BASE_WALL_TIME = datetime.datetime.now()
BASE_PERF_COUNTER = time.perf_counter()

def get_high_res_timestamp():
    """Calculates a high-precision timestamp using time.perf_counter() offsets."""
    elapsed_seconds = time.perf_counter() - BASE_PERF_COUNTER
    precise_time = BASE_WALL_TIME + datetime.timedelta(seconds=elapsed_seconds)
    return precise_time.strftime('%Y-%m-%d %H:%M:%S.%f')

def parse_arguments():
    """Handles CLI arguments."""
    parser = argparse.ArgumentParser(
        description="High-Precision Continuous Buffer Serial Reader."
    )
    parser.add_argument("-si", "--structuredIn", required=True, help="Path to configuration .json")
    parser.add_argument("-fo", "--fileOut", required=True, help="Path to output .csv")
    parser.add_argument("-sp", "--serialPort", required=True, help="Serial port (e.g. COM3 or /dev/ttyUSB0)")
    parser.add_argument("-br", "--baudRate", type=int, default=9600, help="Baud rate")
    return parser.parse_args()

def load_config(json_path):
    """Loads and validates the JSON configuration."""
    if not os.path.exists(json_path):
        print(f"[Error] Configuration file not found at: {json_path}")
        sys.exit(1)
    with open(json_path, 'r') as f:
        try:
            config = json.load(f)
            if "Structured Format" not in config or "End of Data" not in config:
                raise KeyError("Missing 'Structured Format' or 'End of Data' keys.")
            return config
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[Error] Failed to parse JSON config: {e}")
            sys.exit(1)

def apply_structure(raw_data, format_str):
    """
    Strips out all whitespaces, carriage returns, and non-alphanumeric noise,
    then segments the clean data into strict chunks separated by commas.
    """
    # Isolate only valid characters (removes hidden \r, spaces, etc.)
    clean_data = re.sub(r'[^a-zA-Z0-9]', '', raw_data)
    
    chunk_size = len(format_str)
    if chunk_size == 0 or not clean_data:
        return clean_data
        
    chunks = [clean_data[i:i+chunk_size] for i in range(0, len(clean_data), chunk_size)]
    return ",".join(chunks)

def process_and_save(stream_data, timestamps, marker, format_str, output_path):
    """Cleans stream boundaries, handles the 1:1 pop optimization, and writes to CSV."""
    print("\n[Info] Parsing raw data stream boundaries...")

    first_marker_idx = stream_data.find(marker)
    last_marker_idx = stream_data.rfind(marker)

    if first_marker_idx == -1 or first_marker_idx == last_marker_idx:
        print("[Warning] Insufficient data segments recorded. CSV was not generated.")
        return

    # Isolate data string starting right after the first marker up to the last marker
    clean_stream = stream_data[first_marker_idx + len(marker) : last_marker_idx]
    
    # Intentionally pop the first timestamp off to match the dropped leading fragment
    if timestamps:
        popped_ts = timestamps.pop(0)
        print(f"[Cleanup] Dropped initial incomplete block data and timestamp: {popped_ts}")

    # Split remaining stream into individual structural blocks
    raw_blocks = clean_stream.split(marker)
    
    # Filter empty items that might appear from double-markers
    data_blocks = [b for b in raw_blocks if b.strip()]

    print(f"[Info] Sync Check -> Clean Blocks: {len(data_blocks)} | Timestamps Tracked: {len(timestamps)}")

    try:
        with open(output_path, 'w', newline='') as csv_file:
            # Zip ensures alignment matching data blocks strictly against remaining timestamps
            for block, ts in zip(data_blocks, timestamps):
                formatted_row = apply_structure(block, format_str)
                if formatted_row:
                    csv_file.write(f"{ts},{formatted_row}\n")
        print(f"[Success] Stream finalized and flushed to {output_path}")
    except Exception as e:
        print(f"[Error] Failed to write to CSV file: {e}")

def main():
    global raw_stream, collected_timestamps
    args = parse_arguments()
    config = load_config(args.structuredIn)
    
    end_of_data_marker = config["End of Data"]
    structure_format = config["Structured Format"]

    print(f"[Info] Attempting to open serial port {args.serialPort} at {args.baudRate} baud...")
    try:
        ser = serial.Serial(args.serialPort, args.baudRate, timeout=0.01)
    except serial.SerialException as e:
        print(f"[Error] Could not open serial port: {e}")
        sys.exit(1)

    print(f"[Connected] Stream recording active. Press Ctrl+C to terminate.")

    def signal_handler(sig, frame):
        print("\n[Ctrl+C Detected] Halting hardware port interface...")
        ser.close()
        process_and_save(raw_stream, collected_timestamps, end_of_data_marker, structure_format, args.fileOut)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    while True:
        try:
            byte_data = ser.read(1)
            if byte_data:
                char = byte_data.decode('utf-8', errors='ignore')
                raw_stream += char

                # Check back across continuous string for the end marker 
                if raw_stream.endswith(end_of_data_marker):
                    timestamp = get_high_res_timestamp()
                    collected_timestamps.append(timestamp)
                    
        except serial.SerialException as e:
            print(f"\n[Error] Serial port error during read: {e}")
            break

if __name__ == "__main__":
    main()