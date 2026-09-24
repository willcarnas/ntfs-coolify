"""Módulo de coleta forex (RF-02).

Serviço independente 24/7. Usa MetaTrader 5 quando disponível; caso contrário,
se `permitir_simulado` estiver ligado, usa gerador simulado (fonte `simulado`,
claramente marcada). Sempre grava histórico com fonte e timestamp.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from comum import config, db, repo  # noqa: E402
from comum.contratos_dados import Cotacao, Vela  # noqa: E402
from comum.servico import Servico, modo_uma_vez  # noqa: E402
import simulado  # noqa: E402
from mt5_client import ConectorMT5  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
CFG = config.load_json(CONFIG_PATH, {})
MODULO = "forex"


class ServicoForex(Servico):
    def __init__(self) -> None:
        super().__init__(MODULO, intervalo=int(CFG.get("intervalo_coleta", 60)))
        self.conector = ConectorMT5(terminal_path=CFG.get("terminal_path") or None)
        self.usando_simulado = False

    def inicializar(self) -> None:
        if self.conector.disponivel and self.conector.conectar():
            self.log.info("MT5 operacional; coletando dados reais")
            self.usando_simulado = False
        elif CFG.get("permitir_simulado", False):
            self.usando_simulado = True
            self.log.warning(
                "MT5 indisponível: operando com feed SIMULADO (fonte='simulado'), "
                "apenas para validar o pipeline. Configure o terminal para dados reais."
            )

    def _coletar(self, simbolo: str) -> Optional[tuple[list[dict[str, Any]], str]]:
        if not self.usando_simulado:
            velas = self.conector.velas(simbolo, CFG.get("timeframe", "1h"), int(CFG.get("limite_velas", 300)))
            if velas:
                return velas, f"mt5:{simbolo}"
            # Cai para simulado somente se permitido (evita lacuna silenciosa).
            if not CFG.get("permitir_simulado", False):
                return None
            self.log.warning("sem velas MT5 para %s; caindo para simulado", simbolo)
        return simulado.velas(simbolo, int(CFG.get("limite_velas", 300))), "simulado"

    def ciclo(self) -> None:
        if not self.usando_simulado:
            self.conector.conectar()
            if not self.conector.conectado and CFG.get("permitir_simulado", False):
                self.usando_simulado = True

        simbolos = list(CFG.get("pares", [])) + list(CFG.get("indices_cfd", [])) + list(
            CFG.get("referencias_pre_abertura", [])
        )
        simbolos = list(dict.fromkeys(simbolos))  # remove duplicatas preservando ordem
        timeframe = CFG.get("timeframe", "1h")
        disponiveis = 0

        for simbolo in simbolos:
            resultado = self._coletar(simbolo)
            if not resultado:
                self.log.warning("sem dados forex para %s", simbolo)
                continue
            brutos, fonte = resultado
            velas = [
                Vela(
                    ativo=simbolo, classe="forex", timeframe=timeframe,
                    ts=bruto["ts"] if isinstance(bruto["ts"], str) else db.iso(bruto["ts"]),
                    abertura=bruto["abertura"], maxima=bruto["maxima"], minima=bruto["minima"],
                    fechamento=bruto["fechamento"], volume=bruto.get("volume"), fonte=fonte,
                )
                for bruto in brutos
            ]
            repo.inserir_velas(velas)

            if self.usando_simulado:
                t = simulado.ticker(simbolo)
                preco, bid, ask, variacao = t["preco"], t["bid"], t["ask"], t["variacao_pct"]
            else:
                t = self.conector.ticker(simbolo) or {}
                preco, bid, ask, variacao = t.get("preco"), t.get("bid"), t.get("ask"), t.get("variacao_pct")

            repo.inserir_cotacao(
                Cotacao(
                    ativo=simbolo, classe="forex", preco=preco, bid=bid, ask=ask,
                    abertura=velas[-1].abertura, maxima=velas[-1].maxima,
                    minima=velas[-1].minima, volume=velas[-1].volume,
                    variacao_pct=variacao, fonte=fonte,
                    extra={"simulado": self.usando_simulado},
                )
            )
            disponiveis += 1

        if self.usando_simulado:
            self.heartbeat("degradado", "MT5 indisponível - usando feed simulado")
        self.log.info("ciclo concluído: %s símbolos (%s)", disponiveis, "simulado" if self.usando_simulado else "mt5")

    def finalizar(self) -> None:
        self.conector.desconectar()


if __name__ == "__main__":
    ServicoForex().executar(executar_uma_vez=modo_uma_vez())
