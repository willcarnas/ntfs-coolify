"""Testes da estimativa de pré-abertura (RF-06) e do sentimento (RF-07)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from noticias.sentiment import classificar, pontuar  # noqa: E402
from sinais.pre_abertura import estimar  # noqa: E402


def test_pre_abertura_completo_confianca_total():
    est = estimar(
        ativo="IBOV",
        preco_referencia=130000.0,
        variacoes={"US500": 1.0, "USTEC": 1.0},
        pesos={"US500": 0.5, "USTEC": 0.5},
    )
    assert est.confianca == 1.0
    assert est.faltantes == []
    assert est.valor_estimado == round(130000.0 * 1.01, 4)


def test_pre_abertura_fonte_faltante_reduz_confianca_sem_quebrar():
    est = estimar(
        ativo="IBOV",
        preco_referencia=130000.0,
        variacoes={"US500": 1.0, "USDX": None},
        pesos={"US500": 0.5, "USDX": -0.5},
    )
    assert est.confianca == 0.5
    assert "USDX" in est.faltantes
    assert est.valor_estimado is not None  # calcula com o que há


def test_pre_abertura_sem_entradas_nao_estima():
    est = estimar(
        ativo="IBOV",
        preco_referencia=100.0,
        variacoes={"US500": None},
        pesos={"US500": 1.0},
    )
    assert est.valor_estimado is None
    assert est.confianca == 0.0
    assert est.faltantes == ["US500"]


def test_pre_abertura_correlacao_inversa():
    est = estimar(
        ativo="USDBRL",
        preco_referencia=5.0,
        variacoes={"USDX": 2.0},
        pesos={"USDX": 1.0},
    )
    assert est.valor_estimado == round(5.0 * 1.02, 4)


def test_sentimento_positivo():
    rotulo, score = classificar("Ações sobem com lucro recorde e otimismo no mercado")
    assert rotulo == "positivo"
    assert score > 0


def test_sentimento_negativo():
    rotulo, score = classificar("Bolsa despenca com crise e pânico entre investidores")
    assert rotulo == "negativo"
    assert score < 0


def test_sentimento_neutro():
    rotulo, _ = classificar("Empresa anuncia reunião do conselho na próxima semana")
    assert rotulo == "neutro"


def test_pontuar_sem_palavras_chave():
    assert pontuar("texto completamente neutro sem termos de mercado") == 0.0
