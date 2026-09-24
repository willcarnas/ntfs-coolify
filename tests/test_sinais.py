"""Testes do motor de sinais (RF-08) - regras puras e explicáveis."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sinais.regras_sinais import gerar_sinal  # noqa: E402


def _ind_tendencia_alta() -> dict:
    return {
        "fechamento": 30.0, "sma_5": 29.0, "sma_20": 27.0, "sma_50": 25.0,
        "ema_9": 29.5, "ema_21": 28.0, "rsi_14": 62.0,
        "macd": 1.2, "macd_sinal": 0.8, "macd_hist": 0.4,
        "bb_superior": 31.0, "bb_media": 28.0, "bb_inferior": 25.0,
        "volume_relativo": 1.8, "variacao_pct": 2.0,
    }


def test_tendencia_de_alta_gera_compra():
    sinal = gerar_sinal("PETR4", "b3", 30.0, _ind_tendencia_alta(), humor_score=0.5)
    assert sinal.tipo == "compra"
    assert sinal.confianca > 0
    assert "compra" in sinal.justificativa.lower()


def test_tendencia_de_baixa_gera_venda():
    ind = {
        "fechamento": 20.0, "sma_5": 21.0, "sma_20": 23.0, "sma_50": 26.0,
        "ema_9": 20.5, "ema_21": 22.0, "rsi_14": 35.0,
        "macd": -1.0, "macd_sinal": -0.5, "macd_hist": -0.5,
        "bb_superior": 26.0, "bb_media": 23.0, "bb_inferior": 20.0,
        "volume_relativo": 1.5, "variacao_pct": -2.0,
    }
    sinal = gerar_sinal("VALE3", "b3", 20.0, ind, humor_score=-0.5)
    assert sinal.tipo == "venda"


def test_mercado_lateral_gera_observacao():
    ind = {
        "fechamento": 100.0, "sma_20": 100.0, "sma_50": 100.0,
        "rsi_14": 50.0, "macd_hist": 0.0, "bb_superior": 105.0, "bb_media": 100.0,
        "bb_inferior": 95.0,
    }
    sinal = gerar_sinal("ITUB4", "b3", 100.0, ind, humor_score=0.0)
    assert sinal.tipo == "observacao"


def test_sinal_lista_fatores_e_fontes():
    sinal = gerar_sinal("PETR4", "b3", 30.0, _ind_tendencia_alta(), humor_score=0.5)
    nomes = {f.nome for f in sinal.fatores}
    assert "tendencia_medias" in nomes
    assert "rsi" in nomes
    assert sinal.fontes


def test_dados_desatualizados_reduzem_confianca():
    ind = _ind_tendencia_alta()
    atual = gerar_sinal("PETR4", "b3", 30.0, ind, humor_score=0.5, dados_desatualizados=False)
    velho = gerar_sinal("PETR4", "b3", 30.0, ind, humor_score=0.5, dados_desatualizados=True)
    assert velho.confianca < atual.confianca
    assert velho.dados_desatualizados is True
    assert "desatualizado" in velho.justificativa.lower()


def test_poucos_dados_nao_quebra_e_reduz_confianca():
    sinal = gerar_sinal("X", "cripto", 100.0, {"fechamento": 100.0, "rsi_14": 25.0})
    assert sinal.tipo in ("compra", "venda", "observacao")
    assert sinal.confianca <= 0.35  # cobertura baixa limita a confiança


def test_determinismo():
    a = gerar_sinal("PETR4", "b3", 30.0, _ind_tendencia_alta(), humor_score=0.5)
    b = gerar_sinal("PETR4", "b3", 30.0, _ind_tendencia_alta(), humor_score=0.5)
    assert a.tipo == b.tipo and a.confianca == b.confianca
