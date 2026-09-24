"""Teste de isolamento (secao 5.3): a queda do módulo cripto não afeta a dashboard.

Verifica o princípio de isolamento: a dashboard lê apenas o banco e continua
respondendo (HTTP 200) mesmo quando o módulo cripto não publica dados recentes,
marcando o dado como desatualizado em vez de quebrar. É a versão automatizada e
reproduzível do teste manual de encerrar um processo de domínio.
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from comum import db, repo  # noqa: E402
from comum.contratos_dados import Cotacao  # noqa: E402
from dashboard.main import app  # noqa: E402


def _inserir_cotacao_com_idade(ativo: str, classe: str, idade_seg: int) -> None:
    ts = db.iso(db.agora_utc() - timedelta(seconds=idade_seg))
    repo.inserir_cotacao(
        Cotacao(ativo=ativo, classe=classe, preco=100.0, fonte="teste", coletado_em=ts)
    )


def test_dashboard_responde_com_cripto_desatualizado(db_limpo):
    # b3 recente; cripto "morto" há 2 horas.
    _inserir_cotacao_com_idade("PETR4", "b3", 10)
    _inserir_cotacao_com_idade("BTCUSDT", "cripto", 7200)
    repo.heartbeat("dashboard", "ok")

    client = TestClient(app)
    resp = client.get("/api/resumo")
    assert resp.status_code == 200
    dados = resp.json()

    por_ativo = {c["ativo"]: c for c in dados["cotacoes"]}
    assert por_ativo["PETR4"]["desatualizado"] is False
    assert por_ativo["BTCUSDT"]["desatualizado"] is True


def test_dashboard_responde_sem_servicos(db_limpo):
    client = TestClient(app)
    resp = client.get("/api/resumo")
    assert resp.status_code == 200
    assert resp.json()["cotacoes"] == []


def test_dashboard_index_carrega(db_limpo):
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Painel de Trading" in resp.text


def test_registrar_e_fechar_operacao_via_api(db_limpo):
    client = TestClient(app)
    resp = client.post("/api/operacoes", json={"ativo": "petr4", "preco_entrada": 10.0, "quantidade": 10})
    assert resp.status_code == 200
    op_id = resp.json()["id"]
    resp2 = client.post(f"/api/operacoes/{op_id}/fechar", json={"preco_saida": 12.0})
    assert resp2.status_code == 200
    assert resp2.json()["operacao"]["resultado"] == 20.0
