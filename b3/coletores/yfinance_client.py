"""Coletor B3 via yfinance (fallback da cascata - PRD secao 6).

Também usado para índices e, quando disponível, como fonte de referência
internacional (DXY/índices americanos) na estimativa de pré-abertura.
"""
from __future__ import annotations

from typing import Any, Optional

from comum.logger import get_logger

log = get_logger("b3.yfinance")

try:
    import yfinance as yf

    DISPONIVEL = True
except Exception as exc:  # pragma: no cover - depende do ambiente
    yf = None
    DISPONIVEL = False
    log.warning("yfinance indisponível: %s", exc)


def historico(simbolo_yf: str, periodo: str = "6mo", intervalo: str = "1d") -> list[dict[str, Any]]:
    """Retorna velas OHLCV normalizadas. Lista vazia em caso de falha."""
    if not DISPONIVEL:
        return []
    try:
        ticker = yf.Ticker(simbolo_yf)
        df = ticker.history(period=periodo, interval=intervalo, auto_adjust=False)
        if df is None or df.empty:
            return []
        velas: list[dict[str, Any]] = []
        for idx, linha in df.iterrows():
            try:
                ts = idx.to_pydatetime()
            except AttributeError:
                continue
            velas.append(
                {
                    "ts": ts,
                    "abertura": _f(linha.get("Open")),
                    "maxima": _f(linha.get("High")),
                    "minima": _f(linha.get("Low")),
                    "fechamento": _f(linha.get("Close")),
                    "volume": _f(linha.get("Volume")),
                }
            )
        return velas
    except Exception as exc:  # noqa: BLE001 - falha de fonte não pode propagar
        log.warning("yfinance falhou para %s: %s", simbolo_yf, exc)
        return []


def ultima_cotacao(simbolo_yf: str) -> Optional[dict[str, Any]]:
    velas = historico(simbolo_yf, periodo="5d", intervalo="1d")
    if not velas:
        return None
    ultima = velas[-1]
    anterior = velas[-2] if len(velas) > 1 else None
    variacao = None
    if anterior and anterior.get("fechamento"):
        variacao = (ultima["fechamento"] - anterior["fechamento"]) / anterior["fechamento"] * 100.0
    return {
        "preco": ultima["fechamento"],
        "abertura": ultima["abertura"],
        "maxima": ultima["maxima"],
        "minima": ultima["minima"],
        "volume": ultima["volume"],
        "variacao_pct": variacao,
    }


def _f(valor: Any) -> Optional[float]:
    try:
        if valor is None:
            return None
        f = float(valor)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None
