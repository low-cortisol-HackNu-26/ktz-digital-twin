// 'use client'
// WebHID API hook — optional direct RFID/NFC card reader access in supported browsers.
//
// Flow:
//   1. requestDevice(): prompts browser HID device picker (Chrome/Edge only)
//      Filter: vendorId for common RFID readers (e.g. 0x076b HID Global, 0x08e6 Gemalto)
//   2. Open device, listen for inputreport events
//   3. Parse report data to extract card UID (format depends on reader; typically 4 or 7 bytes hex)
//   4. Call onCardRead(uid: string) callback
//
// Returns:
//   requestReader(): Promise<void>    — triggers browser device picker
//   isSupported: boolean              — navigator.hid !== undefined
//   isConnected: boolean
//   lastCardUID: string | null
//   error: string | null
//
// Fallback: if WebHID not supported, UI shows manual card ID input field instead.
// The hook does NOT call the backend — that is done by cardAuth.ts using the UID.
//
// Note: WebHID requires a user gesture to call requestDevice (button click).
//       Device access is persisted across page reloads via browser permission.
