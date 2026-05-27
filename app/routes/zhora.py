import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.zhora_service import (
    ask_gemini,
    build_climate_context,
    context_to_text,
    get_latest_context,
    save_context_snapshot,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/zhora", tags=["Zhora Agent"])


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    question: str
    answer: str
    context_used: str


@router.post("/ask", response_model=AskResponse)
def ask_zhora(payload: AskRequest):
    if not payload.question.strip():
        raise HTTPException(status_code=422, detail="question não pode estar vazio")

    try:
        try:
            ctx = build_climate_context()
            context_text = context_to_text(ctx)
        except Exception as e:
            logger.warning("Falha ao buscar contexto do DB, usando snapshot: %s", e)
            context_text = get_latest_context() or "Contexto climático não disponível."

        answer = ask_gemini(payload.question, context_text)
        return {"question": payload.question, "answer": answer, "context_used": context_text}

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Erro em /api/zhora/ask: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao processar pergunta")


@router.post("/context/refresh")
def refresh_context():
    """Rebuild and persist a fresh climate context snapshot."""
    try:
        ctx = build_climate_context()
        snapshot_id = save_context_snapshot(ctx)
        return {
            "status": "ok",
            "snapshot_id": snapshot_id,
            "context": context_to_text(ctx),
        }
    except Exception as e:
        logger.error("Erro em /api/zhora/context/refresh: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao atualizar contexto")


@router.get("/context")
def get_context():
    """Return the most recently stored climate context snapshot."""
    try:
        content = get_latest_context()
        if content is None:
            return {"context": None, "message": "Nenhum snapshot disponível. Use POST /context/refresh."}
        return {"context": content}
    except Exception as e:
        logger.error("Erro em /api/zhora/context: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar contexto")
