#!/usr/bin/env python3
"""Patch packets.py to add heading and route fields to DEFAULT_INITIAL_STATE."""

# Read the file
with open('simulator/simulator/packets.py', 'r') as f:
    content = f.read()

# Add the three missing fields to DEFAULT_INITIAL_STATE
old = '''\t"gps_lat": 43.2389,
\t"gps_lon": 76.8897,
\t"route_segment": "ALA-NUR:000",'''

new = '''\t"gps_lat": 43.2389,
\t"gps_lon": 76.8897,
\t"heading": 0.0,
\t"route_code": "UNKNOWN",
\t"route_name": "Unknown Route",
\t"route_segment": "ALA-NUR:000",'''

content = content.replace(old, new)

# Write the patched file
with open('simulator/simulator/packets.py', 'w') as f:
    f.write(content)

print("✓ Patched simulator/simulator/packets.py")
