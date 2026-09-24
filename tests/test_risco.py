"""Testes do motor de risco (RF-09) - regras puras de bloqueio."""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from comum import db  # noqa: E402
from risco.regras_risco import avaliar_risco  # noqa: E402


def _sinal(tipo="compra", confianca=0.8, desatualizado=False):
    return {"tipo": tipo, "confianca": confianca, "dados_desatualizados": desatualizado}


def _ctx(**kwargs):
    base = {
        "agora": db.agora_utc(),
        "ultimo_alerta_ativo_em": None,
        "ultimo_alerta_ativo_tipo": None,
        "alertas_enviados_hoje_ativo": 0,
        "alertas_enviados_hoje_total": 0,
    }
    base.update(kwargs)
    return base


def test_sinal_valido_aprovado():
    resultado = avaliar_risco(_sinal(), _ctx())
    assert resultado.aprovado is True
    assert resultado.motivo == ""


def test_observacao_nao_gera_alerta():
    resultado = avaliar_risco(_sinal(tipo="observacao"), _ctx())
    assert resultado.aprovado is False
    assert "não alertável" in resultado.motivo


def test_confianca_baixa_bloqueia():
    resultado = avaliar_risco(_sinal(confianca=0.1), _ctx())
    assert resultado.aprovado is False
    assert "confiança" in resultado.motivo


def test_dados_desatualizados_bloqueiam():
    resultado = avaliar_risco(_sinal(desatualizado=True, confianca=0.9), _ctx())
    assert resultado.aprovado is False
    assert "desatualizado" in resultado.motivo


def test_anti_duplicidade_por_intervalo():
    agora = db.agora_utc()
    resultado = avaliar_risco(
        _sinal(),
        _ctx(
            agora=agora,
            ultimo_alerta_ativo_em=db.iso(agora - timedelta(seconds=60)),
            ultimo_alerta_ativo_tipo="compra",
        ),
    )
    assert resultado.aprovado is False
    assert "duplicado" in resultado.motivo


def test_duplicidade_fora_do_intervalo_permitida():
    agora = db.agora_utc()
    resultado = avaliar_risco(
        _sinal(),
        _ctx(
            agora=agora,
            ultimo_alerta_ativo_em=db.iso(agora - timedelta(seconds=99999)),
            ultimo_alerta_ativo_tipo="compra",
        ),
    )
    assert resultado.aprovado is True


def test_limite_diario_por_ativo():
    resultado = avaliar_risco(_sinal(), _ctx(alertas_enviados_hoje_ativo=99))
    assert resultado.aprovado is False
    assert "limite diário por ativo" in resultado.motivo


def test_limite_diario_global():
    resultado = avaliar_risco(_sinal(), _ctx(alertas_enviados_hoje_total=999))
    assert resultado.aprovado is False
    assert "global" in resultado.motivo


def test_regras_personalizadas():
    regras = {"confianca_minima": 0.95}
    resultado = avaliar_risco(_sinal(confianca=0.5), _ctx(), regras)
    assert resultado.aprovado is False
