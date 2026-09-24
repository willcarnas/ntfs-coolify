"""Indicadores técnicos do motor de sinais.

Reexporta a implementação pura e testável da biblioteca comum (secao 13).
"""
from comum.indicadores import (  # noqa: F401
    bollinger,
    calcular_indicadores,
    ema,
    macd,
    rsi,
    sma,
    ultimo,
    variacao_pct,
    volume_relativo,
)

__all__ = [
    "sma",
    "ema",
    "rsi",
    "macd",
    "bollinger",
    "volume_relativo",
    "variacao_pct",
    "ultimo",
    "calcular_indicadores",
]
