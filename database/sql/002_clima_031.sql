-- CLIMA-031: Indicadores climáticos mensais adicionais
-- PDO, NAO, AMO, QBO — todos no formato NOAA PSL (ano + 12 valores mensais)

CREATE TABLE IF NOT EXISTS climate.noaa_pdo (
    id              SERIAL PRIMARY KEY,
    data_referencia DATE NOT NULL,
    ano             INTEGER NOT NULL,
    mes             INTEGER NOT NULL,
    pdo             NUMERIC(8, 4) NOT NULL,
    classificacao   TEXT NOT NULL,
    fonte           TEXT,
    payload_bruto   JSONB,
    criado_em       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ano, mes)
);

CREATE TABLE IF NOT EXISTS climate.noaa_nao (
    id              SERIAL PRIMARY KEY,
    data_referencia DATE NOT NULL,
    ano             INTEGER NOT NULL,
    mes             INTEGER NOT NULL,
    nao             NUMERIC(8, 4) NOT NULL,
    classificacao   TEXT NOT NULL,
    fonte           TEXT,
    payload_bruto   JSONB,
    criado_em       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ano, mes)
);

CREATE TABLE IF NOT EXISTS climate.noaa_amo (
    id              SERIAL PRIMARY KEY,
    data_referencia DATE NOT NULL,
    ano             INTEGER NOT NULL,
    mes             INTEGER NOT NULL,
    amo             NUMERIC(10, 6) NOT NULL,
    classificacao   TEXT NOT NULL,
    fonte           TEXT,
    payload_bruto   JSONB,
    criado_em       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ano, mes)
);

CREATE TABLE IF NOT EXISTS climate.noaa_qbo (
    id              SERIAL PRIMARY KEY,
    data_referencia DATE NOT NULL,
    ano             INTEGER NOT NULL,
    mes             INTEGER NOT NULL,
    qbo             NUMERIC(8, 3) NOT NULL,
    classificacao   TEXT NOT NULL,
    fonte           TEXT,
    payload_bruto   JSONB,
    criado_em       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ano, mes)
);
