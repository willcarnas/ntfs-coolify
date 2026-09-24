"""Feed simulado de forex (somente quando MT5 não está disponível).

Marcado explicitamente com fonte `simulado` para nunca ser confundido com dado
real (secao 6 - transparência da fonte). Permite validar o pipeline completo
(dashboard, sinais, alertas) antes da conexão com o terminal MT5, no espírito
da ativação gradual prevista na Fase 0 do PRD.
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone
from random import Random
from typing import Any

BASES = {
    "EURUSD": 1.0850,
    "GBPUSD": 1.2700,
    "USDJPY": 149.50,
    "USDBRL": 5.4200,
    "AUDUSD": 0.6600,
    "USDCAD": 1.3600,
    "XAUUSD": 2350.0,
    "WTIUSD": 78.50,
    "USDX": 104.20,
    "US500": 5450.0,
    "USTEC": 19800.0,
    "DE40": 18400.0,
    "XPTUSD": 980.0,
}


def _rng(simbolo: str) -> Random:
    return Random(f"seed:{simbolo}:{int(time.time() // 3600)}")


def preco_atual(simbolo: str) -> float:
    base = BASES.get(simbolo, 100.0)
    r = _rng(simbolo)
    onda = math.sin(time.time() / 900.0 + hash(simbolo) % 7) * 0.004
    ruido = (r.random() - 0.5) * 0.002
    return round(base * (1.0 + onda + ruido), 4 if base < 10 else 2)


def ticker(simbolo: str) -> dict[str, Any]:
    preco = preco_atual(simbolo)
    spread = preco * 0.0002
    variacao = math.sin(time.time() / 1800.0) * 0.8
    return {
        "preco": preco,
        "bid": round(preco - spread, 5),
        "ask": round(preco + spread, 5),
        "variacao_pct": round(variacao, 3),
    }


def velas(simbolo: str, timeframe: str = "1h", limite: int = 300) -> list[dict[str, Any]]:
    """Gera uma série OHLCV determinística por hora (random walk ancorado)."""
    base = BASES.get(simbolo, 100.0)
    agora = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    r = Random(f"hist:{simbolo}")
    fechamento = base * 0.98
    velas: list[dict[str, Any]] = []
    inicio = agora - timedelta(hours=limite - 1)
    for i in range(limite):
        ts = inicio + timedelta(hours=i)
        abertura = fechamento
        drift = r.gauss(0, base * 0.004)
        fechamento = max(base * 0.5, abertura + drift)
        maxima = max(abertura, fechamento) + abs(r.gauss(0, base * 0.002))
        minima = min(abertura, fechamento) - abs(r.gauss(0, base * 0.002))
        velas.append(
            {
                "ts": ts,
                "abertura": round(abertura, 4 if base < 10 else 2),
                "maxima": round(maxima, 4 if base < 10 else 2),
                "minima": round(minima, 4 if base < 10 else 2),
                "fechamento": round(fechamento, 4 if base < 10 else 2),
                "volume": round(abs(r.gauss(1000, 200)), 0),
            }
        )
    return velas
