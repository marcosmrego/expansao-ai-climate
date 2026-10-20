-- BRASIL Fase 3: desmatamento (INPE, TerraBrasilis: DETER e PRODES)

-- Alertas DETER, um por feição. Sem geometria: o painel usa só atributos e a produção não tem PostGIS.
-- area_km2 é a área da feição dentro do município (areamunkm), unidade da fonte.
CREATE TABLE IF NOT EXISTS climate.deforestation_alert (
    projeto         TEXT          NOT NULL,              -- deter-amz | deter-cerrado
    fonte_id        TEXT          NOT NULL,              -- id da feição no WFS (a fonte republica e reclassifica)
    data_alerta     DATE          NOT NULL,              -- view_date
    publicado_em    DATE,                                -- publish_month
    classe          TEXT          NOT NULL,
    grupo           TEXT          NOT NULL,              -- desmatamento | corte_seletivo | degradacao | queimada | mineracao | outras
    area_km2        NUMERIC(12, 4) NOT NULL,
    uf              CHAR(2),
    municipio       TEXT,
    sensor          TEXT,
    satelite        TEXT,
    experimental    BOOLEAN       NOT NULL DEFAULT FALSE,
    atualizado_em   TIMESTAMPTZ   DEFAULT NOW(),
    PRIMARY KEY (projeto, fonte_id)
);

CREATE INDEX IF NOT EXISTS idx_deforestation_alert_data
    ON climate.deforestation_alert (projeto, data_alerta DESC);
CREATE INDEX IF NOT EXISTS idx_deforestation_alert_uf
    ON climate.deforestation_alert (projeto, uf, data_alerta DESC);

-- Taxa anual do PRODES por recorte. ano_prodes vai de 1º de agosto a 31 de julho e é rotulado pelo ano em que termina.
CREATE TABLE IF NOT EXISTS climate.deforestation_rate (
    projeto         TEXT          NOT NULL,              -- prodes-amazonia | prodes-cerrado
    ano_prodes      SMALLINT      NOT NULL,
    recorte         TEXT          NOT NULL,              -- TOTAL ou sigla da UF
    area_km2        NUMERIC(14, 3) NOT NULL,
    atualizado_em   TIMESTAMPTZ   DEFAULT NOW(),
    PRIMARY KEY (projeto, ano_prodes, recorte)
);
