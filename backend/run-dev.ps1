# Run from the backend folder (where this script lives).
# Uses `app.main` — not `backend.app.main` (that form needs repo root as cwd).
Set-Location $PSScriptRoot
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
