#!/usr/bin/env python3
"""
Generate channel CSVs for multiple radios.

Base Station (D578UV):
- DRN: I2Base (DMR ID 100)

Handhelds (DM32UV):
- DJN: MrSI2 (DMR ID 2)
- EJD: LiLI21 (DMR ID 3)
- JGN: LiLI22 (DMR ID 4)
- MAN: LiLI23 (DMR ID 5)

The only difference between CSVs is the Radio ID used for transmitting.
"""

import csv
import os
import shutil

# Radio configurations
# Each handheld transmits with its own Radio ID
RADIOS = {
    'DRN': {'name': 'I2Base', 'dmr_id': 100, 'type': 'D578UV'},
    'DJN': {'name': 'MrSI2', 'dmr_id': 102, 'type': 'DM32UV'},
    'EJD': {'name': 'LiLI21', 'dmr_id': 1, 'type': 'DM32UV'},
    'JGN': {'name': 'LiLI22', 'dmr_id': 2, 'type': 'DM32UV'},
    'MAN': {'name': 'LiLI23', 'dmr_id': 3, 'type': 'DM32UV'},
}

def load_channels_csv(csv_path):
    """Load channels from CSV file."""
    channels = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            channels.append(row)
    return channels

def generate_channels_csv(channels, radio_name, output_path):
    """Generate channels CSV for a specific radio."""
    with open(output_path, 'w', newline='') as f:
        fieldnames = list(channels[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for ch in channels:
            row = ch.copy()
            # Update Radio ID to this radio's name for TX
            row['Radio ID'] = radio_name
            writer.writerow(row)

def generate_radioid_csv(radio_info, output_path):
    """Generate radioid CSV for a specific radio."""
    with open(output_path, 'w', newline='') as f:
        f.write("No.,Radio ID,Name\n")
        f.write(f"1,{radio_info['dmr_id']},{radio_info['name']}\n")

def main():
    base_dir = '/home/user/AT-D578UV'
    channels_csv = os.path.join(base_dir, 'codeplug', 'channels.csv')

    # Load channels
    channels = load_channels_csv(channels_csv)
    print(f"Loaded {len(channels)} channels from {channels_csv}")

    # Generate CSVs for each radio
    for radio_code, radio_info in RADIOS.items():
        print(f"\n=== {radio_code}: {radio_info['name']} (DMR ID {radio_info['dmr_id']}) - {radio_info['type']} ===")

        # Channels CSV with this radio's ID
        csv_path = os.path.join(base_dir, f'{radio_code}_channels.csv')
        generate_channels_csv(channels, radio_info['name'], csv_path)
        print(f"  Created {csv_path}")

        # Radio ID CSV
        radioid_path = os.path.join(base_dir, f'{radio_code}_radioid.csv')
        generate_radioid_csv(radio_info, radioid_path)
        print(f"  Created {radioid_path}")

    # Copy zones and scanlist for reference
    print("\n=== Reference files ===")
    for src_name in ['zones.csv', 'scanlist.csv']:
        src = os.path.join(base_dir, 'codeplug', src_name)
        if os.path.exists(src):
            print(f"  Zone/Scanlist: {src}")

    print("\n=== Summary ===")
    print("Radio IDs configured:")
    for code, info in RADIOS.items():
        print(f"  {code}: {info['name']} = DMR ID {info['dmr_id']}")

    print("\nFor CPS import order:")
    print("1. Import channels CSV for the specific radio")
    print("2. Import zones.csv (same for all)")
    print("3. Import scanlist.csv (same for all)")
    print("4. Set Radio ID manually in CPS")

if __name__ == '__main__':
    main()
