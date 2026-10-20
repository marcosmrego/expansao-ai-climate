"""Regras puras do desmatamento (DETER/PRODES): ano PRODES, grupos de classe e dado experimental."""
from datetime import date
from typing import Optional

PROJETO_NOMES = {
    "deter-amz": "DETER Amazônia",
    "deter-cerrado": "DETER Cerrado",
    "prodes-amazonia": "PRODES Amazônia Legal",
    "prodes-cerrado": "PRODES Cerrado",
}
PROJETOS_DETER = ("deter-amz", "deter-cerrado")

# DETER em áreas não florestais e no Pantanal é experimental, segundo o INPE.
PROJETOS_EXPERIMENTAIS = frozenset({"deter-pantanal"})

# Só o corte raso entra no "desmatamento"; degradação, queimada e corte seletivo ficam à parte.
GRUPOS_DESMATAMENTO = {"desmatamento"}
GRUPO_NOMES = {
    "desmatamento": "Desmatamento (corte raso)",
    "corte_seletivo": "Corte seletivo",
    "degradacao": "Degradação",
    "queimada": "Cicatriz de queimada",
    "mineracao": "Mineração",
    "outras": "Outras classes",
}
UFS = frozenset("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())
PERIODOS_ALERTAS = {"30d": 30, "90d": 90, "365d": 365}
_PRODES_MES_INICIO = 8  # o ano PRODES vai de 1º de agosto a 31 de julho


def ano_prodes(dia: date) -> int:
    """Ano PRODES, rotulado pelo ano em que termina (01/08/2025 a 31/07/2026 = 2026)."""
    return dia.year + 1 if dia.month >= _PRODES_MES_INICIO else dia.year


def janela_prodes(ano: int) -> tuple[date, date]:
    return date(ano - 1, _PRODES_MES_INICIO, 1), date(ano, _PRODES_MES_INICIO - 1, 31)


def grupo_classe(classe: Optional[str]) -> str:
    nome = (classe or "").strip().upper()
    if nome.startswith("DESMATAMENTO"):
        return "desmatamento"
    if nome.startswith("CS_"):
        return "corte_seletivo"
    if nome == "DEGRADACAO":
        return "degradacao"
    if nome == "CICATRIZ_DE_QUEIMADA":
        return "queimada"
    if nome == "MINERACAO":
        return "mineracao"
    return "outras"


def experimental(projeto: str) -> bool:
    return projeto in PROJETOS_EXPERIMENTAIS


def um_ano_antes(dia: date) -> date:
    try:
        return dia.replace(year=dia.year - 1)
    except ValueError:  # 29/02 -> 28/02
        return dia.replace(year=dia.year - 1, day=28)
