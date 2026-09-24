"""Cliente cripto via ccxt (endpoints públicos, sem autenticação).

Toda a lógica de conexão/reconexão fica isolada aqui (secao 13). A cascata de
exchanges é resolvida no `main.py`, que nunca deixa exceções propagarem.
"""
from __future__ import annotations

from typing import Any, Optional

from comum.logger import get_logger

log = get_logger("cripto.ccxt")

try:
    import ccxt  # type: ignore

    DISPONIVEL = True
except Exception as exc:  # pragma: no cover
    ccxt = None
    DISPONIVEL = False
    log.warning("ccxt indisponível: %s", exc)


def criar_exchange(nome: str):
    """Cria uma instância de exchange com timeout agressivo e sem credenciais."""
    if not DISPONIVEL:
        raise RuntimeError("ccxt não instalado")
    if not hasattr(ccxt, nome):
        raise ValueError(f"exchange desconhecida: {nome}")
    exchange = getattr(ccxt, nome)(
        {
            "enableRateLimit": True,
            "timeout": 15000,
            "options": {"defaultType": "spot"},
        }
    )
    return exchange


def historico(nome: str, par: str, timeframe: str = "1h", limite: int = 300) -> list[list]:
    """Retorna OHLCV bruto [ts, open, high, low, close, volume]."""
    exchange = criar_exchange(nome)
    dados = exchange.fetch_ohlcv(par, timeframe=timeframe, limit=limite)
    return dados or []


def ticker(nome: str, par: str) -> dict[str, Any]:
    exchange = criar_exchange(nome)
    t = exchange.fetch_ticker(par)
    return {
        "preco": t.get("last"),
        "bid": t.get("bid"),
        "ask": t.get("ask"),
        "maxima": t.get("high"),
        "minima": t.get("low"),
        "volume": t.get("quoteVolume") or t.get("baseVolume"),
        "variacao_pct": t.get("percentage"),
    }


def orderbook(nome: str, par: str, limite: int = 20) -> dict[str, Any]:
    """Livro de ofertas - usado para estimar pressão compradora/vendedora (RF-05)."""
    exchange = criar_exchange(nome)
    ob = exchange.fetch_order_book(par, limit=limite)
    lances = ob.get("bids", [])
    vendas = ob.get("asks", [])
    vol_bid = sum(float(p) * float(v) for p, v in lances)
    vol_ask = sum(float(p) * float(v) for p, v in vendas)
    total = vol_bid + vol_ask
    desequilibrio = 0.0 if total == 0 else (vol_bid - vol_ask) / total
    return {
        "vol_bid": vol_bid,
        "vol_ask": vol_ask,
        "desequilibrio": desequilibrio,
    }


def trades_recentes(nome: str, par: str, limite: int = 50) -> list[dict[str, Any]]:
    exchange = criar_exchange(nome)
    trocas = exchange.fetch_trades(par, limit=limite)
    return [
        {"lado": t.get("side"), "preco": t.get("price"), "quantidade": t.get("amount")}
        for t in trocas or []
    ]
