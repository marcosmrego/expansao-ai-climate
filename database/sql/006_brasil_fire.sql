-- BRASIL Fase 1: focos de calor (INPE Programa Queimadas)

-- Registro de execução de todo coletor da área Brasil
CREATE TABLE IF NOT EXISTS climate.collector_run (
    id             SERIAL PRIMARY KEY,
    fonte          TEXT        NOT NULL,
    inicio         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fim            TIMESTAMPTZ,
    janela_inicio  DATE,
    janela_fim     DATE,
    registros      INTEGER,
    status         TEXT        NOT NULL DEFAULT 'running',  -- running | ok | erro
    erro           TEXT
);

CREATE INDEX IF NOT EXISTS idx_collector_run_fonte
    ON climate.collector_run (fonte, inicio DESC);

-- Detecções individuais. Satélites não-referência ficam poucos dias (retenção no coletor).
CREATE TABLE IF NOT EXISTS climate.fire_hotspot (
    id              BIGSERIAL PRIMARY KEY,
    fonte           TEXT         NOT NULL DEFAULT 'inpe',
    fonte_id        TEXT         NOT NULL,
    satelite        TEXT,
    detectado_em    TIMESTAMPTZ  NOT NULL,                  -- UTC
    latitude        NUMERIC(9, 6) NOT NULL,
    longitude       NUMERIC(9, 6) NOT NULL,
    frp             NUMERIC(8, 1),                          -- potência radiativa (MW)
    risco_fogo      NUMERIC(4, 2),
    dias_sem_chuva  INTEGER,
    precipitacao    NUMERIC(6, 1),
    uf              CHAR(2),
    municipio       TEXT,
    municipio_id    INTEGER,
    bioma           TEXT,
    is_ref          BOOLEAN      NOT NULL DEFAULT FALSE,    -- satélite de referência (AQUA_M-T)
    criado_em       TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE (fonte, fonte_id)
);

CREATE INDEX IF NOT EXISTS idx_fire_hotspot_data
    ON climate.fire_hotspot (detectado_em DESC);
CREATE INDEX IF NOT EXISTS idx_fire_hotspot_ref_data
    ON climate.fire_hotspot (detectado_em DESC) WHERE is_ref;
CREATE INDEX IF NOT EXISTS idx_fire_hotspot_mun
    ON climate.fire_hotspot (municipio_id, detectado_em DESC);

-- Agregado diário SOMENTE do satélite de referência (série comparável desde 2003)
CREATE TABLE IF NOT EXISTS climate.fire_daily_agg (
    data       DATE         NOT NULL,
    nivel      TEXT         NOT NULL CHECK (nivel IN ('brasil', 'uf', 'bioma')),
    codigo     TEXT         NOT NULL,                       -- 'BR', sigla da UF ou slug do bioma
    focos      INTEGER      NOT NULL,
    frp_soma   NUMERIC(14, 1),
    PRIMARY KEY (data, nivel, codigo)
);

CREATE INDEX IF NOT EXISTS idx_fire_daily_agg_codigo
    ON climate.fire_daily_agg (nivel, codigo, data);
