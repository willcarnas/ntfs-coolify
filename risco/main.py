"""Motor de risco (RF-09).

Serviço independente. Lê sinais pendentes, aplica as regras puras de
`regras_risco.py` e decide: enfileira alerta (para o serviço de Telegram) ou
marca o sinal como bloqueado. Continua funcional mesmo se o motor de sinais
estiver parado (apenas não há sinais novos para avaliar).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from comum import config, db, repo  # noqa: E402
from comum.servico import Servico, modo_uma_vez  # noqa: E402
from regras_risco import avaliar_risco, resumo  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
CFG = config.load_json(CONFIG_PATH, {})
MODULO = "risco"


class ServicoRisco(Servico):
    def __init__(self) -> None:
        super().__init__(MODULO, intervalo=int(CFG.get("intervalo_risco", 60)))

    def ciclo(self) -> None:
        pendentes = repo.listar_sinais(limite=100, status="pendente")
        aprovados = bloqueados = 0

        for sinal in pendentes:
            contexto = self._contexto(sinal)
            resultado = avaliar_risco(sinal, contexto, CFG)
            if resultado.aprovado:
                payload = _montar_payload(sinal, contexto)
                repo.enfileirar_alerta(sinal["id"], payload, status="pendente")
                repo.atualizar_status_sinal(sinal["id"], "aprovado")
                aprovados += 1
                self.log.info("APROVADO %s %s conf=%.2f -> fila de alertas",
                              sinal["tipo"], sinal["ativo"], sinal["confianca"])
            else:
                repo.enfileirar_alerta(sinal["id"], _montar_payload(sinal, contexto),
                                       status="bloqueado", motivo_bloqueio=resultado.motivo)
                repo.atualizar_status_sinal(sinal["id"], "bloqueado")
                bloqueados += 1
                self.log.info("BLOQUEADO %s %s: %s", sinal["tipo"], sinal["ativo"], resultado.motivo)

        if pendentes:
            self.log.info("ciclo: %s aprovados, %s bloqueados de %s pendentes",
                          aprovados, bloqueados, len(pendentes))

    def _contexto(self, sinal: dict[str, Any]) -> dict[str, Any]:
        ativo = sinal["ativo"]
        ultimo = repo.ultimo_alerta_enviado(ativo)
        return {
            "agora": db.agora_utc(),
            "ultimo_alerta_ativo_em": ultimo["atualizado_em"] if ultimo else None,
            "ultimo_alerta_ativo_tipo": ultimo.get("tipo") if ultimo else None,
            "alertas_enviados_hoje_ativo": repo.alertas_enviados_hoje(ativo),
            "alertas_enviados_hoje_total": repo.alertas_enviados_hoje(),
        }


def _montar_payload(sinal: dict[str, Any], contexto: dict[str, Any]) -> dict[str, Any]:
    import json

    fatores = json.loads(sinal.get("fatores_json") or "[]")
    fontes = json.loads(sinal.get("fontes_json") or "[]")
    return {
        "sinal_id": sinal["id"],
        "ativo": sinal["ativo"],
        "classe": sinal["classe"],
        "tipo": sinal["tipo"],
        "confianca": sinal["confianca"],
        "preco": sinal["preco"],
        "justificativa": sinal["justificativa"],
        "fatores": fatores,
        "fontes": fontes,
        "dados_desatualizados": bool(sinal.get("dados_desatualizados")),
        "criado_em": sinal["criado_em"],
    }


if __name__ == "__main__":
    ServicoRisco().executar(executar_uma_vez=modo_uma_vez())
