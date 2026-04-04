// Train proximity calculations using @turf/turf.
// Used by RouteMap and the fleet manager to detect dangerous closeness between trains.
//
// PROXIMITY_WARNING_KM = 2.0   (amber warning threshold)
// PROXIMITY_CRITICAL_KM = 0.5  (red critical threshold)
//
// calculateProximities(positions: TrainPosition[]): ProximityResult[]
//   For each pair of trains, compute turf.distance([lng,lat], [lng,lat], { units: 'kilometers' })
//   Return only pairs below PROXIMITY_WARNING_KM
//   Each result: { trainA: string; trainB: string; distanceKm: number; severity: 'warning'|'critical' }
//
// snapToRoute(point: [lng, lat], routeLine: GeoJSON.LineString): SnappedPoint
//   Uses turf.nearestPointOnLine to snap a GPS position to the route polyline
//   Returns: { snapped: [lng,lat]; distanceFromStart: number (km); bearing: number (degrees) }
//
// isApproaching(a: SnappedPoint, b: SnappedPoint, speedA: number, speedB: number): boolean
//   Returns true if distanceFromStart is converging (trains moving toward each other)
//   Uses bearing comparison and sign of (b.distanceFromStart - a.distanceFromStart)
//
// buildRouteGeoJSON(waypoints: [lng, lat][]): GeoJSON.Feature<GeoJSON.LineString>
//   Uses turf.lineString to build a GeoJSON Feature for the route
//   Used by RouteMap to initialize the route polyline
