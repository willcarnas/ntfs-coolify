"""Coletor B3 via brapi.dev (fonte primária de acompanhamento de sessão).

Endpoint público; pode exigir token (`BRAPI_TOKEN`) em planos com mais ativos.
Retorna sempre `None`/lista vazia em falha, para que a cascata siga adiante.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import requests

from comum import config
from comum.logger import get_logger

log = get_logger("b3.brapi")

BASE = "https://brapi.dev/api"


def _params(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    token = os.getenv("BRAPI_TOKEN", "").strip()
    if token:
        params["token"] = token
    if extra:
        params.update(extra)
    return params


def cotacoes(simbolos: list[str]) -> dict[str, dict[str, Any]]:
    """Cotações atuais para vários tickers de uma vez."""
    if not simbolos:
        return {}
    url = f"{BASE}/quote/{','.join(simbolos)}"
    try:
        resp = requests.get(url, params=_params(), timeout=config.HTTP_TIMEOUT)
        resp.raise_for_status()
        dados = resp.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("brapi falhou (%s): %s", simbolos, exc)
        return {}

    resultado: dict[str, dict[str, Any]] = {}
    for item in dados.get("results", []):
        simbolo = item.get("symbol")
        if not simbolo:
            continue
        resultado[simbolo] = {
            "preco": item.get("regularMarketPrice"),
            "abertura": item.get("regularMarketOpen"),
            "maxima": item.get("regularMarketDayHigh"),
            "minima": item.get("regularMarketDayLow"),
            "volume": item.get("regularMarketVolume"),
            "variacao_pct": item.get("regularMarketChangePercent"),
            "extra": {
                "nome": item.get("shortName"),
                "hora_mercado": item.get("regularMarketTime"),
            },
        }
    return resultado


def historico(simbolo: str, range_: str = "3mo", interval: str = "1d") -> list[dict[str, Any]]:
    """Histórico diário de um ticker."""
    url = f"{BASE}/quote/{simbolo}"
    try:
        resp = requests.get(
            url,
            params=_params({"range": range_, "interval": interval}),
            timeout=config.HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        dados = resp.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("brapi histórico falhou (%s): %s", simbolo, exc)
        return []

    item = (dados.get("results") or [{}])[0]
    velas: list[dict[str, Any]] = []
    for ponto in item.get("historicalDataPrice", []) or []:
        ts = ponto.get("date")
        velas.append(
            {
                "ts_epoch": ts,
                "abertura": ponto.get("open"),
                "maxima": ponto.get("high"),
                "minima": ponto.get("low"),
                "fechamento": ponto.get("close"),
                "volume": ponto.get("volume"),
            }
        )
    return velas


def ultima_cotacao(simbolo: str) -> Optional[dict[str, Any]]:
    return cotacoes([simbolo]).get(simbolo)
