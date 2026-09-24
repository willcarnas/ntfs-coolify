"""Adaptador opcional para a biblioteca `mercados` (dados oficiais B3/CVM/BCB).

A API pública da `mercados` varia entre versões. Este adaptador tenta importar
e usar as funções conhecidas; se indisponível ou se a assinatura mudar, retorna
vazio sem quebrar a cascata (a fonte é considerada "indisponível").
"""
from __future__ import annotations

from typing import Any

from comum.logger import get_logger

log = get_logger("b3.mercados")

try:
    import mercados  # type: ignore

    DISPONIVEL = True
except Exception as exc:  # pragma: no cover - depende do ambiente
    mercados = None
    DISPONIVEL = False
    log.info("biblioteca `mercados` indisponível (%s) - usando fallback brapi/yfinance", exc)


def cotacao_historica(simbolo: str) -> list[dict[str, Any]]:
    """Tenta obter histórico oficial; lista vazia se indisponível."""
    if not DISPONIVEL:
        return []
    for nome_funcao in ("cotacao_historica", "historico", "cotacoes"):
        func = getattr(mercados, nome_funcao, None)
        if func is None:
            continue
        try:
            dados = func(simbolo)
            return list(dados) if dados else []
        except Exception as exc:  # noqa: BLE001
            log.warning("mercados.%s falhou para %s: %s", nome_funcao, simbolo, exc)
    return []
