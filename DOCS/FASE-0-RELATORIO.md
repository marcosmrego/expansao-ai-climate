# Fase 0: relatório de verificação das fontes

Data dos testes: 2026-10-19 (chamadas reais, sem chave, exceto onde indicado).
Este relatório alimenta as seções 4 e 5 da SPEC.

## Resumo das decisões

| Tema | Resultado | Impacto |
|---|---|---|
| Focos de calor | O INPE publica CSV diário e histórico por arquivo, **sem chave**, já com município, UF, bioma, FRP, risco de fogo e dias sem chuva | **A prioridade se inverte: INPE vira fonte primária da Fase 1 e o FIRMS vira fonte de conferência** (a SPEC §5.1 previa essa avaliação) |
| Resolução geográfica | O INPE já entrega município, UF e bioma | Não é preciso PostGIS nem shapely na Fase 1 |
| PostGIS | **Indisponível** no Postgres de produção (17.9 em Alpine, só `pg_trgm` na lista de extensões) | Quando for necessário geoprocessamento (Fase 4), usar `shapely` em memória |
| Reservatórios | O SAR da ANA tem API oficial (ArcGIS FeatureServer), mas só com a **última medição** | Coleta diária acumula histórico próprio. O histórico de 5 anos exige backfill pela página do SAR (autorizado pelo autor, ver abaixo) |
| Desmatamento | TerraBrasilis WFS funciona e tem camadas DETER e PRODES | Sem bloqueios |

## 1. Focos de calor

### 1.1 INPE (fonte primária, sem chave)

Base: `https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/`

| Caminho | Conteúdo |
|---|---|
| `diario/Brasil/focos_diario_br_AAAAMMDD.csv` | Um arquivo por dia, atualizado ao longo do dia (~13 mil linhas, 2 MB) |
| `10min/focos_10min_AAAAMMDD_HHMM.csv` | Atualização a cada 10 minutos |
| `mensal/Brasil/focos_mensal_br_AAAAMM.csv` | Consolidado mensal |
| `anual/Brasil_sat_ref/focos_br_ref_AAAA.zip` | **Satélite de referência (AQUA_M-T), 2003 até hoje**. É a série correta para média histórica e anomalia |
| `anual/Brasil_todos_sats/focos_br_todos-sats_AAAA.zip` | Todos os satélites, 1998 até hoje |

Colunas: `id, lat, lon, data_hora_gmt, satelite, municipio, estado, pais, municipio_id, estado_id, pais_id, numero_dias_sem_chuva, precipitacao, risco_fogo, bioma, frp`.

Observações:
- O CSV diário de 2026-10-18 tinha 9 satélites (GOES-19, NOAA-20, NOAA-21, NPP-375, NPP-375D, AQUA_M-T, TERRA_M-T, MSG-03, AQUA_M-M). Contar tudo junto mistura sensores de resolução diferente, portanto **a anomalia deve usar só o satélite de referência**. Os demais aparecem no mapa e na contagem bruta.
- O `id` é um UUID estável, então serve de chave natural (`fonte + id`).
- Cobertura nacional (inclui `pais`, então filtrar `Brasil`).
- Sem autenticação e sem limite documentado. Mesmo assim, coletar de forma educada (1 requisição por ciclo, cabeçalho `If-Modified-Since`, espera progressiva em 429/5xx).
- Pendência: confirmar a licença e as condições de uso do INPE para a página de créditos (a página de dados abertos do Programa Queimadas).

### 1.2 NASA FIRMS (conferência)

Conforme a documentação oficial: formato CSV, `MAP_KEY` obrigatória, **5.000 transações por 10 minutos** (consulta de vários dias conta como várias), `DAY_RANGE` de 1 a 5, bbox `oeste,sul,leste,norte`. Fontes: `VIIRS_SNPP_NRT`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA21_NRT`, `MODIS_NRT` e as `_SP`. O teste real com chave fica pendente: ver `GUIA-FIRMS-MAP-KEY.md`.

## 2. Reservatórios (ANA)

### 2.1 API oficial: SAR ArcGIS FeatureServer

`https://www.snirh.gov.br/arcgis/rest/services/IG/SAR/FeatureServer/{camada}`

| Camada | Sistema | Registros | Limite por página |
|---|---|---|---|
| 0 | SIN | 168 | 2000 |
| 1 | Nordeste e Semiárido | 499 | 2000 |
| 2 | Distrito Federal | n/d | 2000 |
| 3 | Cantareira | n/d | 2000 |
| 4 | Belo Horizonte | n/d | 2000 |

Consulta: `.../query?where=1=1&outFields=*&returnGeometry=false&f=json`. Sem chave.

Campos principais: `SAR_ID`, `SAR_NM`, `SAR_SG_UF`, `SAR_NM_MUNICIPIO`, `SAR_NM_BACIA`, coordenadas, `SAR_QT_CAPACIDADE` (hm³), `SAR_PC_VOLUME`, `SAR_VO_UTIL_ULTIMA`, `SAR_DT_ULTIMA_MEDICAO` (texto `dd/mm/aaaa`).

Pontos de atenção:
- **Só há a última medição.** O histórico próprio começa na primeira coleta.
- No SIN, `SAR_PC_VOLUME` vem nulo e o percentual útil está em `SAR_VO_UTIL_ULTIMA`. No Nordeste ocorre o inverso. O coletor deve normalizar.
- Há reservatórios sem medição recente (ex.: um do Nordeste com última medição em 2025-11-03). A interface deve mostrar a data da medição e marcar "sem medição recente", sem tratar como zero.
- Datas vêm como texto e precisam de conversão explícita.

### 2.2 Histórico: página do SAR (avaliação autorizada)

O autor autorizou avaliar a extração da página (2026-10-19). Achados:
- `https://www.ana.gov.br/sar0/MedicaoSin` tem formulário (`dropDownListEstados`, `dropDownListReservatorios`, `dataInicial`, `dataFinal`) e o botão `ExportarExcel`.
- A tabela de resultados vem por requisição dinâmica (o HTML estático não traz as linhas), e o `POST` de exportação sem a sessão correta retorna erro 500.
- Colunas disponíveis: cota, afluência, defluência, vazão vertida/turbinada/natural, **volume útil (%)**, vazão incremental e data da medição.
- `robots.txt` do domínio `ana.gov.br` não pôde ser lido nos testes (resposta vazia).

Próximo passo (Fase 2): inspecionar a requisição que a página faz ao buscar (aba Rede do navegador), implementar o backfill **uma única vez**, em lotes pequenos, com identificação do projeto no User-Agent, e depois manter só a API oficial. Confirmar os termos de uso antes.

## 3. Desmatamento (TerraBrasilis, INPE)

`https://terrabrasilis.dpi.inpe.br/geoserver/ows` (WFS 2.0.0, GeoJSON suportado).

Camadas confirmadas no GetCapabilities:

| Uso | Camada |
|---|---|
| DETER Amazônia | `deter-amz:deter_amz` (462.921 feições) |
| DETER Cerrado | `deter-cerrado-nb:deter_cerrado` |
| PRODES Amazônia Legal | `prodes-legal-amz:yearly_deforestation` |
| PRODES Amazônia (bioma) | `prodes-amazon-nb:yearly_deforestation_biome` |
| PRODES Cerrado | `prodes-cerrado-nb:yearly_deforestation` |
| PRODES Caatinga, Mata Atlântica, Pampa, Pantanal | `prodes-<bioma>-nb:yearly_deforestation` |
| Limites dos biomas | `prodes-brasil-nb:biomas_brasil` |

Campos do DETER Amazônia: `classname, view_date, areamunkm, municipality, mun_geocod, uf, sensor, satellite, publish_month`. Classes vistas em outubro/2026: `CICATRIZ_DE_QUEIMADA`, `DESMATAMENTO_CR`, `DESMATAMENTO_VEG`, `DEGRADACAO`, `MINERACAO`, `CS_DESORDENADO`, `CS_GEOMETRICO`.
Campos do PRODES (Amazônia Legal): `state, class_name, main_class, year, area_km, image_date, publish_year, sub_class, pub_date`.

Observações:
- `propertyName=` permite trazer só os atributos (sem geometria), que é o caso do painel.
- Filtro por data via `cql_filter=view_date>'AAAA-MM-DD'`. Para coleta incremental, usar `publish_month`/`view_date` com paginação (`startIndex`, `count`).
- A camada do Cerrado ainda precisa de DescribeFeatureType antes da implementação.
- Classes `CICATRIZ_DE_QUEIMADA` e `DEGRADACAO` não são desmatamento por corte raso, então o painel deve separar as classes.

## 4. Banco de produção

Consulta somente leitura em 2026-10-19: PostgreSQL 17.9 (Alpine), 298 MB, usuário com perfil de superusuário. A extensão `postgis` **não consta** em `pg_available_extensions`. Para ter PostGIS seria preciso trocar a imagem do Postgres (ex.: `postgis/postgis`), o que não é necessário agora.

## 5. Mudanças propostas ao plano

1. Fase 1 passa a coletar do **INPE** (CSV diário e 10 min). O FIRMS entra como conferência quando a chave existir.
2. A carga inicial usa os ZIPs anuais do **satélite de referência**, de 2003 até hoje, que dão a média e o desvio por dia do ano.
3. `fire_hotspot` ganha `risco_fogo`, `dias_sem_chuva` e `precipitacao`, que o INPE entrega.
4. Fase 2 coleta a API do SAR todo dia e guarda o histórico, sem esperar pelo backfill.
5. Retenção: pontos brutos por 24 meses e agregados para sempre (aprovado).

## 6. Limitações conhecidas da série de referência (Fase 1)

- O satélite AQUA_M-T é o de referência do INPE, mas a órbita do Aqua deriva desde 2022 e o horário de passagem muda. A contagem diária do satélite de referência tem variação própria (ex.: dias com 150 e outros com 2.000 focos no Brasil), então a comparação usa média de períodos e a faixa de ±1 desvio. A interface não deve dar leitura de tendência a um único dia.
- Pontos de todos os satélites ficam 14 dias; os do satélite de referência, 24 meses. A série diária agregada é permanente.
- Os endpoints públicos não têm rate limit e o `COLLECTOR_SECRET` está vazio em produção (os workflows do n8n não enviam chave). Registrado como pendência de segurança, anterior a esta fase.
