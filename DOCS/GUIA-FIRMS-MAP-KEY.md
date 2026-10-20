# Guia: obter e configurar a MAP_KEY do NASA FIRMS

A MAP_KEY é gratuita e libera a API de focos de calor do FIRMS. Ela é complementar:
a coleta principal da Fase 1 usa o INPE, que não exige chave (ver `FASE-0-RELATORIO.md`).
Obtenha a chave quando puder, pois ela serve para conferir os totais do INPE
e para cobrir lacunas.

## 1. Pedir a chave

1. Abra https://firms.modaps.eosdis.nasa.gov/api/area/
2. Clique em **Get MAP_KEY**.
3. Informe seu e-mail e escolha o tipo de uso (pode ser "Other / Research").
4. A chave chega por e-mail em poucos minutos. É uma string de 32 caracteres.
   Se o e-mail já estiver registrado, o site oferece reenviar a chave.

## 2. Testar a chave (no seu terminal)

Troque `SUA_CHAVE` pela chave recebida:

```bash
# Quantas "transações" restam na janela de 10 minutos
curl "https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY=SUA_CHAVE"

# Focos das últimas 24 h no Brasil (bbox: oeste,sul,leste,norte), sensor VIIRS S-NPP
curl "https://firms.modaps.eosdis.nasa.gov/api/area/csv/SUA_CHAVE/VIIRS_SNPP_NRT/-74,-34,-34,6/1" | head -5

# Quais datas existem por produto
curl "https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv/SUA_CHAVE/ALL"
```

Resultado esperado: um CSV com colunas como `latitude,longitude,bright_ti4,acq_date,acq_time,satellite,confidence,frp`.
A resposta `Invalid MAP_KEY.` indica chave errada.

Regras da API (conferidas na documentação oficial em 2026-10-19):
- Limite: 5.000 transações a cada 10 minutos. Consultas com vários dias contam como várias.
- `DAY_RANGE` aceita de 1 a 5 dias por chamada.
- Fontes úteis: `VIIRS_SNPP_NRT`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA21_NRT`, `MODIS_NRT`
  e as versões `_SP` (processamento padrão, usadas para histórico e reconciliação).

## 3. Configurar o projeto

**Nunca** coloque a chave no repositório, em log ou no front-end.

Local: no arquivo `.env` (que já está no `.gitignore`), acrescente

```
FIRMS_MAP_KEY=cole_a_chave_aqui
```

Produção: adicione a variável `FIRMS_MAP_KEY` no painel do serviço onde o container
roda (mesmo lugar onde estão `ANTHROPIC_API_KEY` e `COLLECTOR_SECRET`) e reinicie o serviço.

## 4. Avisar o Claude

Depois de configurar, diga "a MAP_KEY está configurada". A partir daí o coletor FIRMS
é ativado como fonte de conferência.
