# Expansao AI Climate

Plataforma de monitoramento climático ENSO. Coleta dados ONI e SST da NOAA, armazena em PostgreSQL e expõe via API REST + dashboard.

## Arquitetura

```
collector/   → scripts de coleta NOAA (rodados via scheduler)
api/         → FastAPI (entry point de produção: api/zhora_api.py)
app/         → rotas e serviços (alertas climáticos)
database/    → conexão PostgreSQL + schema SQL
dashboard/   → frontend HTML/CSS/JS (Chart.js)
tests/       → testes unitários e de integração
```

## Setup local

**Pré-requisitos:** Python 3.11+, PostgreSQL 12+

```bash
# 1. Instalar dependências
pip install -r requirements.txt
pip install -e . --no-deps

# 2. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas credenciais

# 3. Criar schema no banco
psql -U postgres -d climate -f database/sql/001_schema.sql

# 4. Rodar a API
uvicorn api.zhora_api:app --reload

# 5. Coletar dados NOAA
python collector/noaa_oni_collector.py
python collector/noaa_sst_collector.py
```

## Docker

```bash
docker build -t climate .
docker run -p 8000:8000 --env-file .env climate
```

## Endpoints

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/health` | Health check (verifica conectividade com DB) |
| GET | `/climate/status` | Status atual: ONI, classificação, Niño 3.4, fase |
| GET | `/climate/history` | Histórico ONI dos últimos 24 meses |
| GET | `/climate/analysis` | Análise textual El Niño / La Niña / Neutro |
| GET | `/climate/trend` | Tendência ONI (SUBINDO / CAINDO / ESTAVEL) |
| GET | `/climate/update` | Data da última atualização NOAA |
| GET | `/api/climate/alerts` | Alertas operacionais ativos |

Documentação interativa disponível em `/docs` quando a API estiver rodando.

## Testes

```bash
# Testes unitários (sem banco)
pytest tests/ -m "not integration"

# Testes de integração (requer banco configurado)
pytest tests/ -m integration
```

## Variáveis de ambiente

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `DB_HOST` | Host do PostgreSQL | `localhost` |
| `DB_PORT` | Porta | `5432` |
| `DB_DATABASE` | Nome do banco | `climate` |
| `DB_USER` | Usuário | `postgres` |
| `DB_PASSWORD` | Senha | `...` |
| `ALLOWED_ORIGINS` | Origens CORS permitidas (separadas por vírgula) | `https://climate.expansao-ai.com.br` |
