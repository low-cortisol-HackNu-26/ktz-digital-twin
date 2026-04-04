// Login page — card tap authentication.
//
// Two modes depending on browser support:
//
// Mode A — WebHID supported (Chrome/Edge on desktop):
//   - Full-screen prompt: large card icon + "Tap your operator card"
//   - useCardReader() hook listens for HID input report
//   - On card read: calls cardAuth.authenticateCard(uid) → stores token → redirect /dashboard
//   - "Connect reader" button triggers navigator.hid.requestDevice() on first use
//
// Mode B — WebHID not supported (fallback):
//   - Manual card UID input field (for dev/testing)
//   - Submit → same authenticateCard() flow
//
// Error states:
//   - "Card not registered" (401 from backend)
//   - "Card deactivated" (403 from backend)
//   - "Reader disconnected" (HID device lost)
//
// No username/password form. No OAuth redirect.
