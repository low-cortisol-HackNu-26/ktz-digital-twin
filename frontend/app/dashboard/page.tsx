// Main dashboard "Cabin" page — the primary screen.
//
// Layout: cabin-grid CSS Grid (see globals.css)
//
// Panels to render (all are client components reading from Zustand store):
//   Top row:
//     <HealthIndexWidget />   — large, left
//     <SpeedPanel />          — center
//     <AlertsPanel />         — right
//   Middle row:
//     <FuelEnergyPanel />
//     <PressureTempPanel />
//     <ElectricsPanel />
//   Bottom row:
//     <TrendsPanel />         — spans 2 cols, live scrolling multi-line chart
//     <RouteMap />            — right, shows current position on track segment
//
// Default locomotiveId comes from URL searchParam ?id= or first available from API.
