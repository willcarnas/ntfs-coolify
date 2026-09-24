"""Dashboard web local (RF-11) — somente leitura do banco compartilhado.

Backend leve (FastAPI + Uvicorn). Nunca chama as APIs externas dos módulos de
coleta: lê exclusivamente do SQLite e sinaliza quando um dado está desatualizado
ou um serviço está fora do ar, sem quebrar a interface (secao 5.3).
A única escrita permitida é o registro manual de operações (RF-12).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from comum import config, db, repo  # noqa: E402
from comum.logger import get_logger  # noqa: E402

log = get_logger("dashboard")
app = FastAPI(title="TradingSystemWCN - Dashboard", version="1.0")

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Limites de staleness por serviço (segundos): acima disso, "desatualizado".
# Sobrescrevíveis por `dashboard.json` (chave "limites_stale") ou por variáveis
# de ambiente `TRADING_STALE_<SERVICO>` (usado nos testes de isolamento).
import os  # noqa: E402

LIMITES_STALE = {
    "b3": 900,
    "forex": 300,
    "cripto": 300,
    "noticias": 900,
    "sinais": 600,
    "risco": 300,
    "telegram": 120,
    "dashboard": 1_000_000,
    "monitor_saude": 300,
}

_CFG_PRE = config.load_json("dashboard.json", {})
LIMITES_STALE.update(_CFG_PRE.get("limites_stale", {}))
for _servico in list(LIMITES_STALE):
    _env = os.getenv(f"TRADING_STALE_{_servico.upper()}")
    if _env:
        LIMITES_STALE[_servico] = float(_env)
IDADE_MAX_COTACAO = float(os.getenv("TRADING_STALE_COTACAO", _CFG_PRE.get("idade_max_cotacao", 600)))


def _json_load(texto: Optional[str], default: Any = None) -> Any:
    if not texto:
        return default if default is not None else []
    try:
        return json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else []


def _servicos_com_estado() -> list[dict[str, Any]]:
    servicos = repo.listar_servicos()
    for s in servicos:
        limite = LIMITES_STALE.get(s["servico"], 600)
        idade = s.get("idade_segundos") or 0
        s["limite_stale"] = limite
        s["desatualizado"] = idade > limite
    return servicos


def _cotacao_view(row: dict[str, Any]) -> dict[str, Any]:
    idade = row.get("idade_segundos") or 0
    return {
        "ativo": row["ativo"],
        "classe": row["classe"],
        "preco": row.get("preco"),
        "variacao_pct": row.get("variacao_pct"),
        "abertura": row.get("abertura"),
        "maxima": row.get("maxima"),
        "minima": row.get("minima"),
        "volume": row.get("volume"),
        "fonte": row.get("fonte"),
        "coletado_em": row.get("coletado_em"),
        "idade_segundos": round(idade, 1),
        "desatualizado": idade > IDADE_MAX_COTACAO,
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/resumo")
def resumo() -> dict[str, Any]:
    cotacoes = [_cotacao_view(c) for c in repo.cotacoes_mais_recentes()]
    indicadores: dict[str, Any] = {}
    for c in cotacoes:
        ind = repo.obter_indicadores(c["ativo"])
        if ind:
            indicadores[c["ativo"]] = {
                k: (round(v, 4) if isinstance(v, (int, float)) else v) for k, v in ind.items()
            }

    sinais = []
    for s in repo.listar_sinais(limite=25):
        sinais.append(
            {
                "id": s["id"],
                "ativo": s["ativo"],
                "classe": s["classe"],
                "tipo": s["tipo"],
                "confianca": s["confianca"],
                "preco": s["preco"],
                "justificativa": s["justificativa"],
                "fatores": _json_load(s.get("fatores_json")),
                "fontes": _json_load(s.get("fontes_json")),
                "dados_desatualizados": bool(s.get("dados_desatualizados")),
                "status": s["status"],
                "criado_em": s["criado_em"],
                "idade_segundos": round(db.idade_segundos(s["criado_em"]) or 0, 1),
            }
        )

    pre_abertura = []
    for p in repo.listar_pre_aberturas():
        pre_abertura.append(
            {
                "ativo": p["ativo"],
                "valor_estimado": p["valor_estimado"],
                "confianca": p["confianca"],
                "entradas": _json_load(p.get("entradas_json")),
                "faltantes": _json_load(p.get("faltantes_json")),
                "fonte": p["fonte"],
                "coletado_em": p["coletado_em"],
                "idade_segundos": round(db.idade_segundos(p["coletado_em"]) or 0, 1),
            }
        )

    alertas = repo.listar_alertas(limite=20)
    alertas_view = [
        {
            "id": a["id"],
            "sinal_id": a["sinal_id"],
            "status": a["status"],
            "motivo_bloqueio": a["motivo_bloqueio"],
            "payload": _json_load(a.get("payload_json"), {}),
            "criado_em": a["criado_em"],
            "atualizado_em": a["atualizado_em"],
        }
        for a in alertas
    ]

    return {
        "gerado_em": db.iso(),
        "cotacoes": cotacoes,
        "indicadores": indicadores,
        "sinais": sinais,
        "noticias": repo.listar_noticias(limite=20),
        "humor": repo.humor_mercado(),
        "pre_abertura": pre_abertura,
        "alertas": alertas_view,
        "operacoes": repo.listar_operacoes(limite=50),
        "resumo_operacoes": repo.resumo_operacoes(),
        "servicos": _servicos_com_estado(),
        "saude": repo.ultima_saude(),
        "historico_saude": repo.historico_saude(limite=30),
    }


@app.get("/api/cotacoes")
def api_cotacoes() -> dict[str, Any]:
    return {"cotacoes": [_cotacao_view(c) for c in repo.cotacoes_mais_recentes()]}


@app.get("/api/historico/{ativo}")
def api_historico(ativo: str, timeframe: str = "1d", limite: int = 120) -> dict[str, Any]:
    return {"ativo": ativo, "velas": repo.obter_velas(ativo, timeframe, limite)}


@app.get("/api/sinais")
def api_sinais(limite: int = 50) -> dict[str, Any]:
    return {"sinais": repo.listar_sinais(limite=limite)}


@app.get("/api/noticias")
def api_noticias(limite: int = 50) -> dict[str, Any]:
    return {"noticias": repo.listar_noticias(limite=limite), "humor": repo.humor_mercado()}


@app.get("/api/operacoes")
def api_operacoes() -> dict[str, Any]:
    return {"operacoes": repo.listar_operacoes(limite=100), "resumo": repo.resumo_operacoes()}


class OperacaoEntrada(BaseModel):
    ativo: str
    preco_entrada: float
    classe: Optional[str] = None
    lado: str = "compra"
    quantidade: float = 1.0
    sinal_id: Optional[int] = None
    observacao: Optional[str] = None


class OperacaoSaida(BaseModel):
    preco_saida: float
    observacao: Optional[str] = None


@app.post("/api/operacoes")
def api_criar_operacao(dados: OperacaoEntrada) -> dict[str, Any]:
    op_id = repo.registrar_operacao(
        ativo=dados.ativo.upper(),
        preco_entrada=dados.preco_entrada,
        classe=dados.classe,
        lado=dados.lado,
        quantidade=dados.quantidade,
        sinal_id=dados.sinal_id,
        observacao=dados.observacao,
    )
    log.info("operação manual registrada via dashboard: #%s %s", op_id, dados.ativo)
    return {"ok": True, "id": op_id}


@app.post("/api/operacoes/{operacao_id}/fechar")
def api_fechar_operacao(operacao_id: int, dados: OperacaoSaida) -> dict[str, Any]:
    op = repo.fechar_operacao(operacao_id, dados.preco_saida, dados.observacao)
    if not op:
        raise HTTPException(status_code=404, detail="Operação não encontrada")
    return {"ok": True, "operacao": op}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=_CFG_PRE.get("host", "0.0.0.0"),
        port=int(_CFG_PRE.get("porta", 8080)),
        log_level="info",
    )
