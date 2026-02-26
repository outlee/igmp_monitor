#!/usr/bin/env python3
"""Generate a CSV file with 300 channel configurations for import."""
import csv
import ipaddress
import sys

BASE_MCAST_IP = ipaddress.IPv4Address("239.1.1.1")
BASE_PORT = 1234
OUTPUT = "channels.csv"


def main():
    rows = []
    for i in range(300):
        rows.append({
            "id": f"ch{i + 1:03d}",
            "name": f"频道{i + 1:03d}",
            "multicast_ip": str(BASE_MCAST_IP + i),
            "multicast_port": BASE_PORT,
            "group_name": "default",
            "sort_order": i,
            "enabled": 1,
            "expected_bitrate_kbps": 5000,
        })

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Generated {len(rows)} channels in {OUTPUT}")


if __name__ == "__main__":
    main()
