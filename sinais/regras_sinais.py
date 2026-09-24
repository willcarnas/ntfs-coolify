"""Regras puras do motor de sinais (RF-08).

Cada regra é uma função pura e isolada (entrada -> saída determinística),
conforme exigido na secao 13. Nenhuma regra acessa banco, rede ou relógio.
O resultado combinado é explicável: todo fator carrega valor, peso e descrição.
"""
from __future__ import annotations

from typing import Any, Optional

from comum.contratos_dados import FatorSinal, Sinal

# Pesos somam 1.0 quando todos os fatores estão disponíveis.
PESOS = {
    "tendencia_medias": 0.25,
    "rsi": 0.15,
    "macd": 0.20,
    "bollinger": 0.10,
    "volume": 0.05,
    "fluxo": 0.10,
    "noticias": 0.10,
    "pre_abertura": 0.05,
}

LIMIAR_ACAO = 0.25


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def fator_tendencia_medias(ind: dict[str, Any]) -> Optional[FatorSinal]:
    preco = ind.get("fechamento")
    sma20 = ind.get("sma_20")
    sma50 = ind.get("sma_50")
    if preco is None or sma20 is None:
        return None
    direcao = 0.0
    detalhe = []
    if sma50 is not None:
        if sma20 > sma50:
            direcao += 0.5
            detalhe.append("SMA20>SMA50")
        elif sma20 < sma50:
            direcao -= 0.5
            detalhe.append("SMA20<SMA50")
    if preco > sma20:
        direcao += 0.5
        detalhe.append("preço>SMA20")
    elif preco < sma20:
        direcao -= 0.5
        detalhe.append("preço<SMA20")
    return FatorSinal(
        nome="tendencia_medias", valor=round(direcao, 2), peso=PESOS["tendencia_medias"],
        contribuicao=round(direcao, 2), descricao="Tendência por médias móveis (" + ", ".join(detalhe) + ")",
    )


def fator_rsi(ind: dict[str, Any]) -> Optional[FatorSinal]:
    rsi = ind.get("rsi_14")
    if rsi is None:
        return None
    if rsi <= 30:
        contrib = _clamp((30 - rsi) / 30)
    elif rsi >= 70:
        contrib = -_clamp((rsi - 70) / 30)
    else:
        contrib = 0.0
    return FatorSinal(
        nome="rsi", valor=round(rsi, 2), peso=PESOS["rsi"], contribuicao=round(contrib, 2),
        descricao=f"RSI(14)={rsi:.1f}",
    )


def fator_macd(ind: dict[str, Any]) -> Optional[FatorSinal]:
    hist = ind.get("macd_hist")
    macd = ind.get("macd")
    sinal = ind.get("macd_sinal")
    if hist is None:
        return None
    preco = ind.get("fechamento") or 1.0
    escala = abs(preco) * 0.01 or 1.0
    contrib = _clamp(hist / escala)
    return FatorSinal(
        nome="macd", valor=round(hist, 4), peso=PESOS["macd"], contribuicao=round(contrib, 2),
        descricao=f"MACD hist={hist:.4f} (linha={macd}, sinal={sinal})",
    )


def fator_bollinger(ind: dict[str, Any]) -> Optional[FatorSinal]:
    preco = ind.get("fechamento")
    sup = ind.get("bb_superior")
    inf = ind.get("bb_inferior")
    med = ind.get("bb_media")
    if None in (preco, sup, inf, med) or sup == inf:
        return None
    if preco <= inf:
        contrib = 1.0
        desc = "preço na banda inferior (sobrevenda)"
    elif preco >= sup:
        contrib = -1.0
        desc = "preço na banda superior (sobrecompra)"
    else:
        pos = (preco - med) / (sup - med) if sup != med else 0.0
        contrib = _clamp(-pos)
        desc = "preço dentro das bandas"
    return FatorSinal(
        nome="bollinger", valor=round(contrib, 2), peso=PESOS["bollinger"],
        contribuicao=round(contrib, 2), descricao=f"Bollinger: {desc}",
    )


def fator_volume(ind: dict[str, Any]) -> Optional[FatorSinal]:
    vol_rel = ind.get("volume_relativo")
    var = ind.get("variacao_pct")
    if vol_rel is None or var is None:
        return None
    intensidade = _clamp((vol_rel - 1.0), -1.0, 1.0)
    direcao = 1.0 if var > 0 else (-1.0 if var < 0 else 0.0)
    contrib = _clamp(intensidade * direcao)
    return FatorSinal(
        nome="volume", valor=round(vol_rel, 2), peso=PESOS["volume"], contribuicao=round(contrib, 2),
        descricao=f"Volume relativo={vol_rel:.2f}x",
    )


def fator_fluxo(ind: dict[str, Any]) -> Optional[FatorSinal]:
    deseq = ind.get("fluxo_desequilibrio")
    if deseq is None:
        return None
    contrib = _clamp(float(deseq))
    return FatorSinal(
        nome="fluxo", valor=round(contrib, 3), peso=PESOS["fluxo"], contribuicao=round(contrib, 3),
        descricao=f"Desequilíbrio do livro (bids-asks)={contrib:.2f}",
    )


def fator_noticias(humor_score: Optional[float]) -> Optional[FatorSinal]:
    if humor_score is None:
        return None
    contrib = _clamp(float(humor_score))
    return FatorSinal(
        nome="noticias", valor=round(contrib, 3), peso=PESOS["noticias"], contribuicao=round(contrib, 3),
        descricao=f"Humor de notícias={contrib:+.2f}",
    )


def fator_pre_abertura(preco: Optional[float], estimado: Optional[float]) -> Optional[FatorSinal]:
    if preco is None or estimado is None or preco == 0:
        return None
    gap_pct = (estimado - preco) / preco
    contrib = _clamp(gap_pct * 20.0)  # 5% de gap -> saturação
    return FatorSinal(
        nome="pre_abertura", valor=round(gap_pct * 100, 3), peso=PESOS["pre_abertura"],
        contribuicao=round(contrib, 2),
        descricao=f"Gap pré-abertura esperado={gap_pct*100:+.2f}%",
    )


def gerar_sinal(
    ativo: str,
    classe: str,
    preco: Optional[float],
    indicadores: dict[str, Any],
    humor_score: Optional[float] = None,
    estimativa_pre_abertura: Optional[float] = None,
    dados_desatualizados: bool = False,
    criado_em: Optional[str] = None,
) -> Sinal:
    """Combina os fatores disponíveis em um sinal explicável (RF-08)."""
    candidatos = [
        fator_tendencia_medias(indicadores),
        fator_rsi(indicadores),
        fator_macd(indicadores),
        fator_bollinger(indicadores),
        fator_volume(indicadores),
        fator_fluxo(indicadores),
        fator_noticias(humor_score),
        fator_pre_abertura(preco, estimativa_pre_abertura),
    ]
    fatores = [f for f in candidatos if f is not None]

    # Score ponderado: trata pesos disponíveis como 100% e mede a cobertura.
    peso_disponivel = sum(f.peso for f in fatores)
    soma = sum(f.peso * f.contribuicao for f in fatores)
    score = soma / peso_disponivel if peso_disponivel else 0.0
    cobertura = peso_disponivel  # já que a soma total é 1.0 quando completo

    confianca = min(1.0, abs(score))
    confianca *= 0.5 + 0.5 * min(1.0, cobertura)  # poucos dados -> menos confiança
    if dados_desatualizados:
        confianca *= 0.6
    confianca = round(confianca, 3)

    if score >= LIMIAR_ACAO:
        tipo = "compra"
    elif score <= -LIMIAR_ACAO:
        tipo = "venda"
    else:
        tipo = "observacao"

    justificativa = _montar_justificativa(tipo, score, fatores, dados_desatualizados)
    fontes = ["indicadores(db)"]
    if humor_score is not None:
        fontes.append("noticias(db)")
    if estimativa_pre_abertura is not None:
        fontes.append("pre_abertura(db)")

    sinal = Sinal(
        ativo=ativo, classe=classe, tipo=tipo, confianca=confianca, preco=preco,
        justificativa=justificativa, fatores=fatores, fontes=fontes,
        dados_desatualizados=dados_desatualizados,
    )
    if criado_em:
        sinal.criado_em = criado_em
    return sinal


def _montar_justificativa(tipo: str, score: float, fatores: list[FatorSinal], desatualizado: bool) -> str:
    cabecalho = f"Recomendação: {tipo.upper()} (score={score:+.2f})"
    linhas = [cabecalho]
    for f in sorted(fatores, key=lambda x: abs(x.contribuicao * x.peso), reverse=True):
        linhas.append(f"• {f.descricao} [peso {f.peso:.2f}, contrib {f.contribuicao:+.2f}]")
    if desatualizado:
        linhas.append("⚠ Dados desatualizados: confiança reduzida.")
    return "\n".join(linhas)
