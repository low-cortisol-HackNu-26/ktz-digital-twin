from simulator.state_machine import StateMachine
sm = StateMachine("KZ8A-0001", "normal", 5)
packet = sm.next_packet()
print("heading:", packet.get("heading"))
print("route_code:", packet.get("route_code"))
print("route_name:", packet.get("route_name"))
print("route_segment:", packet.get("route_segment"))
