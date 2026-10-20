"""Cálculos puros dos reservatórios: faixas, recência e médias (sem acesso a banco)."""
from datetime import date
from typing import Optional

SISTEMA_NOMES = {
    "SIN": "Sistema Interligado Nacional",
    "NORDESTE": "Nordeste e Semiárido",
    "CANTAREIRA": "Cantareira",
    "DF": "Distrito Federal",
    "RMBH": "Região Metropolitana de BH",
}
# Medição considerada recente: o Nordeste mede com menos frequência que os demais.
RECENTE_DIAS = {"NORDESTE": 30}
RECENTE_DIAS_PADRAO = 7
FAIXAS = (("critico", 20.0), ("baixo", 40.0), ("medio", 60.0), ("bom", 80.0))
FAIXA_TOPO = "alto"
FAIXA_NOMES = {"critico": "Abaixo de 20%", "baixo": "20% a 40%", "medio": "40% a 60%",
               "bom": "60% a 80%", "alto": "Acima de 80%"}


def faixa_de(pct: Optional[float]) -> Optional[str]:
    if pct is None:
        return None
    for nome, limite in FAIXAS:
        if pct < limite:
            return nome
    return FAIXA_TOPO


def recente(sistema: str, data_leitura: Optional[date], hoje: date) -> bool:
    if data_leitura is None:
        return False
    return (hoje - data_leitura).days <= RECENTE_DIAS.get(sistema, RECENTE_DIAS_PADRAO)


def media_pct(itens: list[tuple[float, Optional[float]]]) -> tuple[Optional[float], Optional[str]]:
    """Média do volume (%). Ponderada pela capacidade só quando todos têm capacidade."""
    if not itens:
        return None, None
    if all(cap and cap > 0 for _, cap in itens):
        total = sum(cap for _, cap in itens)
        return sum(pct * cap for pct, cap in itens) / total, "ponderada"
    return sum(pct for pct, _ in itens) / len(itens), "simples"


def variacao_pp(atual: Optional[float], anterior: Optional[float]) -> Optional[float]:
    """Variação em pontos percentuais."""
    if atual is None or anterior is None:
        return None
    return atual - anterior
