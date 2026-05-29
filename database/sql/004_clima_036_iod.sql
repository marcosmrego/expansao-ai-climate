-- CLIMA-036: Indian Ocean Dipole (IOD) — Dipole Mode Index mensal
-- Calculado a partir do ERSSTv5 via OPeNDAP (NOAA PSL THREDDS)
-- DMI = anomalia SST box ocidental - anomalia SST box oriental (base 1981-2010)

CREATE TABLE IF NOT EXISTS climate.noaa_iod (
    id             SERIAL PRIMARY KEY,
    data_referencia DATE NOT NULL,
    dmi            NUMERIC(7, 4) NOT NULL,
    classificacao  TEXT NOT NULL,  -- POSITIVO | NEUTRO | NEGATIVO
    fonte          TEXT,
    payload_bruto  JSONB,
    criado_em      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (data_referencia)
);

CREATE INDEX IF NOT EXISTS idx_noaa_iod_data
    ON climate.noaa_iod (data_referencia DESC);
