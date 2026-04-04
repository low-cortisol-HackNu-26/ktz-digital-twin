CREATE TABLE IF NOT EXISTS locomotives (
	id VARCHAR(64) PRIMARY KEY,
	display_name VARCHAR(128),
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS telemetry_events (
	id BIGSERIAL PRIMARY KEY,
	timestamp TIMESTAMPTZ NOT NULL,
	locomotive_id VARCHAR(64) NOT NULL,
	speed_kph DOUBLE PRECISION NOT NULL,
	target_speed_kph DOUBLE PRECISION,
	allowed_speed_kph DOUBLE PRECISION,
	acceleration DOUBLE PRECISION,
	traction_mode VARCHAR(16) NOT NULL,
	tractive_effort_kn DOUBLE PRECISION,
	brake_pipe_pressure_bar DOUBLE PRECISION,
	brake_cylinder_pressure_bar DOUBLE PRECISION,
	pantograph_up BOOLEAN NOT NULL,
	catenary_voltage_kv DOUBLE PRECISION,
	traction_current_a DOUBLE PRECISION,
	traction_power_kw DOUBLE PRECISION,
	regen_power_kw DOUBLE PRECISION,
	transformer_temp_c DOUBLE PRECISION,
	converter_temp_c DOUBLE PRECISION,
	traction_motor_temp_c DOUBLE PRECISION,
	axle_bearing_temp_c DOUBLE PRECISION,
	compressor_state VARCHAR(8),
	compressor_cycles_per_hour DOUBLE PRECISION,
	pneumatic_pressure_bar DOUBLE PRECISION,
	vibration_motor DOUBLE PRECISION,
	vibration_gearbox DOUBLE PRECISION,
	gps_lat DOUBLE PRECISION,
	gps_lon DOUBLE PRECISION,
	route_segment VARCHAR(128),
	gradient_permille DOUBLE PRECISION,
	train_mass_tons DOUBLE PRECISION,
	active_fault_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
	signal_quality DOUBLE PRECISION,
	data_quality DOUBLE PRECISION,
	ingestion_time TIMESTAMPTZ NOT NULL DEFAULT now(),
	source VARCHAR(64),
	schema_version VARCHAR(32) NOT NULL DEFAULT '1.0',
	CONSTRAINT fk_telemetry_locomotive FOREIGN KEY (locomotive_id) REFERENCES locomotives(id)
);

CREATE INDEX IF NOT EXISTS idx_telemetry_events_loco_ts
	ON telemetry_events (locomotive_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS current_snapshots (
	locomotive_id VARCHAR(64) PRIMARY KEY REFERENCES locomotives(id),
	payload JSONB NOT NULL,
	event_timestamp TIMESTAMPTZ NOT NULL,
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ingestion_stats (
	locomotive_id VARCHAR(64) PRIMARY KEY,
	total_events INTEGER NOT NULL DEFAULT 0,
	valid_events INTEGER NOT NULL DEFAULT 0,
	invalid_events INTEGER NOT NULL DEFAULT 0,
	last_error TEXT,
	last_ingest_time TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$
BEGIN
	IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
		PERFORM create_hypertable('telemetry_events', 'timestamp', if_not_exists => TRUE);
	END IF;
EXCEPTION
	WHEN undefined_function THEN
		NULL;
END
$$;
