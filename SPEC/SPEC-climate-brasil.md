# SPEC: Expansão AI Climate, área Brasil

Versão: 0.2 (Fase 0 concluída: seções 4 e 5 verificadas)
Data: 2026-10-19
Autor: Marcos, com apoio do Claude
Projeto: https://climate.expansao-ai.com.br/

---

## 1. Contexto

O Expansão AI Climate monitora índices climáticos globais (ONI, SOI, PDO, NAO, AMO, QBO, IOD, MJO, CO2 e gelo polar) com dados de NOAA, NOAA PSL e NSIDC. Tem análise preditiva por IA e a Zhora, uma analista climática em chat.

Hoje o site responde bem "o que está acontecendo no clima global" e pouco "o que isso significa observado no Brasil". Esta SPEC adiciona uma área Brasil com dados observados por satélite e por órgãos oficiais, e conecta esses dados aos índices que o site já mostra.

## 2. Objetivos

1. Mostrar o que está acontecendo no Brasil com dados públicos atualizados: focos de calor, reservatórios e desmatamento.
2. Cruzar esses dados com o estado atual dos índices climáticos já existentes (ENSO, IOD, MJO).
3. Dar à Zhora contexto de dados observados no Brasil, para respostas mais úteis sobre safra, seca e chuva.
4. Manter o projeto sustentável: coleta agendada, histórico próprio, sem depender de scraping frágil.

## 3. Fora de escopo (nesta versão)

- Previsão própria de queimadas, nível de reservatório ou desmatamento.
- Dados privados ou de clientes (CWI ou qualquer outro). Só fontes públicas.
- Processamento de imagens de satélite bruto (Sentinel-2, Landsat). Fica no backlog, depois da fase 5.
- Autenticação de usuários, contas e área logada.

## 4. Premissas a confirmar com o código existente

O autor desta SPEC viu apenas o site publicado, não o repositório. Antes de implementar, confirmar e registrar aqui:

| Item | Resposta |
|---|---|
| Linguagem e framework do backend | Python 3.11 e FastAPI, `psycopg2` síncrono sem pool. Entrada em `api/zhora_api.py` (monólito), rotas novas em `app/routes/` |
| Como o front-end é servido (estático, SPA, SSR) | Estático (HTML, CSS e JS puros em `dashboard/`), sem build, servido pelo próprio FastAPI |
| Onde os dados dos índices atuais são guardados | PostgreSQL 17, schema `climate`, migrações SQL numeradas à mão em `database/sql/` (sem PostGIS) |
| Como a coleta atual é agendada | n8n chama `POST /api/collect/<fonte>` com `X-API-Key` (`COLLECTOR_SECRET`). Workflows em `n8n/` (diário 07h UTC e mensal) |
| Onde roda em produção e como é feito o deploy | Container Docker (`uvicorn`). Detalhe da hospedagem a confirmar com o autor |
| Como a Zhora recebe o contexto | Prompt montado no backend: `build_climate_context()` consulta o banco, `context_to_text()` gera o texto e `ask_claude()` envia junto da pergunta |
| Biblioteca de gráficos usada no front | Chart.js, mais d3 e topojson para o mapa-múndi |

Resultados completos da verificação das fontes em `DOCS/FASE-0-RELATORIO.md`.

Regra: os novos módulos seguem a stack e os padrões que já existem. Se a SPEC conflitar com o código atual, vale o código e a SPEC é ajustada.

## 5. Fontes de dados

Notas de verificação: o que está marcado como confirmado foi checado em documentação pública em 2026-10-19. O que está marcado como a confirmar precisa de teste real antes de implementar.

### 5.1 Focos de calor

**NASA FIRMS (fonte principal da fase 1)**
- Área de API em https://firms.modaps.eosdis.nasa.gov/api/
- Entrega detecções ativas de fogo por bounding box, sensor e intervalo de dias. Sensores: MODIS (Terra e Aqua), VIIRS (S-NPP, NOAA-20, NOAA-21) e Landsat.
- Formato de resposta: apenas CSV (confirmado em sessão de perguntas e respostas da NASA).
- Exige MAP_KEY gratuita. Limite documentado por terceiros: 5.000 transações por 10 minutos por chave. Tratar como a confirmar na página oficial.
- A chave fica em variável de ambiente (FIRMS_MAP_KEY). Nunca no repositório, nunca em log, nunca no front-end.

**INPE, Programa Queimadas (fonte complementar e de conferência)**
- BDQueimadas e sistema de dados abertos do Programa Queimadas, com API programática e geosserviços OGC (WMS e WFS).
- O banco registra focos desde 1998 e permite exportar em CSV, GeoJSON, KML e Shapefile.
- Os focos trazem atributos úteis como dias sem chuva e risco de fogo.
- A confirmar: endpoint exato da API de dados abertos, limites de consulta e se há campo de bioma e município já resolvido.

Decisão original: usar FIRMS como fonte de coleta contínua e INPE para enriquecer.

**Revisão (Fase 0, 2026-10-19): prioridade invertida.** O servidor de dados abertos do INPE (`dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/`) publica, sem chave, CSV diário, a cada 10 minutos e mensal, mais ZIPs anuais desde 1998 (satélite de referência AQUA_M-T desde 2003). As colunas incluem município, UF, bioma, FRP, risco de fogo e dias sem chuva. Passa a ser a fonte primária da Fase 1. O FIRMS vira fonte de conferência (opcional, depende da `FIRMS_MAP_KEY`). Os dois não se somam, porque os focos do INPE derivam dos mesmos satélites. A anomalia usa apenas o satélite de referência.

### 5.2 Reservatórios

**ANA, Sistema de Acompanhamento de Reservatórios (SAR)**
- Cobre reservatórios do Sistema Interligado Nacional (162 reservatórios, dados diários) e do Nordeste e Semiárido (537 reservatórios), além de sistemas de abastecimento como o Cantareira.
- Há consulta de dados históricos no próprio SAR.
- **Confirmado (2026-10-19):** API oficial ArcGIS FeatureServer em `https://www.snirh.gov.br/arcgis/rest/services/IG/SAR/FeatureServer/{0..4}` (SIN, Nordeste, DF, Cantareira, BH), sem chave, até 2000 registros por página. Entrega só a **última medição** de cada reservatório, portanto o histórico próprio começa na primeira coleta.
- Histórico de 5 anos: só pela página do SAR (`/sar0/MedicaoSin`, com exportação para Excel). O autor autorizou avaliar a extração (2026-10-19). Fazer uma vez, em lotes pequenos e conferindo os termos de uso, na Fase 2.

### 5.3 Desmatamento

**TerraBrasilis (INPE), projetos DETER e PRODES**
- Dados disponíveis por download direto de arquivos e por serviço WFS no GeoServer em https://terrabrasilis.dpi.inpe.br/geoserver/ows (confirmado).
- O WFS aceita filtro por data e paginação. O servidor impõe limite por requisição, então a coleta deve paginar.
- PRODES usa ano próprio, de 1 de agosto a 31 de julho. O modelo de dados precisa guardar o ano PRODES, não só o ano civil.
- DETER no Pantanal e em áreas não florestais da Amazônia são dados experimentais, segundo o INPE. Marcar isso na interface.
- **Confirmado (2026-10-19):** camadas `deter-amz:deter_amz`, `deter-cerrado-nb:deter_cerrado`, `prodes-legal-amz:yearly_deforestation`, `prodes-cerrado-nb:yearly_deforestation` e as demais `prodes-<bioma>-nb:yearly_deforestation`. Lista completa e campos no relatório da Fase 0.

### 5.4 Fase posterior

- MapBiomas: uso e cobertura do solo por município, atualização anual.
- SNIS: indicadores de saneamento por município. Liga o painel ao domínio de água e esgoto.
- Sentinel-2: espelho d'água de reservatórios por imagem. Tecnicamente mais pesado, exige validação contra o SAR.

## 6. Arquitetura proposta

Seguir a stack existente (ver seção 4). O desenho abaixo é lógico, não prescreve tecnologia.

```
Fontes externas  ->  Coletores (agendados)  ->  Armazenamento  ->  API interna  ->  Front-end
 FIRMS, INPE,         um por fonte,              histórico próprio    endpoints        módulos da
 ANA, TerraBrasilis   idempotentes               + metadados          por módulo       área Brasil
                                                                            \
                                                                             ->  Contexto da Zhora
```

### 6.1 Contrato de um coletor

Todo coletor segue o mesmo contrato, para que adicionar uma fonte seja repetir um padrão:

- Entrada: janela de datas e parâmetros da fonte, via configuração.
- Saída: registros normalizados gravados no armazenamento.
- Idempotente: rodar duas vezes a mesma janela não duplica registros (chave natural por fonte).
- Falha segura: erro de uma fonte não derruba as outras nem apaga dados antigos.
- Registro de execução: data e hora, janela coletada, quantidade de registros, status e mensagem de erro.
- Respeita limites da fonte (taxa de requisição, tamanho de página) e usa espera progressiva em caso de erro 429 ou 5xx.
- Guarda o dado bruto mínimo necessário para reprocessar (ou o hash e a data da resposta), para auditoria.

### 6.2 Agendamento sugerido

| Módulo | Frequência inicial | Observação |
|---|---|---|
| Focos de calor | a cada 3 horas | VIIRS e MODIS passam várias vezes ao dia. Ajustar conforme limite da API |
| Reservatórios | 1 vez ao dia | SIN atualiza diariamente |
| Desmatamento (DETER) | 1 vez ao dia | Dado muda aos poucos |
| Desmatamento (PRODES) | 1 vez ao mês | Taxa anual, muda raramente |

### 6.3 Modelo de dados (rascunho)

**fire_hotspot**
- id interno, fonte (firms ou inpe), sensor, satélite
- data e hora da detecção (UTC), latitude, longitude
- intensidade (potência radiativa do fogo, quando disponível), confiança
- uf, município e bioma (resolvidos por interseção com malha oficial, ou vindos do INPE)
- chave natural: fonte + sensor + data/hora + latitude + longitude

**fire_daily_agg** (agregado para o painel ficar rápido)
- data, nível (brasil, uf, bioma, município), código do nível, contagem de focos, soma de intensidade
- média histórica do mesmo dia do ano e desvio, para calcular anomalia

**reservoir**
- id, nome, sistema (SIN, Nordeste e Semiárido, abastecimento), uf, capacidade, latitude, longitude

**reservoir_reading**
- reservoir_id, data, volume útil percentual, volume absoluto (se houver), fonte

**deforestation_alert**
- id, projeto (DETER-Amazônia, DETER-Cerrado, etc.), data do alerta, classe, área em hectares, uf, município, geometria simplificada
- flag experimental (para Pantanal e áreas não florestais)

**deforestation_rate**
- projeto, ano PRODES, bioma ou uf, área em km2

**collector_run**
- fonte, início, fim, janela, registros, status, erro

Observação: o histórico próprio é decisivo para calcular anomalias e para o cruzamento com ENSO. Guardar o máximo de histórico que as fontes permitirem na carga inicial.

## 7. API interna (rascunho)

Nomes e formatos a alinhar com o padrão da API atual do projeto.

- GET /api/brasil/focos/resumo?nivel=uf&periodo=30d  : contagem, anomalia e ranking
- GET /api/brasil/focos/serie?nivel=bioma&codigo=cerrado&periodo=365d : série diária com média histórica
- GET /api/brasil/focos/mapa?bbox=...&periodo=7d : pontos para mapa (com limite e agregação por zoom)
- GET /api/brasil/reservatorios/resumo : situação atual por sistema
- GET /api/brasil/reservatorios/{id}/serie?periodo=5y
- GET /api/brasil/desmatamento/alertas?projeto=deter-amz&periodo=90d
- GET /api/brasil/desmatamento/taxa?projeto=prodes&bioma=amazonia
- GET /api/brasil/contexto : resumo estruturado do estado atual, usado pelo front e pela Zhora
- GET /api/brasil/status : última coleta bem-sucedida de cada fonte

Requisitos: paginação onde couber, cache de leitura curto, resposta em JSON, campos de data em ISO 8601.

## 8. Front-end

### 8.1 Navegação
Nova aba Brasil ao lado de ENSO, Modulação, Diários, Análise e Zhora.

### 8.2 Módulos da fase 1 e 2

**Focos de calor**
- Cartão de topo: focos nas últimas 24 horas e nos últimos 30 dias, com comparação à média histórica do mesmo período.
- Ranking de UFs e biomas.
- Série temporal do ano corrente sobre a média histórica.
- Mapa com pontos recentes (agregados quando o zoom for baixo).
- Rodapé do módulo: fonte, sensor, hora da última coleta.

**Reservatórios**
- Visão por sistema (SIN, Nordeste e Semiárido, abastecimento) com percentual atual e variação em 30 dias.
- Lista filtrável por UF e por faixa de volume.
- Página de detalhe com série de 5 anos.

**Desmatamento (fase 3)**
- Alertas recentes por projeto e UF, área acumulada no ano PRODES corrente.
- Aviso visível quando o dado for experimental.

### 8.3 Cruzamento com os índices climáticos
Bloco chamado "Clima global e Brasil" que mostra lado a lado o estado atual de ENSO, IOD e MJO e os indicadores da área Brasil.

Regra de honestidade: nenhuma frase do tipo "o El Niño causa mais focos" aparece na interface sem validação estatística feita sobre o histórico coletado e sem indicação de que é associação, não causa. Na fase inicial, mostrar os dois lado a lado sem afirmar relação. A análise de associação entra na fase 5, com metodologia descrita.

### 8.4 Região do usuário
O recurso Clima na sua região passa a aceitar UF e município e mostra, para o local escolhido, focos, reservatórios próximos e o estado do ENSO juntos.

### 8.5 Requisitos gerais
- Funciona bem em celular.
- Textos em linguagem simples, com ícone de informação para termos técnicos (como já é feito hoje).
- Todo gráfico mostra fonte e data da última atualização.
- Estados de carregamento, vazio e erro tratados (dado indisponível não pode aparecer como zero).

## 9. Zhora

- O contexto enviado à Zhora ganha um bloco estruturado vindo de /api/brasil/contexto, com: anomalia de focos por bioma, situação dos reservatórios por sistema, alertas de desmatamento recentes e data de cada coleta.
- Instrução ao modelo: citar sempre a data do dado, dizer quando o dado está desatualizado ou ausente, e não afirmar causalidade entre índice climático e fenômeno observado.
- Manter o aviso existente de que o conteúdo não substitui boletins oficiais, e acrescentar as fontes novas.
- Cuidar do tamanho do contexto: enviar resumos, não séries completas.

## 10. Requisitos não funcionais

- Segredos (MAP_KEY e outros) só em variáveis de ambiente ou no cofre da hospedagem.
- Logs sem chaves e sem dados pessoais.
- Cada fonte tem página de créditos no site com nome, link e licença ou condição de uso, conferida na hora da implementação.
- Painel não pode quebrar se uma fonte cair: mostrar o último dado com a data e um aviso de defasagem.
- Testes: coletores com respostas gravadas (fixtures) de cada fonte, testes de idempotência, testes dos cálculos de anomalia.
- Monitoramento simples: alerta quando uma fonte ficar sem coleta bem-sucedida além de um limite (por exemplo 2x a frequência esperada).

## 11. Plano de entregas

**Fase 0: preparação (1 a 2 dias)**
- Preencher a seção 4 olhando o repositório.
- Obter a MAP_KEY do FIRMS.
- Rodar GetCapabilities no TerraBrasilis e testar uma chamada real em cada fonte, registrando formato e limites na seção 5.
- Critério de aceite: seção 5 sem itens a confirmar nos pontos da fase 1.

**Fase 1: focos de calor (primeira entrega)**
- Coletor FIRMS, armazenamento, agregados diários, endpoints de focos, aba Brasil com o módulo de focos.
- Carga inicial de histórico (o que a API permitir).
- Critério de aceite: painel mostra focos das últimas 24 horas e 30 dias com comparação à média histórica, hora da última coleta visível, e coleta recorrente rodando por 7 dias sem falha manual.

**Fase 2: reservatórios**
- Coletor ANA SAR (ou fonte alternativa confirmada), módulo de reservatórios.
- Critério de aceite: situação atual por sistema e série de 5 anos por reservatório.

**Fase 3: desmatamento**
- Coletor DETER via WFS com paginação, taxa PRODES, módulo na interface.
- Critério de aceite: alertas recentes por UF e acumulado do ano PRODES corrente, com aviso de dado experimental onde couber.

**Fase 4: Zhora com contexto Brasil e região do usuário**
- Endpoint de contexto, ajuste do prompt, recurso Clima na sua região com UF e município.
- Critério de aceite: respostas da Zhora citam dados e datas da área Brasil, e declaram quando faltam dados.

**Fase 5: associação com índices climáticos (opcional)**
- Estudo estatístico sobre o histórico acumulado (por exemplo anomalia de focos por bioma contra fase do ENSO e do IOD, com defasagem).
- Só publica na interface o que passar por critério definido antes, com texto de limitações.

**Backlog**
- MapBiomas, SNIS, Sentinel-2 (espelho d'água), qualidade da água por sensoriamento.

## 12. Riscos e pontos de atenção

| Risco | Mitigação |
|---|---|
| Fonte muda formato ou endpoint sem aviso | Fixtures nos testes, validação de schema na coleta, alerta de falha |
| Limite de requisições do FIRMS | Janelas de coleta incrementais, cache, espaçar chamadas |
| API ou arquivo da ANA não existir de forma programática | Verificar dados abertos da ANA primeiro, avaliar alternativa e pedir decisão antes de qualquer extração de página |
| Volume de pontos de focos pesar no mapa | Agregação por zoom, limite de pontos por resposta |
| Interpretar mal um índice climático como causa | Regra da seção 8.3, texto de limitações |
| Dado experimental (DETER Pantanal e áreas não florestais) ser lido como definitivo | Marca visível na interface |
| Custo da Zhora subir com contexto maior | Enviar resumos, limitar tamanho, cache por período |
| Confusão entre ano civil e ano PRODES | Campo próprio no modelo e rótulo no gráfico |

## 13. Questões em aberto

1. Quais biomas e UFs entram na primeira versão (Brasil inteiro ou foco inicial no Cerrado e na Amazônia)?
2. Há interesse em notificações (por exemplo e-mail ou WhatsApp) quando houver anomalia forte de focos ou queda grande de reservatório?
3. A área Brasil fica gratuita como o restante do site, ou haverá recursos pensados para uso profissional (agro, saneamento)?
4. Qual a política de guarda de histórico (por quantos anos, e com que nível de detalhe para focos)?
5. Idioma: manter só português ou preparar para outros idiomas?

## 14. Fontes consultadas na elaboração

- NASA FIRMS, documentação da API: https://firms.modaps.eosdis.nasa.gov/api/
- NASA Earthdata, perguntas e respostas sobre FIRMS (formato CSV da Area API)
- INPE, Programa Queimadas e BDQueimadas (dados abertos, exportação CSV, GeoJSON, KML, Shapefile)
- ANA, Sistema de Acompanhamento de Reservatórios (SAR) e manual do sistema
- INPE, TerraBrasilis: download de dados, WFS e documentação de paginação: https://terrabrasilis.dpi.inpe.br/
- Site atual do projeto: https://climate.expansao-ai.com.br/
