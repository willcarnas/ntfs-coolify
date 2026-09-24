"""Testes dos indicadores técnicos (RF-04) - funções puras."""
from __future__ import annotations

import math

from comum import indicadores as ind


def test_sma_alinhamento_e_valores():
    saida = ind.sma([1, 2, 3, 4, 5], 3)
    assert saida[:2] == [None, None]
    assert saida[2:] == [2.0, 3.0, 4.0]


def test_sma_janela_maior_que_serie():
    assert ind.sma([1, 2], 5) == [None, None]


def test_ema_seed_e_valor_conhecido():
    valores = [1, 2, 3, 4, 5, 6]
    saida = ind.ema(valores, 3)
    assert saida[1] is None
    assert saida[2] == 2.0  # seed = SMA(1,2,3)
    # k = 2/(3+1) = 0.5 -> proximo = 4*0.5 + 2*0.5 = 3
    assert saida[3] == 3.0


def test_rsi_serie_crescente_aproxima_100():
    valores = list(range(1, 30))
    saida = ind.rsi(valores, 14)
    assert ind.ultimo(saida) is not None
    assert ind.ultimo(saida) > 99.0


def test_rsi_serie_decrescente_aproxima_0():
    valores = list(range(30, 1, -1))
    rsi = ind.ultimo(ind.rsi(valores, 14))
    assert rsi is not None and rsi < 1.0


def test_rsi_periodo_insuficiente():
    assert ind.rsi([1, 2, 3], 14) == [None, None, None]


def test_bollinger_serie_constante():
    sup, med, inf = ind.bollinger([10.0] * 25, 20, 2.0)
    assert ind.ultimo(sup) == 10.0
    assert ind.ultimo(med) == 10.0
    assert ind.ultimo(inf) == 10.0


def test_bollinger_simetria():
    valores = [float(i) for i in range(1, 30)]
    sup, med, inf = ind.bollinger(valores, 20, 2.0)
    s, m, i = ind.ultimo(sup), ind.ultimo(med), ind.ultimo(inf)
    assert math.isclose(m - i, s - m, rel_tol=1e-9)


def test_macd_histograma_consistente():
    valores = [float(10 + i * 0.5) for i in range(60)]
    linha, sinal, hist = ind.macd(valores)
    assert ind.ultimo(linha) is not None
    assert ind.ultimo(sinal) is not None
    assert math.isclose(
        ind.ultimo(hist), ind.ultimo(linha) - ind.ultimo(sinal), rel_tol=1e-9
    )


def test_volume_relativo():
    volumes = [100.0] * 19 + [200.0]
    vr = ind.volume_relativo(volumes, 20)
    # média inclui o próprio volume atual: 200 / ((19*100 + 200)/20) = 200/105
    assert math.isclose(ind.ultimo(vr), 200.0 / 105.0, rel_tol=1e-9)


def test_calcular_indicadores_completo():
    fechamentos = [float(100 + (i % 5) + i * 0.3) for i in range(200)]
    volumes = [1000.0 + i for i in range(200)]
    resultado = ind.calcular_indicadores(fechamentos, volumes)
    for chave in ("sma_20", "rsi_14", "macd", "bb_superior", "volume_relativo"):
        assert resultado.get(chave) is not None, chave


def test_calcular_indicadores_dados_curtos_nao_quebra():
    resultado = ind.calcular_indicadores([1.0, 2.0])
    assert resultado["fechamento"] == 2.0
    assert "sma_20" not in resultado
