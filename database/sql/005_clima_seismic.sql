-- CLIMA: Monitoramento sísmico/vulcânico via USGS
-- Foco em eventos com potencial impacto climático (VEI ≥ 4 / mag ≥ 5.0)

CREATE TABLE IF NOT EXISTS climate.seismic_events (
    id              SERIAL PRIMARY KEY,
    event_id        TEXT UNIQUE NOT NULL,       -- ID USGS (ex: us7000dxk1)
    data_referencia DATE NOT NULL,
    timestamp_utc   TIMESTAMPTZ NOT NULL,
    latitude        NUMERIC(8, 4) NOT NULL,
    longitude       NUMERIC(8, 4) NOT NULL,
    depth_km        NUMERIC(8, 2),
    magnitude       NUMERIC(5, 2) NOT NULL,
    magnitude_type  TEXT,                       -- ml, mb, mw, mww...
    event_type      TEXT NOT NULL,              -- earthquake | volcanic explosion | explosion
    place           TEXT,                       -- ex: "50km NW of Talkeetna, Alaska"
    title           TEXT,                       -- título legível USGS
    climate_relevant BOOLEAN DEFAULT FALSE,     -- TRUE se VEI estimado >= 4 ou mag >= 6 vulcânico
    alert_level     TEXT,                       -- green | yellow | orange | red (USGS)
    fonte           TEXT DEFAULT 'USGS_FDSN',
    criado_em       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_seismic_data
    ON climate.seismic_events (data_referencia DESC);
CREATE INDEX IF NOT EXISTS idx_seismic_type
    ON climate.seismic_events (event_type, magnitude DESC);
CREATE INDEX IF NOT EXISTS idx_seismic_relevant
    ON climate.seismic_events (climate_relevant) WHERE climate_relevant = TRUE;
