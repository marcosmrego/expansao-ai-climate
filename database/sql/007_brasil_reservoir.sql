-- BRASIL Fase 2: reservatórios (ANA, Sistema de Acompanhamento de Reservatórios)

CREATE TABLE IF NOT EXISTS climate.reservoir (
    id              INTEGER PRIMARY KEY,                 -- SAR_ID da ANA
    nome            TEXT          NOT NULL,
    sistema         TEXT          NOT NULL CHECK (sistema IN ('SIN', 'NORDESTE', 'CANTAREIRA', 'DF', 'RMBH')),
    uf              CHAR(2),
    municipio       TEXT,
    bacia           TEXT,
    capacidade_hm3  NUMERIC(12, 3),
    latitude        NUMERIC(9, 5),
    longitude       NUMERIC(9, 5),
    atualizado_em   TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reservoir_sistema ON climate.reservoir (sistema, uf);

-- Uma leitura por reservatório e dia de medição.
-- volume_pct: volume útil (%) no SIN; volume (%) da capacidade nos demais sistemas.
CREATE TABLE IF NOT EXISTS climate.reservoir_reading (
    reservoir_id    INTEGER       NOT NULL REFERENCES climate.reservoir (id) ON DELETE CASCADE,
    data            DATE          NOT NULL,
    volume_pct      NUMERIC(7, 2),
    volume_hm3      NUMERIC(12, 3),
    cota_m          NUMERIC(9, 2),
    afluencia_m3s   NUMERIC(10, 2),
    defluencia_m3s  NUMERIC(10, 2),
    fonte           TEXT          NOT NULL,              -- sar_api | sar_pagina
    criado_em       TIMESTAMPTZ   DEFAULT NOW(),
    PRIMARY KEY (reservoir_id, data)
);

CREATE INDEX IF NOT EXISTS idx_reservoir_reading_data
    ON climate.reservoir_reading (data DESC);
