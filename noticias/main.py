"""Módulo de notícias e humor de mercado (RF-07).

Serviço independente. Cascata RSS -> scraping. Classifica sentimento e grava
cada notícia inédita no banco (deduplicada por hash).
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from comum import config, repo  # noqa: E402
from comum.contratos_dados import Noticia  # noqa: E402
from comum.servico import Servico, modo_uma_vez  # noqa: E402
import rss_client  # noqa: E402
import scraping_client  # noqa: E402
from sentiment import classificar  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
CFG = config.load_json(CONFIG_PATH, {})
MODULO = "noticias"


class ServicoNoticias(Servico):
    def __init__(self) -> None:
        super().__init__(MODULO, intervalo=int(CFG.get("intervalo_coleta", 300)))

    def ciclo(self) -> None:
        itens = rss_client.coletar(CFG.get("feeds", []), int(CFG.get("limite_por_feed", 15)))
        origem = "rss"
        if not itens:
            itens = scraping_client.coletar(CFG.get("scraping", []))
            origem = "scraping"

        novas = 0
        for item in itens:
            texto = f"{item.get('titulo','')} {item.get('resumo','') or ''}"
            rotulo, score = classificar(texto)
            noticia = Noticia(
                titulo=item["titulo"],
                link=item.get("link"),
                resumo=item.get("resumo"),
                fonte=item.get("fonte", origem),
                sentimento=rotulo,
                score=score,
                publicado_em=item.get("publicado_em"),
            )
            if repo.inserir_noticia(noticia):
                novas += 1

        humor = repo.humor_mercado()
        self.log.info(
            "notícias: %s lidas via %s, %s novas | humor=%s (score=%s)",
            len(itens), origem, novas, humor["rotulo"], humor["score"],
        )
        if not itens:
            self.heartbeat("degradado", "nenhuma fonte de notícias disponível")


if __name__ == "__main__":
    ServicoNoticias().executar(executar_uma_vez=modo_uma_vez())
