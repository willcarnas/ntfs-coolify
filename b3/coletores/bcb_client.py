"""Coletor de macroeconomia brasileira via API SGS do Banco Central (gratuita).

Fonte oficial, sem autenticação. Séries usadas:
  432  - Meta Selic (% a.a.)
  11   - Selic diária (% a.d.)
  4389 - CDI (% a.d.)
  433  - IPCA mensal (%)
  1    - Dólar comercial venda (R$/US$)

Ref: https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados
"""
from __future__ import annotations

from typing import Any, Optional

import requests

from comum import config, db
from comum.logger import get_logger

log = get_logger("b3.bcb")

BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{n}"

SERIES = {
    432: "Selic_meta",
    11: "Selic_diaria",
    4389: "CDI",
    433: "IPCA",
    1: "Dolar_comercial",
}


def buscar_serie(codigo: int, ultimos: int = 5) -> list[dict[str, Any]]:
    """Retorna os últimos pontos da série SGS: [{'data','valor'}, ...]."""
    url = BASE.format(codigo=codigo, n=ultimos)
    try:
        resp = requests.get(
            url,
            params={"formato": "json"},
            headers={"Accept": "application/json"},
            timeout=config.HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        dados = resp.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("SGS %s falhou: %s", codigo, exc)
        return []
    if not isinstance(dados, list):
        log.warning("SGS %s retornou formato inesperado: %s", codigo, str(dados)[:120])
        return []
    pontos = []
    for item in dados:
        try:
            pontos.append(
                {
                    "data": item.get("data"),
                    "valor": float(str(item.get("valor", "")).replace(",", ".")),
                }
            )
        except (TypeError, ValueError):
            continue
    return pontos


def valores_atuais(codigos: list[int] | None = None) -> dict[str, float]:
    """Último valor de cada série, rotulado pelo nome."""
    resultado: dict[str, float] = {}
    for codigo in codigos or list(SERIES):
        pontos = buscar_serie(codigo, ultimos=1)
        if pontos:
            resultado[SERIES.get(codigo, str(codigo))] = pontos[-1]["valor"]
    return resultado


def registrar_no_banco(codigos: list[int] | None = None) -> int:
    """Persiste as séries em `cotacoes` (classe='macro') e retorna nº de séries."""
    total = 0
    for codigo in codigos or list(SERIES):
        nome = SERIES.get(codigo, str(codigo))
        pontos = buscar_serie(codigo, ultimos=1)
        if not pontos:
            continue
        db.execute(
            """
            INSERT INTO cotacoes (ativo, classe, preco, extra_json, fonte, coletado_em)
            VALUES (?, 'macro', ?, ?, ?, ?)
            """,
            (
                nome,
                pontos[-1]["valor"],
                '{"referencia":"' + str(pontos[-1]["data"]) + '"}',
                f"bcb_sgs:{codigo}",
                db.iso(),
            ),
        )
        total += 1
    return total


def dolar_ptax() -> Optional[float]:
    """Último dólar comercial (útil como entrada do pré-abertura)."""
    pontos = buscar_serie(1, ultimos=1)
    return pontos[-1]["valor"] if pontos else None
