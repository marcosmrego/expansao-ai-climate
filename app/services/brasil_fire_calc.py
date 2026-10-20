"""Cálculos puros da área Brasil: períodos, janelas históricas e anomalia (sem acesso a banco)."""
import math
import re
from datetime import date, timedelta
from typing import Optional

ANO_INICIAL_SERIE = 2003
JANELA_MINIMA_BASE_DIAS = 7
PERIODO_MAX_DIAS = 3650
LIMIAR_Z = 1.0
MIN_ANOS_BASE = 3

_PERIODO_RE = re.compile(r"^(\d{1,4})([dhy])$")

UF_NOMES = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul",
    "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}
BIOMA_NOMES = {
    "amazonia": "Amazônia", "cerrado": "Cerrado", "caatinga": "Caatinga",
    "mata-atlantica": "Mata Atlântica", "pampa": "Pampa", "pantanal": "Pantanal",
}


def nome_codigo(nivel: str, codigo: str) -> str:
    if nivel == "brasil":
        return "Brasil"
    return (UF_NOMES if nivel == "uf" else BIOMA_NOMES).get(codigo, codigo)


def codigos_do_nivel(nivel: str) -> list[str]:
    if nivel == "brasil":
        return ["BR"]
    return list(UF_NOMES if nivel == "uf" else BIOMA_NOMES)


def codigo_valido(nivel: str, codigo: str) -> bool:
    if nivel == "brasil":
        return codigo == "BR"
    return codigo in (UF_NOMES if nivel == "uf" else BIOMA_NOMES)


def parse_periodo(texto: str) -> int:
    """'24h' -> 1, '7d' -> 7, '365d' -> 365, '5y' -> 1825. Levanta ValueError se inválido."""
    m = _PERIODO_RE.match((texto or "").strip().lower())
    if not m:
        raise ValueError(f"período inválido: {texto!r}")
    n, unidade = int(m.group(1)), m.group(2)
    dias = {"h": max(1, math.ceil(n / 24)), "d": n, "y": n * 365}[unidade]
    if not 1 <= dias <= PERIODO_MAX_DIAS:
        raise ValueError(f"período fora do intervalo: {texto!r}")
    return dias


def _mesmo_dia_em(dia: date, ano: int) -> date:
    try:
        return dia.replace(year=ano)
    except ValueError:  # 29/02 em ano não bissexto
        return dia.replace(year=ano, day=28)


def janelas_base(fim: date, dias: int, ano_inicial: int = ANO_INICIAL_SERIE) -> list[tuple[date, date, int]]:
    """Janela equivalente nos anos anteriores: (início, fim, ano).

    Períodos curtos são ampliados para 7 dias centrados no período, para suavizar
    o ruído diário. Cada janela tem o mesmo comprimento em todos os anos.
    """
    inicio = fim - timedelta(days=dias - 1)
    extra = max(0, JANELA_MINIMA_BASE_DIAS - dias)
    antes, depois = extra // 2, extra - extra // 2
    salto = fim.year - inicio.year  # período que cruza a virada de ano
    return [
        (_mesmo_dia_em(inicio, ano - salto) - timedelta(days=antes),
         _mesmo_dia_em(fim, ano) + timedelta(days=depois), ano)
        for ano in range(ano_inicial + salto, fim.year)
    ]


def comprimento_base(dias: int) -> int:
    return max(dias, JANELA_MINIMA_BASE_DIAS)


def anomalia(media_atual: float, medias_base: list[float]) -> dict:
    """Compara a média diária atual com as médias diárias dos anos anteriores."""
    n = len(medias_base)
    if n < MIN_ANOS_BASE:
        return {"media_historica": None, "desvio": None, "variacao_pct": None, "z": None, "situacao": None}
    media = sum(medias_base) / n
    desvio = math.sqrt(sum((x - media) ** 2 for x in medias_base) / (n - 1))
    variacao = (media_atual - media) / media * 100 if media > 0 else None
    z = (media_atual - media) / desvio if desvio > 0 else None
    return {
        "media_historica": round(media, 2),
        "desvio": round(desvio, 2),
        "variacao_pct": None if variacao is None else round(variacao, 1),
        "z": None if z is None else round(z, 2),
        "situacao": _situacao(z),
    }


def _situacao(z: Optional[float]) -> Optional[str]:
    if z is None:
        return None
    if z >= LIMIAR_Z:
        return "acima"
    if z <= -LIMIAR_Z:
        return "abaixo"
    return "normal"


def desvio_de_somas(soma: float, soma_quadrados: float, n: int) -> float:
    """Desvio amostral a partir de soma e soma de quadrados (dias sem registro contam como zero)."""
    if n < 2:
        return 0.0
    media = soma / n
    variancia = (soma_quadrados / n - media ** 2) * n / (n - 1)
    return math.sqrt(max(variancia, 0.0))


def celula_mapa(zoom: int) -> Optional[float]:
    """Tamanho da célula (graus) para agregar pontos; None = pontos individuais."""
    if zoom >= 7:
        return None
    return {4: 1.0, 5: 0.5, 6: 0.25}.get(zoom, 2.0 if zoom < 4 else 0.25)
