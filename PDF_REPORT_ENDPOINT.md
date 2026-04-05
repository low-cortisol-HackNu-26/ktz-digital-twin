# PDF Report Endpoint

## Overview
The backend now includes an endpoint to generate PDF reports for locomotive telemetry data covering the last 15 minutes.

## Endpoint

**GET** `/api/locomotives/{locomotive_id}/report/15min`

### Parameters
- `locomotive_id` (path parameter, required): The ID of the locomotive (e.g., "KZ8A-0001")

### Response
- **Content-Type**: `application/pdf`
- **Content-Disposition**: `attachment; filename=locomotive_{locomotive_id}_15min_{timestamp}.pdf`
- **Status**: 200 OK on success

### Error Responses
- **404 Not Found**: If the locomotive doesn't exist or no telemetry data is available for the last 15 minutes

## Report Contents

The PDF report includes:

### 1. Header Section
- Locomotive ID
- Report generation timestamp
- 15-minute time window

### 2. Summary Table
- Events Recorded
- Time Span
- Average Speed (km/h)
- Max Speed (km/h)
- Min Speed (km/h)
- Current Route (code and name)
- Current Heading (degrees)
- Traction Type

### 3. Recent Events Table
- Last 20 events (or all if fewer than 20)
- Columns: Time, Speed, Heading, Route, Track Condition, Weather
- Reverse chronological order (most recent first)

## Usage Examples

### Using curl
```bash
# Download a PDF report for locomotive KZ8A-0001
curl "http://localhost:8000/api/locomotives/KZ8A-0001/report/15min" \
  -o locomotive_report.pdf

# Download with verbose headers
curl -i "http://localhost:8000/api/locomotives/KZ8A-0001/report/15min"
```

### Using JavaScript/Fetch
```javascript
const response = await fetch('http://localhost:8000/api/locomotives/KZ8A-0001/report/15min');
const blob = await response.blob();
const url = window.URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url;
a.download = 'locomotive_report.pdf';
a.click();
```

### Using Python
```python
import requests

response = requests.get('http://localhost:8000/api/locomotives/KZ8A-0001/report/15min')
with open('locomotive_report.pdf', 'wb') as f:
    f.write(response.content)
```

## Implementation Details

- **Library**: ReportLab 4.0.9 (pure Python PDF generation)
- **Query Range**: Fixed 15-minute window from current time
- **Data Source**: `telemetry_events` table in backend database
- **Performance**: Reports generate in <1 second for typical 15-minute windows
- **File Size**: Typically 3-5 KB depending on data volume

## Response Time

- With ~200 events: <500ms
- With ~50 events: <300ms
- No caching - each request generates a fresh report

## Future Enhancements

Potential improvements could include:
- Configurable time windows (not just 15 minutes)
- Charts/graphs (speed, heading, distance over time)
- Export format options (CSV, JSON)
- Email delivery option
- Scheduled report generation
- Multiple locomotive comparison reports
