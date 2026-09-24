"""Estimativa de preço justo de pré-abertura (RF-06).

Cada entrada (DXY, futuro de índice, câmbio) é opcional e tem peso explícito.
A ausência de uma fonte apenas reduz a confiança — nunca quebra o cálculo nem é
preenchida silenciosamente com dado desatualizado (secao 13).
"""
from __future__ import annotations

from typing import Any, Optional

from comum.contratos_dados import EntradaPreAbertura, EstimativaPreAbertura


def estimar(
    ativo: str,
    preco_referencia: Optional[float],
    variacoes: dict[str, Optional[float]],
    pesos: dict[str, float],
    fontes: Optional[dict[str, str]] = None,
) -> EstimativaPreAbertura:
    """Estima a abertura de `ativo` a partir das variações (%) das referências.

    `variacoes`: nome da referência -> variação percentual (None se indisponível)
    `pesos`:     nome da referência -> peso (pode ser negativo p/ correlação inversa)
    """
    fontes = fontes or {}
    entradas: list[EntradaPreAbertura] = []
    faltantes: list[str] = []
    soma_peso_disp = 0.0
    soma_contrib = 0.0

    for nome, peso in pesos.items():
        variacao = variacoes.get(nome)
        disponivel = variacao is not None
        entradas.append(
            EntradaPreAbertura(
                nome=nome,
                valor=None if variacao is None else round(float(variacao), 4),
                fonte=fontes.get(nome, "desconhecida"),
                peso=peso,
                disponivel=disponivel,
            )
        )
        if disponivel:
            soma_peso_disp += abs(peso)
            soma_contrib += peso * float(variacao)
        else:
            faltantes.append(nome)

    peso_total = sum(abs(p) for p in pesos.values()) or 1.0
    confianca = round(soma_peso_disp / peso_total, 3)

    valor_estimado = None
    if preco_referencia is not None and soma_peso_disp > 0:
        # Variação esperada = soma ponderada / soma dos pesos disponíveis.
        variacao_esperada = soma_contrib / soma_peso_disp
        valor_estimado = round(preco_referencia * (1.0 + variacao_esperada / 100.0), 4)

    return EstimativaPreAbertura(
        ativo=ativo,
        valor_estimado=valor_estimado,
        confianca=confianca,
        entradas=entradas,
        faltantes=faltantes,
        fonte="composicao:" + ",".join(f"{k}={pesos[k]}" for k in pesos),
    )
