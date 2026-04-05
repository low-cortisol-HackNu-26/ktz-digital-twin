#!/usr/bin/env python3
"""Patch state_machine.py to add heading and route info to telemetry packets."""

import re

# Read the file
with open('simulator/simulator/state_machine.py', 'r') as f:
    content = f.read()

# Patch 1: Add route_code/name and heading storage in __init__
# Find the line with self._current_scale and add after it
old_init = """		self._current_scale = 1.0 + (((seed % 9) - 4) * 0.02)

		# Prime GPS"""

new_init = """		self._current_scale = 1.0 + (((seed % 9) - 4) * 0.02)

		# Store route info
		self._route_code = route.get("code", "UNKNOWN")
		self._route_name = route.get("name", "Unknown Route")
		self._last_heading: float | None = None

		# Prime GPS"""

content = content.replace(old_init, new_init)

# Patch 2: Add heading computation before build_packet
old_packet = """		self._synchronize_metric_aliases()

		return build_packet(self.locomotive_id, self.state)"""

new_packet = """		self._synchronize_metric_aliases()

		# Add route and heading info
		self._compute_heading()
		self.state["heading"] = self._last_heading
		self.state["route_code"] = self._route_code
		self.state["route_name"] = self._route_name

		return build_packet(self.locomotive_id, self.state)"""

content = content.replace(old_packet, new_packet)

# Patch 3: Add _compute_heading method before _apply_route_context
compute_heading_method = """	def _compute_heading(self) -> None:
		\"\"\"Compute heading (bearing) from current position to next coordinate.\"\"\"
		coords = self._follower.coords
		if len(coords) < 2:
			self._last_heading = 0.0
			return
		
		seg = self._follower._segment_index()
		if seg < 0 or seg >= len(coords) - 1:
			self._last_heading = 0.0
			return

		from_coord = coords[seg]
		to_coord = coords[seg + 1]
		
		dlon = math.radians(to_coord[0] - from_coord[0])
		lat1 = math.radians(from_coord[1])
		lat2 = math.radians(to_coord[1])
		
		x = math.sin(dlon) * math.cos(lat2)
		y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
		
		heading = (math.degrees(math.atan2(x, y)) + 360) % 360
		self._last_heading = heading

"""

# Find where to insert the method - right before _apply_route_context
insert_before = "\tdef _apply_route_context(self) -> None:"
content = content.replace(insert_before, compute_heading_method + insert_before)

# Write the patched file
with open('simulator/simulator/state_machine.py', 'w') as f:
    f.write(content)

print("✓ Patched simulator/simulator/state_machine.py")
