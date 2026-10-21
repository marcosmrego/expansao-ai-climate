-- Progresso das cargas longas: o monitor da aba Brasil lê estas colunas de collector_run.
ALTER TABLE climate.collector_run
    ADD COLUMN IF NOT EXISTS etapa          TEXT,          -- ex.: "deter-amz · 2021-05"
    ADD COLUMN IF NOT EXISTS etapas_feitas  INTEGER,
    ADD COLUMN IF NOT EXISTS etapas_total   INTEGER,
    ADD COLUMN IF NOT EXISTS atualizado_em  TIMESTAMPTZ;
