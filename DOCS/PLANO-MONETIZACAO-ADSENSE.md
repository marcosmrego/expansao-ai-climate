# Plano de monetização com Google AdSense

Registrado em 21/10/2026. Nada deste plano foi executado ainda.

## Resumo

Monetizar `climate.expansao-ai.com.br` com o Google AdSense, em duas fases:

1. **Preparação:** o que o Google exige para aprovar o site. Não depende do AdSense.
2. **Anúncios:** depois da aprovação, colocar os espaços de anúncio nos lugares seguros.

O maior risco é a **reprovação por "conteúdo de pouco valor"**. O Google costuma reprovar sites que são só painéis de dados com pouco texto, e o painel novo (aba Painel) tem pouco texto corrido.

## O que só você pode fazer

- [ ] Criar a conta no AdSense (https://adsense.google.com) com os dados fiscais e bancários.
- [ ] Adicionar o domínio `climate.expansao-ai.com.br` na conta e pedir a revisão.
- [ ] Esperar a aprovação (de dias a algumas semanas).
- [ ] Anotar o ID de publicador (`ca-pub-XXXXXXXXXXXXXXXX`) e passar para quem for implementar.

Dica: peça a revisão só depois da Fase 1 pronta. Um pedido reprovado atrasa o recomeço.

## Fase 1: preparação (antes de pedir a revisão)

### 1.1 Conteúdo original
O Google avalia se o site tem texto útil e original. O Climate tem dados próprios, análise por IA e o blog do ENSO Tracker (https://ensotracker.expansao-ai.com.br/blog.html). Falta texto explicativo no próprio domínio.

- [ ] Páginas de texto no site, por exemplo: "O que é o ONI", "Como ler o MJO", "Como o El Niño afeta o Brasil", "Focos de calor: como o INPE mede", "Como interpretar o desmatamento DETER".
- [ ] Cada página com pelo menos 500 a 800 palavras, escritas de forma original (não copiar da NOAA nem do INPE).
- [ ] Linkar essas páginas no menu e no rodapé.
- [ ] Avaliar levar o blog para o mesmo domínio ou linkar com destaque.

### 1.2 Páginas obrigatórias
- [ ] Política de privacidade (citar cookies, Google AdSense, analytics, LGPD).
- [ ] Termos de uso.
- [ ] Página de contato (e-mail visível).
- [ ] Página "Sobre", com quem mantém o projeto.
- Dados necessários: nome do responsável legal e e-mail de contato.

### 1.3 Consentimento de cookies (LGPD)
- [ ] Banner de consentimento. Sem consentimento, os anúncios devem ser servidos **sem personalização**.
- [ ] Para visitantes do Espaço Econômico Europeu e do Reino Unido, o Google exige uma plataforma de consentimento (CMP) certificada. O Google oferece uma gratuita dentro do AdSense (Privacidade e mensagens).
- [ ] O script de anúncios só deve carregar depois do consentimento.

### 1.4 Arquivos técnicos
- [ ] `ads.txt` na raiz do site (`https://climate.expansao-ai.com.br/ads.txt`) com a linha:
  `google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0`
  (trocar pelo seu ID de publicador).
- [ ] `robots.txt` e `sitemap.xml` válidos.
- [ ] HTTPS ativo em todo o site (já está).

## Fase 2: anúncios (depois da aprovação)

### 2.1 Onde colocar

| Lugar | Pode? | Observação |
|---|---|---|
| Mapa-herói e faixa de KPIs (aba Painel) | **Não** | É o diferencial visual; anúncio destruiria a primeira impressão. |
| Botões de camada e do ticker | **Não** | Cliques acidentais podem suspender a conta. |
| Abaixo da dobra da aba Início | Sim | Entre blocos de conteúdo. |
| Aba Análise | Sim | Entre as seções de texto. |
| Rodapé | Sim | |
| Páginas de texto e blog | Sim | Melhor desempenho por haver texto. |

### 2.2 Regras técnicas
- [ ] Reservar a **altura fixa** de cada espaço para não causar salto de layout. Meta de CLS abaixo de 0,1 (o guia de performance do projeto).
- [ ] Carregamento tardio (`async`) e só depois do consentimento.
- [ ] Respeitar o orçamento de peso do JS (aba de app: menos de 300 kb comprimido).
- [ ] No celular, no máximo um anúncio visível por tela.
- [ ] Conferir contraste e responsividade dos espaços com o tema escuro.

### 2.3 O que evitar (risco de suspensão)
- Clicar nos próprios anúncios ou pedir cliques.
- Anúncios sobre ou colados a botões e controles do mapa.
- Mais anúncios do que conteúdo na página.

## Estimativa de receita

O AdSense paga por impressão e clique, então **receita depende do tráfego**. Com pouco tráfego, o valor é baixo.

- [ ] Levantar as visitas mensais (Umami e Cloudflare Analytics) e a origem do tráfego (Brasil x exterior).
- Referência: sites de nicho no Brasil costumam ter RPM de poucos reais por mil visitas. Faça a conta com o seu número real antes de investir tempo.

## Alternativas e complementos

- **Patrocínio direto:** agro, energia, seguros e meteorologia. Costuma render mais por visita em site de nicho.
- **Google Ad Manager e outras redes:** só fazem sentido com tráfego maior.
- **Versão premium ou API:** dados e alertas para empresas, em vez de anúncios.

## Ordem sugerida de execução

1. Levantar o tráfego atual e decidir se vale (seção "Estimativa de receita").
2. Fase 1.2: páginas obrigatórias (política de privacidade, termos, contato, sobre).
3. Fase 1.1: pelo menos 3 a 5 páginas de texto original.
4. Fase 1.3 e 1.4: banner de consentimento, `ads.txt` (com o ID provisório ou depois), `robots.txt`, `sitemap.xml`.
5. Criar a conta no AdSense e pedir a revisão.
6. Depois da aprovação, executar a Fase 2.

## Dados que o implementador precisa

- Nome do responsável legal e e-mail de contato (para a política de privacidade).
- ID de publicador do AdSense (`ca-pub-...`), depois da criação da conta.
- Número de visitas mensais, para a estimativa.
