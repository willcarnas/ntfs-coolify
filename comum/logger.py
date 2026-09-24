"""Log estruturado (nivel, timestamp, modulo, mensagem) - secao 8 Observabilidade.

Escreve simultaneamente para stdout e para `logs/<modulo>.log`, com rotacao
simples por tamanho para nao crescer indefinidamente no mini PC.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from . import config


def _build_logger(nome: str) -> logging.Logger:
    logger = logging.getLogger(nome)
    if getattr(logger, "_trading_configurado", False):
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | " + nome + " | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    try:
        fh = RotatingFileHandler(
            config.LOG_DIR / f"{nome}.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        # Se nao conseguir escrever em disco, segue apenas com stdout.
        pass

    logger._trading_configurado = True  # type: ignore[attr-defined]
    return logger


def get_logger(nome: str) -> logging.Logger:
    return _build_logger(nome)
