"""Gera posts diários para o blog ENSO Tracker usando knowledge_base como contexto RAG."""

import json
import logging
import os
import re
import time
from datetime import date, timezone, datetime

import anthropic
from dotenv import load_dotenv

from database.db import conectar
from app.services.zhora_service import build_climate_context, context_to_text, _track_usage

load_dotenv()

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL   = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

_SYSTEM_BLOG = (
    "Você é um jornalista científico especializado em clima e ENSO. "
    "Escreve para o site ENSOTracker.com — público educado mas não especialista. "
    "Tom: objetivo, fluente, informativo. Sem alarmismo, sem linguagem de vendas. "
    "Use markdown simples no corpo: **negrito** para valores-chave, parágrafos separados por linha em branco. "
    "Nunca use títulos com # nem bullet lists. Apenas parágrafos corridos."
)

_BLOG_PROMPT_TMPL = """\
DATA DE HOJE: {today}

ESTADO CLIMÁTICO ATUAL:
{climate_ctx}

ARTIGOS RECENTES (últimos 7 dias) — use como contexto e cite quando relevante:
{articles_block}

Escreva uma análise editorial em português sobre o estado atual do ENSO e do clima global.
A análise deve ter entre 4 e 6 parágrafos e ~400 palavras.
Cite os artigos acima quando pertinentes (mencione a fonte entre parênteses, ex: "segundo o Carbon Brief").
No final inclua um parágrafo de perspectiva para os próximos 30-60 dias.

Responda APENAS com JSON válido no formato abaixo (sem texto fora do JSON):
{{
  "titulo": "Título jornalístico chamativo com até 90 caracteres",
  "resumo": "Duas frases resumindo o post para o card de listagem.",
  "corpo": "Corpo completo em markdown simples (parágrafos separados por \\n\\n)."
}}
"""


def _fetch_recent_articles(conn, days: int = 7, limit: int = 12) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT source, title, summary, url, published_at
        FROM climate.knowledge_base
        WHERE published_at >= NOW() - INTERVAL '%s days'
        ORDER BY published_at DESC
        LIMIT %s
        """,
        (days, limit),
    )
    rows = cur.fetchall()
    return [
        {"source": r[0], "title": r[1], "summary": r[2], "url": r[3],
         "published_at": r[4].strftime("%Y-%m-%d") if r[4] else None}
        for r in rows
    ]


def _articles_block(articles: list[dict]) -> str:
    if not articles:
        return "(nenhum artigo recente disponível)"
    lines = []
    for a in articles:
        dt = f" [{a['published_at']}]" if a["published_at"] else ""
        lines.append(f"- [{a['source']}{dt}] {a['title']}: {(a['summary'] or '')[:200]}")
    return "\n".join(lines)


def _fontes_list(articles: list[dict]) -> list[dict]:
    return [{"source": a["source"], "title": a["title"], "url": a["url"]} for a in articles]


def _parse_json_response(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("Resposta não contém JSON válido")
    return json.loads(match.group(0))


def _strip_headers(text: str) -> str:
    lines = text.splitlines()
    cleaned = [l for l in lines if not l.strip().startswith("#")]
    result = "\n".join(cleaned).strip()
    return re.sub(r"\n{3,}", "\n\n", result)


def gerar_post(today: date | None = None) -> dict:
    today = today or date.today()
    slug  = f"enso-{today.isoformat()}"

    conn = conectar()
    try:
        # idempotente: já existe post para hoje?
        cur = conn.cursor()
        cur.execute("SELECT id FROM climate.blog_posts WHERE slug = %s", (slug,))
        if cur.fetchone():
            logger.info("Post %s já existe, pulando geração.", slug)
            return {"status": "already_exists", "slug": slug}

        ctx     = build_climate_context()
        ctx_txt = context_to_text(ctx)
        artigos = _fetch_recent_articles(conn)

        prompt = _BLOG_PROMPT_TMPL.format(
            today=today.isoformat(),
            climate_ctx=ctx_txt,
            articles_block=_articles_block(artigos),
        )

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        t0 = time.monotonic()
        msg = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2048,
            system=_SYSTEM_BLOG,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed = int((time.monotonic() - t0) * 1000)
        _track_usage("blog-generator", ANTHROPIC_MODEL,
                     msg.usage.input_tokens, msg.usage.output_tokens, elapsed)

        raw = msg.content[0].text
        data = _parse_json_response(raw)

        titulo = data.get("titulo", "").strip()
        resumo = data.get("resumo", "").strip()
        corpo  = _strip_headers(data.get("corpo", "").strip())

        if not titulo or not corpo:
            raise ValueError(f"Campos obrigatórios ausentes. Raw: {raw[:300]}")

        cur.execute(
            """
            INSERT INTO climate.blog_posts
                (slug, titulo, corpo, resumo, fase_enso, oni_valor, fontes, publicado_em)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (slug) DO NOTHING
            """,
            (
                slug, titulo, corpo, resumo,
                ctx.get("classificacao"),
                ctx.get("oni"),
                json.dumps(_fontes_list(artigos)),
                datetime.now(timezone.utc),
            ),
        )
        conn.commit()
        logger.info("Post '%s' gerado e salvo.", titulo)
        return {"status": "created", "slug": slug, "titulo": titulo}

    except Exception as e:
        conn.rollback()
        logger.error("Erro ao gerar post: %s", e)
        raise
    finally:
        conn.close()


def main() -> dict:
    result = gerar_post()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    main()
