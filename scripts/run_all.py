"""Executador de desenvolvimento: sobe todos os módulos como processos separados.

Reproduz localmente o isolamento de processos exigido pelo PRD (secao 5.2).
Em produção, cada módulo é registrado como serviço Windows independente via NSSM
(ver scripts/install_servicos.ps1). Aqui é apenas conveniência para o dia a dia.
"""
from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

MODULOS = {
    "b3": "b3/main.py",
    "forex": "forex/main.py",
    "cripto": "cripto/main.py",
    "noticias": "noticias/main.py",
    "sinais": "sinais/main.py",
    "risco": "risco/main.py",
    "telegram": "telegram/main.py",
    "dashboard": "dashboard/main.py",
    "monitor_saude": "scripts/monitor_saude.py",
}

# Ordem de subida conforme PRD secao 8 (dados -> sinais -> risco -> alertas -> dashboard).
ORDEM = ["b3", "forex", "cripto", "noticias", "monitor_saude", "sinais", "risco", "telegram", "dashboard"]


def subir(nomes: list[str]) -> list[subprocess.Popen]:
    processos: list[subprocess.Popen] = []
    for nome in nomes:
        caminho = RAIZ / MODULOS[nome]
        log = open(RAIZ / "logs" / f"{nome}.out.log", "a", encoding="utf-8")
        proc = subprocess.Popen(
            [sys.executable, str(caminho)],
            cwd=str(RAIZ),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        processos.append(proc)
        print(f"[run_all] {nome} iniciado (pid {proc.pid})")
        time.sleep(0.5)
    return processos


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="subir apenas estes módulos")
    parser.add_argument("--skip", nargs="*", default=[], help="não subir estes módulos")
    args = parser.parse_args()

    nomes = args.only if args.only else [m for m in ORDEM if m not in args.skip]
    invalidos = [n for n in nomes if n not in MODULOS]
    if invalidos:
        print(f"módulos inválidos: {invalidos}. Válidos: {list(MODULOS)}")
        sys.exit(1)

    processos = subir(nomes)
    parar = False

    def _handler(*_):
        nonlocal parar
        parar = True

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)

    try:
        while not parar:
            time.sleep(1)
            for nome, proc in zip(nomes, processos):
                if proc.poll() is not None:
                    print(f"[run_all] AVISO: {nome} encerrou (exit {proc.returncode})")
    finally:
        print("[run_all] encerrando processos...")
        for nome, proc in zip(nomes, processos):
            if proc.poll() is None:
                proc.terminate()
        for proc in processos:
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("[run_all] encerrado.")


if __name__ == "__main__":
    main()
