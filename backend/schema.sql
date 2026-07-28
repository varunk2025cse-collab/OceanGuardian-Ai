-- OceanGuardian AI MVP -- PostgreSQL schema
-- Auto-generated from SQLAlchemy models. Do not edit by hand;
-- edit the models in app/models/ and re-run generate_schema_sql.py instead.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE userrole AS ENUM ('fisherman', 'family');
CREATE TYPE hazardtype AS ENUM ('cyclone', 'high_waves', 'storm', 'strong_wind', 'lightning');
CREATE TYPE hazardseverity AS ENUM ('advisory', 'warning', 'danger');
CREATE TYPE sosstatus AS ENUM ('active', 'acknowledged', 'resolved', 'false_alarm');

CREATE TABLE govt_schemes (
	id SERIAL NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	category VARCHAR(60) NOT NULL, 
	region VARCHAR(120) NOT NULL, 
	description TEXT NOT NULL, 
	eligibility TEXT NOT NULL, 
	how_to_apply TEXT NOT NULL, 
	contact_info VARCHAR(255), 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_govt_schemes_id ON govt_schemes (id);

CREATE TABLE market_prices (
	id SERIAL NOT NULL, 
	species VARCHAR(80) NOT NULL, 
	market_name VARCHAR(120) NOT NULL, 
	harbor_region VARCHAR(120) NOT NULL, 
	price_per_kg FLOAT NOT NULL, 
	currency VARCHAR(8) NOT NULL, 
	price_date DATE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_market_prices_id ON market_prices (id);
CREATE INDEX ix_market_prices_price_date ON market_prices (price_date);
CREATE INDEX ix_market_prices_harbor_region ON market_prices (harbor_region);
CREATE INDEX ix_market_prices_species ON market_prices (species);

CREATE TABLE users (
	id SERIAL NOT NULL, 
	phone_number VARCHAR(20) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	full_name VARCHAR(120) NOT NULL, 
	role userrole NOT NULL, 
	boat_name VARCHAR(120), 
	boat_registration_number VARCHAR(60), 
	home_harbor VARCHAR(120), 
	preferred_language VARCHAR(10) NOT NULL, 
	emergency_contact_name VARCHAR(120), 
	emergency_contact_phone VARCHAR(20), 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_phone_number ON users (phone_number);
CREATE INDEX ix_users_id ON users (id);

CREATE TABLE weather_alerts (
	id SERIAL NOT NULL, 
	title VARCHAR(160) NOT NULL, 
	description TEXT NOT NULL, 
	hazard_type hazardtype NOT NULL, 
	severity hazardseverity NOT NULL, 
	center_latitude FLOAT NOT NULL, 
	center_longitude FLOAT NOT NULL, 
	radius_km FLOAT NOT NULL, 
	valid_from TIMESTAMP WITH TIME ZONE NOT NULL, 
	valid_until TIMESTAMP WITH TIME ZONE NOT NULL, 
	source VARCHAR(120), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id)
);

CREATE INDEX ix_weather_alerts_severity ON weather_alerts (severity);
CREATE INDEX ix_weather_alerts_id ON weather_alerts (id);

CREATE TABLE family_links (
	id SERIAL NOT NULL, 
	fisherman_id INTEGER NOT NULL, 
	family_user_id INTEGER NOT NULL, 
	relation VARCHAR(50), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_family_link_pair UNIQUE (fisherman_id, family_user_id), 
	FOREIGN KEY(fisherman_id) REFERENCES users (id), 
	FOREIGN KEY(family_user_id) REFERENCES users (id)
);

CREATE INDEX ix_family_links_id ON family_links (id);

CREATE TABLE location_pings (
	id SERIAL NOT NULL, 
	client_uuid VARCHAR(36) NOT NULL, 
	user_id INTEGER NOT NULL, 
	latitude FLOAT NOT NULL, 
	longitude FLOAT NOT NULL, 
	accuracy_meters FLOAT, 
	speed_mps FLOAT, 
	heading_degrees FLOAT, 
	recorded_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	synced_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_location_pings_id ON location_pings (id);
CREATE INDEX ix_location_pings_user_id ON location_pings (user_id);
CREATE UNIQUE INDEX ix_location_pings_client_uuid ON location_pings (client_uuid);

CREATE TABLE sos_alerts (
	id SERIAL NOT NULL, 
	client_uuid VARCHAR(36) NOT NULL, 
	user_id INTEGER NOT NULL, 
	latitude FLOAT NOT NULL, 
	longitude FLOAT NOT NULL, 
	accuracy_meters FLOAT, 
	battery_level_percent INTEGER, 
	message TEXT, 
	status sosstatus NOT NULL, 
	triggered_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	received_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	resolved_at TIMESTAMP WITH TIME ZONE, 
	resolved_note TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_sos_alerts_user_id ON sos_alerts (user_id);
CREATE UNIQUE INDEX ix_sos_alerts_client_uuid ON sos_alerts (client_uuid);
CREATE INDEX ix_sos_alerts_id ON sos_alerts (id);
CREATE INDEX ix_sos_alerts_status ON sos_alerts (status);

