-- CLIMA-032: Indicadores diários (MJO, CO₂, Gelo Ártico, Gelo Antártico)

CREATE TABLE IF NOT EXISTS climate.mjo_daily (
    id              SERIAL PRIMARY KEY,
    data_referencia DATE             NOT NULL,
    rmm1            NUMERIC(8, 4),
    rmm2            NUMERIC(8, 4),
    phase           INTEGER,
    amplitude       NUMERIC(8, 4)    NOT NULL,
    classificacao   TEXT             NOT NULL,
    fonte           TEXT,
    payload_bruto   JSONB,
    criado_em       TIMESTAMPTZ      DEFAULT NOW(),
    UNIQUE (data_referencia)
);

CREATE TABLE IF NOT EXISTS climate.noaa_co2_daily (
    id              SERIAL PRIMARY KEY,
    data_referencia DATE             NOT NULL,
    co2_ppm         NUMERIC(8, 2)    NOT NULL,
    fonte           TEXT,
    payload_bruto   JSONB,
    criado_em       TIMESTAMPTZ      DEFAULT NOW(),
    UNIQUE (data_referencia)
);

CREATE TABLE IF NOT EXISTS climate.nsidc_arctic_ice_daily (
    id              SERIAL PRIMARY KEY,
    data_referencia DATE             NOT NULL,
    extent_mkm2     NUMERIC(8, 3)    NOT NULL,
    area_mkm2       NUMERIC(8, 3),
    fonte           TEXT,
    payload_bruto   JSONB,
    criado_em       TIMESTAMPTZ      DEFAULT NOW(),
    UNIQUE (data_referencia)
);

CREATE TABLE IF NOT EXISTS climate.nsidc_antarctic_ice_daily (
    id              SERIAL PRIMARY KEY,
    data_referencia DATE             NOT NULL,
    extent_mkm2     NUMERIC(8, 3)    NOT NULL,
    area_mkm2       NUMERIC(8, 3),
    fonte           TEXT,
    payload_bruto   JSONB,
    criado_em       TIMESTAMPTZ      DEFAULT NOW(),
    UNIQUE (data_referencia)
);
