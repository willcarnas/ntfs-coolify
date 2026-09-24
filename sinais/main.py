"""Motor de sinais (RF-04 + RF-06 + RF-08).

Serviço independente. Lê apenas do banco (velas, notícias, cotações), calcula
indicadores, estimativas de pré-abertura e gera sinais explicáveis. Não envia
nada: quem decide envio é o motor de risco (RF-09).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from comum import config, db, repo  # noqa: E402
from comum.indicadores import calcular_indicadores  # noqa: E402
from comum.servico import Servico, modo_uma_vez  # noqa: E402
from pre_abertura import estimar  # noqa: E402
from regras_sinais import gerar_sinal  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
CFG = config.load_json(CONFIG_PATH, {})
MODULO = "sinais"

REGISTRAR_OBSERVACAO = bool(CFG.get("registrar_observacao", False))
COOLDOWN_SINAL_SEGUNDOS = int(CFG.get("cooldown_sinal_segundos", 900))


class ServicoSinais(Servico):
    def __init__(self) -> None:
        super().__init__(MODULO, intervalo=int(CFG.get("intervalo_sinais", 120)))

    def ciclo(self) -> None:
        timeframe = CFG.get("timeframe", "1d")
        limite = int(CFG.get("limite_velas", 300))
        idade_max = int(CFG.get("idade_max_dados_segundos", 86400))
        humor = repo.humor_mercado()
        pre_aberturas = self._calcular_pre_abertura()

        ativos = repo.ativos_monitorados()
        gerados = 0
        for item in ativos:
            ativo, classe = item["ativo"], item["classe"]
            # Só gera sinal para ativos com o timeframe configurado; se ausente,
            # usa o timeframe disponível de maior granularidade.
            tf = timeframe
            velas = repo.obter_velas(ativo, tf, limite)
            if len(velas) < 5:
                tf = _timeframe_disponivel(ativo, item)
                velas = repo.obter_velas(ativo, tf, limite)
            if len(velas) < 5:
                continue

            fechamentos = [v["fechamento"] for v in velas if v["fechamento"] is not None]
            volumes = [v["volume"] for v in velas if v["volume"] is not None]
            if len(fechamentos) < 5:
                continue

            indicadores = calcular_indicadores(fechamentos, volumes)
            fonte = velas[-1]["fonte"]
            repo.salvar_indicadores(ativo, classe, tf, indicadores, fonte=fonte)

            idade = db.idade_segundos(velas[-1].get("coletado_em")) or 0
            desatualizado = idade > idade_max

            est = pre_aberturas.get(ativo)
            sinal = gerar_sinal(
                ativo=ativo,
                classe=classe,
                preco=indicadores.get("fechamento"),
                indicadores=indicadores,
                humor_score=humor["score"],
                estimativa_pre_abertura=est.valor_estimado if est else None,
                dados_desatualizados=desatualizado,
            )

            if sinal.tipo == "observacao" and not REGISTRAR_OBSERVACAO:
                continue
            if self._em_cooldown(ativo, sinal.tipo):
                continue

            sinal_id = repo.inserir_sinal(sinal)
            if sinal_id is not None:
                gerados += 1
                self.log.info(
                    "sinal %s %s conf=%.2f (id=%s) preço=%s",
                    sinal.tipo, ativo, sinal.confianca, sinal_id, sinal.preco,
                )

        self.log.info("ciclo concluído: %s sinais gerados de %s ativos", gerados, len(ativos))

    def _em_cooldown(self, ativo: str, tipo: str) -> bool:
        ultimo = repo.ultimo_sinal(ativo)
        if not ultimo or ultimo["tipo"] != tipo:
            return False
        idade = db.idade_segundos(ultimo["criado_em"])
        return idade is not None and idade < COOLDOWN_SINAL_SEGUNDOS

    def _calcular_pre_abertura(self) -> dict[str, Any]:
        cfg_pa = CFG.get("pre_abertura", {})
        if not cfg_pa.get("habilitado", False):
            return {}
        resultado: dict[str, Any] = {}
        for alvo, regra in cfg_pa.get("alvos", {}).items():
            ref = regra.get("referencia", alvo)
            pesos = regra.get("pesos", {})
            cot_ref = repo.ultima_cotacao(ref)
            if not cot_ref:
                continue
            variacoes: dict[str, Optional[float]] = {}
            fontes: dict[str, str] = {}
            for nome_ref in pesos:
                cot = repo.ultima_cotacao(nome_ref)
                if cot and cot.get("variacao_pct") is not None:
                    variacoes[nome_ref] = cot["variacao_pct"]
                    fontes[nome_ref] = cot.get("fonte", "desconhecida")
                else:
                    variacoes[nome_ref] = None
            est = estimar(
                ativo=alvo,
                preco_referencia=cot_ref.get("preco"),
                variacoes=variacoes,
                pesos=pesos,
                fontes=fontes,
            )
            repo.salvar_pre_abertura(est)
            resultado[alvo] = est
            self.log.info(
                "pré-abertura %s: estimado=%s conf=%.2f faltantes=%s",
                alvo, est.valor_estimado, est.confianca, est.faltantes,
            )
        return resultado


def _timeframe_disponivel(ativo: str, item: dict[str, Any]) -> str:
    for tf in ("1d", "1h", "5m", "1m"):
        if repo.obter_velas(ativo, tf, 5):
            return tf
    return item.get("timeframe") or "1d"


if __name__ == "__main__":
    ServicoSinais().executar(executar_uma_vez=modo_uma_vez())
