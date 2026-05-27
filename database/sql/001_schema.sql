CREATE SCHEMA IF NOT EXISTS climate;

CREATE TABLE IF NOT EXISTS climate.raw_payload (
    id          SERIAL PRIMARY KEY,
    origem      TEXT NOT NULL,
    url         TEXT NOT NULL,
    content_type TEXT,
    payload_text TEXT,
    hash_payload TEXT,
    criado_em   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS climate.noaa_oni (
    id              SERIAL PRIMARY KEY,
    data_referencia DATE NOT NULL,
    ano             INTEGER NOT NULL,
    mes             INTEGER NOT NULL,
    oni             NUMERIC(5,2) NOT NULL,
    classificacao   TEXT NOT NULL,
    fonte           TEXT,
    payload_bruto   JSONB,
    criado_em       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ano, mes)
);

CREATE TABLE IF NOT EXISTS climate.noaa_sst_indices (
    id              SERIAL PRIMARY KEY,
    data_referencia DATE NOT NULL,
    ano             INTEGER NOT NULL,
    mes             INTEGER NOT NULL,
    nino_12_temp    NUMERIC(6,2),
    nino_12_anom    NUMERIC(6,2),
    nino_3_temp     NUMERIC(6,2),
    nino_3_anom     NUMERIC(6,2),
    nino_4_temp     NUMERIC(6,2),
    nino_4_anom     NUMERIC(6,2),
    nino_34_temp    NUMERIC(6,2),
    nino_34_anom    NUMERIC(6,2),
    fonte           TEXT,
    payload_bruto   JSONB,
    criado_em       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ano, mes)
);

CREATE TABLE IF NOT EXISTS climate.climate_alerts (
    id          SERIAL PRIMARY KEY,
    alert_type  TEXT NOT NULL,
    severity    TEXT NOT NULL,
    title       TEXT NOT NULL,
    message     TEXT NOT NULL,
    source      TEXT,
    status      TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS climate.operational_context (
    id           SERIAL PRIMARY KEY,
    context_type TEXT NOT NULL DEFAULT 'CLIMATE_SUMMARY',
    content      TEXT NOT NULL,
    oni_snapshot NUMERIC(5,2),
    metadata     JSONB,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_operational_context_type_created
    ON climate.operational_context (context_type, created_at DESC);

-- Columns used by the API (SELECT *):
-- r[0] data_referencia, r[1] periodo, r[2] oni, r[3] classificacao,
-- r[4] data_sst, r[5] nino_34_temp, r[6] nino_34_anom, r[7] classificacao_enso, r[8] fase
CREATE OR REPLACE VIEW climate.vw_enso_status AS
SELECT
    o.data_referencia,
    to_char(o.data_referencia, 'YYYY-MM')  AS periodo,
    o.oni,
    o.classificacao,
    s.data_referencia                       AS data_sst,
    s.nino_34_temp,
    s.nino_34_anom,
    o.classificacao                         AS classificacao_enso,
    CASE
        WHEN o.classificacao = 'EL_NINO'  THEN 'El Niño'
        WHEN o.classificacao = 'LA_NINA'  THEN 'La Niña'
        ELSE 'Neutro'
    END                                     AS fase
FROM (
    SELECT data_referencia, oni, classificacao
    FROM climate.noaa_oni
    WHERE oni > -99
    ORDER BY data_referencia DESC
    LIMIT 1
) o
CROSS JOIN (
    SELECT data_referencia, nino_34_temp, nino_34_anom
    FROM climate.noaa_sst_indices
    ORDER BY data_referencia DESC
    LIMIT 1
) s;
