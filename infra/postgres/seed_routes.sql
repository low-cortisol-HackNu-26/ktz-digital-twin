-- Kazakhstan Temir Zholy (KTZ) railway route seed data.
-- Coordinates are [lng, lat] GeoJSON order, simplified from actual track geometry.
-- Run this AFTER the backend has created tables via create_all.
-- Idempotent: uses INSERT ... ON CONFLICT DO NOTHING.

INSERT INTO routes (id, code, name, coordinates, total_length_km, created_at)
VALUES

-- ── Almaty ↔ Nur-Sultan (Astana) — main trunk line, ~1 300 km ──────────────
(
  gen_random_uuid(),
  'ALA-NUR',
  'Almaty — Nur-Sultan',
  '[
    [76.9286, 43.2567],
    [77.0500, 43.8500],
    [77.1200, 44.4000],
    [77.0000, 44.8500],
    [76.1500, 45.5000],
    [75.3000, 46.2000],
    [74.9950, 46.8474],
    [74.0000, 47.8000],
    [73.6000, 48.6000],
    [73.0884, 49.8073],
    [72.5000, 50.4000],
    [71.9500, 50.8500],
    [71.4460, 51.1801]
  ]'::json,
  1295.0,
  now()
),

-- ── Almaty ↔ Shymkent — southern corridor, ~700 km ──────────────────────────
(
  gen_random_uuid(),
  'ALA-SHY',
  'Almaty — Shymkent',
  '[
    [76.9286, 43.2567],
    [76.0000, 43.0000],
    [74.5000, 42.8500],
    [73.0000, 42.7000],
    [71.9000, 42.6000],
    [71.3713, 42.3167],
    [70.8000, 42.2000],
    [69.5900, 42.3170]
  ]'::json,
  705.0,
  now()
),

-- ── Nur-Sultan ↔ Aktobe — western steppe line, ~1 100 km ────────────────────
(
  gen_random_uuid(),
  'NUR-AKT',
  'Nur-Sultan — Aktobe',
  '[
    [71.4460, 51.1801],
    [70.0000, 51.5000],
    [68.0000, 52.0000],
    [66.0000, 52.5000],
    [64.5000, 52.8000],
    [63.6240, 53.2143],
    [62.0000, 52.5000],
    [60.0000, 51.5000],
    [57.1530, 50.3001]
  ]'::json,
  1090.0,
  now()
),

-- ── Nur-Sultan ↔ Petropavl — northern line to Russia border, ~280 km ────────
(
  gen_random_uuid(),
  'NUR-PET',
  'Nur-Sultan — Petropavl',
  '[
    [71.4460, 51.1801],
    [71.5000, 51.8000],
    [71.6000, 52.4000],
    [71.7000, 52.9000],
    [71.9522, 54.8650]
  ]'::json,
  280.0,
  now()
),

-- ── Shymkent ↔ Kyzylorda — west along the Syr Darya river, ~600 km ──────────
(
  gen_random_uuid(),
  'SHY-KYZ',
  'Shymkent — Kyzylorda',
  '[
    [69.5900, 42.3170],
    [68.5000, 43.0000],
    [67.5000, 43.8000],
    [66.8000, 44.3000],
    [65.5500, 44.8530]
  ]'::json,
  605.0,
  now()
)

ON CONFLICT (code) DO NOTHING;
