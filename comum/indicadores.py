"""Indicadores técnicos em Python puro (sem pandas/numpy).

Implementação leve para o hardware modesto (Celeron, 4 GB) e funções puras e
testáveis (secao 13). Cada função recebe uma lista de floats e devolve uma
lista alinhada (mesmo comprimento, com `None` no período de aquecimento).
"""
from __future__ import annotations

import math
from typing import Optional

Num = Optional[float]


def _limpar(valores: list[float]) -> list[float]:
    return [float(v) for v in valores if v is not None]


def ultimo(valores: list[Num]) -> Num:
    for v in reversed(valores):
        if v is not None:
            return v
    return None


def sma(valores: list[float], periodo: int) -> list[Num]:
    """Média móvel simples."""
    if periodo <= 0:
        raise ValueError("periodo deve ser > 0")
    saida: list[Num] = [None] * len(valores)
    if len(valores) < periodo:
        return saida
    soma = sum(valores[:periodo])
    saida[periodo - 1] = soma / periodo
    for i in range(periodo, len(valores)):
        soma += valores[i] - valores[i - periodo]
        saida[i] = soma / periodo
    return saida


def ema(valores: list[float], periodo: int) -> list[Num]:
    """Média móvel exponencial (seed = SMA do primeiro bloco)."""
    if periodo <= 0:
        raise ValueError("periodo deve ser > 0")
    saida: list[Num] = [None] * len(valores)
    if len(valores) < periodo:
        return saida
    k = 2.0 / (periodo + 1.0)
    seed = sum(valores[:periodo]) / periodo
    saida[periodo - 1] = seed
    anterior = seed
    for i in range(periodo, len(valores)):
        anterior = valores[i] * k + anterior * (1.0 - k)
        saida[i] = anterior
    return saida


def rsi(valores: list[float], periodo: int = 14) -> list[Num]:
    """RSI com suavização de Wilder."""
    saida: list[Num] = [None] * len(valores)
    if len(valores) <= periodo:
        return saida
    ganhos = 0.0
    perdas = 0.0
    for i in range(1, periodo + 1):
        delta = valores[i] - valores[i - 1]
        if delta >= 0:
            ganhos += delta
        else:
            perdas -= delta
    media_ganho = ganhos / periodo
    media_perda = perdas / periodo

    def _calc(g: float, p: float) -> float:
        if p == 0:
            return 100.0
        rs = g / p
        return 100.0 - (100.0 / (1.0 + rs))

    saida[periodo] = _calc(media_ganho, media_perda)
    for i in range(periodo + 1, len(valores)):
        delta = valores[i] - valores[i - 1]
        ganho = delta if delta > 0 else 0.0
        perda = -delta if delta < 0 else 0.0
        media_ganho = (media_ganho * (periodo - 1) + ganho) / periodo
        media_perda = (media_perda * (periodo - 1) + perda) / periodo
        saida[i] = _calc(media_ganho, media_perda)
    return saida


def macd(
    valores: list[float],
    rapida: int = 12,
    lenta: int = 26,
    sinal: int = 9,
) -> tuple[list[Num], list[Num], list[Num]]:
    """MACD: retorna (linha_macd, linha_sinal, histograma), alinhados."""
    ema_rapida = ema(valores, rapida)
    ema_lenta = ema(valores, lenta)
    linha: list[Num] = [
        (a - b) if (a is not None and b is not None) else None
        for a, b in zip(ema_rapida, ema_lenta)
    ]

    idx = [i for i, v in enumerate(linha) if v is not None]
    linha_sinal: list[Num] = [None] * len(valores)
    if idx:
        trecho = [linha[i] for i in idx]  # type: ignore[misc]
        ema_sinal = ema(trecho, sinal)  # type: ignore[arg-type]
        for pos, valor in zip(idx, ema_sinal):
            linha_sinal[pos] = valor

    histograma: list[Num] = [
        (m - s) if (m is not None and s is not None) else None
        for m, s in zip(linha, linha_sinal)
    ]
    return linha, linha_sinal, histograma


def bollinger(
    valores: list[float],
    periodo: int = 20,
    num_desvios: float = 2.0,
) -> tuple[list[Num], list[Num], list[Num]]:
    """Bandas de Bollinger (média, superior, inferior)."""
    media = sma(valores, periodo)
    superior: list[Num] = [None] * len(valores)
    inferior: list[Num] = [None] * len(valores)
    for i in range(len(valores)):
        if media[i] is None:
            continue
        janela = valores[i - periodo + 1 : i + 1]
        mu = media[i]
        var = sum((x - mu) ** 2 for x in janela) / periodo
        desvio = math.sqrt(var)
        superior[i] = mu + num_desvios * desvio
        inferior[i] = mu - num_desvios * desvio
    return superior, media, inferior


def volume_relativo(volumes: list[float], periodo: int = 20) -> list[Num]:
    """Volume atual dividido pela média do período."""
    media = sma(volumes, periodo)
    saida: list[Num] = [None] * len(volumes)
    for i, (v, m) in enumerate(zip(volumes, media)):
        if m and m > 0:
            saida[i] = v / m
    return saida


def variacao_pct(valores: list[float], periodo: int = 1) -> list[Num]:
    """Variação percentual em relação a `periodo` barras atrás."""
    saida: list[Num] = [None] * len(valores)
    for i in range(periodo, len(valores)):
        base = valores[i - periodo]
        if base:
            saida[i] = (valores[i] - base) / base * 100.0
    return saida


def calcular_indicadores(fechamentos: list[float], volumes: list[float] | None = None) -> dict[str, Num]:
    """Calcula o conjunto padrão e devolve o último valor de cada indicador.

    Usado pelo motor de sinais (RF-04). Nunca levanta exceção por dados curtos:
    simplesmente devolve `None` para indicadores sem janela suficiente.
    """
    saida: dict[str, Num] = {"fechamento": fechamentos[-1] if fechamentos else None}
    if len(fechamentos) >= 5:
        saida["sma_5"] = ultimo(sma(fechamentos, 5))
    if len(fechamentos) >= 20:
        saida["sma_20"] = ultimo(sma(fechamentos, 20))
    if len(fechamentos) >= 50:
        saida["sma_50"] = ultimo(sma(fechamentos, 50))
    if len(fechamentos) >= 200:
        saida["sma_200"] = ultimo(sma(fechamentos, 200))
    if len(fechamentos) >= 9:
        saida["ema_9"] = ultimo(ema(fechamentos, 9))
    if len(fechamentos) >= 21:
        saida["ema_21"] = ultimo(ema(fechamentos, 21))
    if len(fechamentos) > 14:
        saida["rsi_14"] = ultimo(rsi(fechamentos, 14))
    if len(fechamentos) >= 35:
        linha, sinal, hist = macd(fechamentos)
        saida["macd"] = ultimo(linha)
        saida["macd_sinal"] = ultimo(sinal)
        saida["macd_hist"] = ultimo(hist)
    if len(fechamentos) >= 20:
        sup, med, inf = bollinger(fechamentos, 20, 2.0)
        saida["bb_superior"] = ultimo(sup)
        saida["bb_media"] = ultimo(med)
        saida["bb_inferior"] = ultimo(inf)
        if saida.get("bb_superior") is not None and saida.get("bb_inferior") is not None:
            largura = saida["bb_superior"] - saida["bb_inferior"]
            saida["bb_largura"] = largura
            if saida["bb_media"]:
                saida["bb_largura_pct"] = largura / saida["bb_media"] * 100.0
    if volumes and len(volumes) >= 20:
        saida["volume_relativo"] = ultimo(volume_relativo(volumes, 20))
    if len(fechamentos) >= 2:
        saida["variacao_pct"] = ultimo(variacao_pct(fechamentos, 1))
    return saida
