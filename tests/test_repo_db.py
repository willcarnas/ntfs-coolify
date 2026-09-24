"""Testes da camada de dados compartilhada (repo/db)."""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from comum import db, repo  # noqa: E402
from comum.contratos_dados import Cotacao, Noticia, Sinal, Vela  # noqa: E402


def test_cotacao_mais_recente(db_limpo):
    repo.inserir_cotacao(Cotacao(ativo="PETR4", classe="b3", preco=10.0, fonte="yfinance"))
    repo.inserir_cotacao(Cotacao(ativo="PETR4", classe="b3", preco=11.0, fonte="yfinance"))
    recentes = repo.cotacoes_mais_recentes()
    petr = [c for c in recentes if c["ativo"] == "PETR4"]
    assert len(petr) == 1
    assert petr[0]["preco"] == 11.0


def test_velas_upsert_idempotente(db_limpo):
    v = Vela(ativo="BTCUSDT", classe="cripto", timeframe="1h", ts="2026-01-01T00:00:00Z",
             abertura=1, maxima=2, minima=0.5, fechamento=1.5, volume=100, fonte="ccxt:binance")
    repo.inserir_velas([v, v])
    assert len(repo.obter_velas("BTCUSDT", "1h", 10)) == 1
    v.fechamento = 2.0
    repo.inserir_velas([v])
    velas = repo.obter_velas("BTCUSDT", "1h", 10)
    assert len(velas) == 1 and velas[0]["fechamento"] == 2.0


def test_noticia_deduplicada(db_limpo):
    n = Noticia(titulo="Mercado sobe", fonte="rss", link="http://x/1")
    assert repo.inserir_noticia(n) is True
    assert repo.inserir_noticia(Noticia(titulo="Mercado sobe", fonte="rss", link="http://x/1")) is False


def test_operacao_resultado_compra(db_limpo):
    op_id = repo.registrar_operacao("PETR4", preco_entrada=10.0, quantidade=100)
    op = repo.fechar_operacao(op_id, 12.0)
    assert op["resultado"] == 200.0
    assert op["resultado_pct"] == 20.0
    assert op["status"] == "fechada"


def test_operacao_resultado_venda(db_limpo):
    op_id = repo.registrar_operacao("VALE3", preco_entrada=100.0, quantidade=10, lado="venda")
    op = repo.fechar_operacao(op_id, 90.0)
    assert op["resultado"] == 100.0


def test_resumo_operacoes(db_limpo):
    a = repo.registrar_operacao("A", 10.0)
    repo.fechar_operacao(a, 11.0)
    b = repo.registrar_operacao("B", 10.0)
    repo.fechar_operacao(b, 9.0)
    r = repo.resumo_operacoes()
    assert r["total"] == 2
    assert r["fechadas"] == 2
    assert r["resultado"] == 0.0
    assert r["taxa_acerto"] == 50.0


def test_sinal_duplicado_ignorado(db_limpo):
    s = Sinal(ativo="PETR4", classe="b3", tipo="compra", confianca=0.5, preco=10.0,
              justificativa="teste", criado_em="2026-01-01T00:00:00Z")
    id1 = repo.inserir_sinal(s)
    id2 = repo.inserir_sinal(Sinal(ativo="PETR4", classe="b3", tipo="compra", confianca=0.5,
                                   preco=10.0, justificativa="teste", criado_em="2026-01-01T00:00:00Z"))
    assert id1 is not None
    assert id2 == id1
    assert len(repo.listar_sinais()) == 1


def test_fila_alertas_e_contadores(db_limpo):
    s = Sinal(ativo="PETR4", classe="b3", tipo="compra", confianca=0.5, preco=10.0,
              justificativa="t", criado_em=db.iso())
    sid = repo.inserir_sinal(s)
    alerta = repo.enfileirar_alerta(sid, {"tipo": "compra", "ativo": "PETR4"})
    assert repo.alertas_pendentes()
    repo.marcar_alerta(alerta, "enviado")
    assert repo.alertas_enviados_hoje("PETR4") == 1
    assert repo.ultimo_alerta_enviado("PETR4")["tipo"] == "compra"


def test_heartbeat_servico(db_limpo):
    repo.heartbeat("b3", "ok", "rodando")
    servicos = repo.listar_servicos()
    assert servicos[0]["servico"] == "b3"
    assert servicos[0]["status"] == "ok"


def test_humor_mercado(db_limpo):
    for rotulo, score in (("positivo", 0.8), ("positivo", 0.5), ("negativo", -0.7)):
        repo.inserir_noticia(Noticia(titulo=f"n{rotulo}{score}", fonte="rss",
                                     sentimento=rotulo, score=score))
    humor = repo.humor_mercado()
    assert humor["rotulo"] == "positivo"
    assert humor["score"] > 0


def test_idade_segundos(db_limpo):
    antigo = db.iso(db.agora_utc() - timedelta(seconds=120))
    assert db.idade_segundos(antigo) >= 119
