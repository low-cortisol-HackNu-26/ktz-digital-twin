// DEPRECATED — single-locomotive store replaced by fleetStore.ts.
//
// This file is kept as a thin re-export shim for any components not yet
// migrated to fleetStore:
//
//   export const useTelemetryStore = () =>
//     useFleetStore(s => s.locomotives[s.activeLocomotiveId ?? ''])
//
// Do not add new state here. Migrate any direct useTelemetryStore() calls
// to useTelemetry() hook or useFleetStore() selectors.
