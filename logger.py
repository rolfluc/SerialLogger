import argparse
import datetime
import json
import os
import serial
import signal
import sys


jsonFormatName = "StructuredFormat"
jsonEoDName = "EndofData"
# Global list to store collected data blocks
collected_data = []
collected_timestamps = []
current_block = ""

def parseArgs():
    """Handles CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Cross-platform Serial Port Reader and JSON-based Structurer."
    )
    parser.add_argument("-si", "--structuredIn", required=True, 
                        help="Path to the configuration .json file")
    parser.add_argument("-fo", "--fileOut", required=True, 
                        help="Path to the output .csv file")
    parser.add_argument("-sp", "--serialPort", required=True, 
                        help="Serial port name (e.g., COM3 or /dev/ttyUSB0)")
    parser.add_argument("-br", "--baudRate", type=int, default=115200, 
                        help="Baud rate for the serial port (default: 115200)")
    return parser.parse_args()

def loadJson(json_path):
    global jsonFormatName, jsonEoDName
    """Loads and validates the JSON configuration."""
    if not os.path.exists(json_path):
        print(f"[Error] Configuration file not found at: {json_path}")
        sys.exit(1)
        
    with open(json_path, 'r') as f:
        try:
            config = json.load(f)
            # Ensure required keys exist
            if jsonFormatName not in config or jsonEoDName not in config:
                raise KeyError("Missing Structured Format or End of Data keys from JSON file.")
            EoDMarker = config[jsonEoDName]
            structureFormat = config[jsonFormatName]
            return [structureFormat,EoDMarker]
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[Error] Failed to parse JSON config: {e}")
            sys.exit(1)

def apply_structure(raw_data, format_str):
    """
    Formats the raw string by inserting commas based on the format structure.
    Example: 'ABCDEF12' with format 'XXXX' becomes 'ABCD,EF12'
    """
    # Clean the data of any accidental residual newlines/whitespace
    clean_data = raw_data.strip()
    chunk_size = len(format_str)
    
    if chunk_size == 0:
        return clean_data

    # Split the string into chunks of 'chunk_size'
    chunks = [clean_data[i:i+chunk_size] for i in range(0, len(clean_data), chunk_size)]
    return ",".join(chunks)

def save_to_csv(data_list, format_str, output_path):
    """Processes all accumulated data blocks and writes them to a CSV."""
    print(f"\n[Info] Referencing captured data against structure format '{format_str}'...")
    
    formatted_rows = []
    for block in data_list:
        if block.strip(): # Skip empty blocks
            formatted_row = apply_structure(block, format_str)
            formatted_rows.append(formatted_row)

    try:
        with open(output_path, 'w', newline='') as csv_file:
            for row in formatted_rows:
                csv_file.write(row + "\n")
        print(f"[Success] Data successfully flushed to {output_path}")
    except Exception as e:
        print(f"[Error] Failed to write to CSV file: {e}")

def main():
    global current_block, collected_data
    args = parseArgs()
    config = loadJson(args.structuredIn)
    
    structure_format = config[0]
    end_of_data_marker = config[1]

    # Attempt to open the serial port
    print(f"[Info] Attempting to open serial port {args.serialPort} at {args.baudRate} baud...")
    try:
        # timeout=1 ensures the read loop doesn't block indefinitely, allowing signal handling
        ser = serial.Serial(args.serialPort, args.baudRate, timeout=1)
    except Exception as e:
        print(f"[Error] Could not open serial port: {e}")
        sys.exit(1)

    print(f"[Connected] Listening in real-time. Press Ctrl+C to stop and save data.")

    # Signal handler for graceful Ctrl+C shutdown
    def signal_handler(sig, frame):
        print("\n[Ctrl+C Detected] Closing serial port and finalizing data...")
        ser.close()
        save_to_csv(collected_data, structure_format, args.fileOut)
        sys.exit(0)

    # Register the Ctrl+C listener
    signal.signal(signal.SIGINT, signal_handler)

    # Real-time listening loop
    while True:
        try:
            # Read data byte by byte
            byte_data = ser.read(1)
            if byte_data:
                # Decode character (ignoring errors if non-text noise appears on lines)
                char = byte_data.decode('utf-8', errors='ignore')
                current_block += char

                # Check if the end of data sequence has been met
                if current_block.endswith(end_of_data_marker):
                    # Strip the marker off the data block before appending
                    data_to_append = current_block[:-len(end_of_data_marker)]
                    print(f"[Data Block Captured] : {data_to_append.strip()}")
                    collected_data.append(data_to_append)
                    collected_timestamps.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'))
                    current_block = "" # Reset for next block
                    
        except serial.SerialException as e:
            print(f"\n[Error] Serial port error during read: {e}")
            break

if __name__ == "__main__":
    main()