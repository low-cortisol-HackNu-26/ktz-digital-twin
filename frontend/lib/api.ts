// Axios instance and typed API helpers for REST calls to the backend.
//
// axios instance:
//   baseURL: process.env.NEXT_PUBLIC_API_URL
//   request interceptor: attach Bearer token from cardAuth.getToken()
//   response interceptor: on 401 → call cardAuth.logout() (token expired/revoked)
//
// API functions to export (all return typed promises):
//   fetchHistory(locomotiveId, from, to): Promise<TelemetryPacket[]>
//   fetchLocomotives(): Promise<{ id: string; name: string }[]>
//   fetchThresholds(): Promise<ThresholdsConfig>
//   updateThresholds(config: ThresholdsConfig): Promise<void>
//   triggerExport(params: ExportParams): Promise<{ jobId: string }>
//   pollExportJob(jobId: string): Promise<{ status: string; url?: string }>
//   fetchRouteGeoJSON(locomotiveId: string): Promise<GeoJSON.FeatureCollection>
