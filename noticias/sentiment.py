"""Classificação simples de sentimento por palavra-chave (RF-07).

Sem ML na Fase 1 (secao 10). Léxico bilíngue (PT/EN) voltado a manchetes de
mercado. Função pura e testável.
"""
from __future__ import annotations

import re
import unicodedata

POSITIVO = {
    "alta", "sobe", "sobem", "subiu", "avança", "avanca", "recorde", "lucro",
    "lucros", "cresce", "crescimento", "ganho", "ganhos", "otimismo", "forte",
    "valorização", "valorizacao", "dispara", "rally", "upgrade", "supera",
    "melhora", "recupera", "estímulo", "estimulo", "aprovação", "aprovacao",
    "surge", "positivo", "bullish", "bull", "up", "rise", "rises", "rally",
    "gain", "gains", "profit", "surge", "record", "strong", "beat", "beats",
    "optimism", "recovery", "boost", "jump", "jumps", "higher",
}

NEGATIVO = {
    "queda", "cai", "caem", "caiu", "despenca", "recua", "perda", "perdas",
    "prejuízo", "prejuizo", "fraco", "fraca", "crise", "pânico", "panico",
    "tensão", "tensao", "guerra", "inflação", "inflacao", "juros altos",
    "recessão", "recessao", "desaceleração", "desaceleracao", "downgrade",
    "abaixo", "negativo", "bearish", "bear", "down", "fall", "falls", "drop",
    "drops", "loss", "losses", "crash", "plunge", "plunges", "weak", "fear",
    "recession", "war", "tension", "lower", "selloff", "sell-off",
}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower()


def pontuar(texto: str) -> float:
    """Score contínuo: (#positivo - #negativo) / (#positivo + #negativo)."""
    limpo = _normalizar(texto)
    palavras = set(re.findall(r"[a-z]+(?:-[a-z]+)?", limpo))
    pos = len(palavras & {_normalizar(p) for p in POSITIVO})
    neg = len(palavras & {_normalizar(n) for n in NEGATIVO})
    if pos + neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


def classificar(texto: str, limiar: float = 0.15) -> tuple[str, float]:
    """Retorna (rotulo, score). Rotulo em positivo|negativo|neutro."""
    score = pontuar(texto)
    if score >= limiar:
        return "positivo", round(score, 3)
    if score <= -limiar:
        return "negativo", round(score, 3)
    return "neutro", round(score, 3)
