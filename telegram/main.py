"""Serviço de Telegram (RF-10 + comandos de RF-12).

Serviço independente e tolerante a falhas: se o token não estiver configurado
ou a API estiver fora, os alertas permanecem na fila e o serviço continua vivo.
Também aceita comandos para registrar operações manualmente (/entrada, /saida).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from comum import config, repo  # noqa: E402
from comum.servico import Servico, modo_uma_vez  # noqa: E402
import bot  # noqa: E402

MODULO = "telegram"
AJUDA = (
    "Comandos disponíveis:\n"
    "/status — resumo do sistema\n"
    "/entrada ATIVO PRECO [QTD] — registra abertura de operação\n"
    "/saida ID PRECO — registra fechamento da operação\n"
    "/operacoes — últimas operações\n"
    "/ajuda — esta mensagem"
)


class ServicoTelegram(Servico):
    def __init__(self) -> None:
        super().__init__(MODULO, intervalo=15)
        self._offset: Optional[int] = None

    def inicializar(self) -> None:
        if not bot.configurado():
            self.log.warning(
                "TELEGRAM_BOT_TOKEN/CHAT_ID não configurados: alertas ficarão na fila "
                "(configure .env para ativar o envio)."
            )

    def ciclo(self) -> None:
        if not bot.configurado():
            self.heartbeat("degradado", "Telegram não configurado")
            return

        # 1) Envia alertas pendentes aprovados pelo motor de risco
        pendentes = repo.alertas_pendentes(limite=10)
        enviados = 0
        for alerta in pendentes:
            payload = json.loads(alerta["payload_json"])
            ok = bot.enviar_mensagem(bot.formatar_alerta(payload))
            if ok:
                repo.marcar_alerta(alerta["id"], "enviado")
                if alerta.get("sinal_id"):
                    repo.atualizar_status_sinal(alerta["sinal_id"], "enviado")
                enviados += 1
                self.log.info("alerta #%s enviado (%s %s)", alerta["id"], payload.get("tipo"), payload.get("ativo"))
            else:
                # Marca erro e para de tentar para não travar a fila indefinidamente.
                tentativas = (alerta.get("tentativas") or 0) + 1
                status = "erro" if tentativas >= 3 else "pendente"
                repo.marcar_alerta(alerta["id"], status, motivo="falha de envio")
                break

        # 2) Processa comandos recebidos
        self._processar_comandos()

        if enviados:
            self.log.info("ciclo: %s alertas enviados", enviados)

    def _processar_comandos(self) -> None:
        updates = bot.obter_updates(self._offset)
        for upd in updates:
            self._offset = upd.get("update_id", 0) + 1
            msg = upd.get("message") or {}
            texto = (msg.get("text") or "").strip()
            if not texto:
                continue
            try:
                resposta = self._executar_comando(texto)
            except Exception as exc:  # noqa: BLE001
                resposta = f"Erro ao executar comando: {exc}"
            if resposta:
                bot.enviar_mensagem(resposta)

    def _executar_comando(self, texto: str) -> Optional[str]:
        partes = texto.split()
        cmd = partes[0].lower().split("@")[0]
        if cmd in ("/start", "/ajuda", "/help"):
            return AJUDA
        if cmd == "/status":
            servicos = repo.listar_servicos()
            saude = repo.ultima_saude() or {}
            resumo = repo.resumo_operacoes()
            linhas = ["<b>Status do sistema</b>"]
            for s in servicos:
                idade = s.get("idade_segundos")
                estado = s.get("status")
                if idade is not None and idade > 180:
                    estado += " (desatualizado)"
                linhas.append(f"• {s['servico']}: {estado}")
            linhas.append(
                f"RAM {saude.get('ram_pct', '?')}% | CPU {saude.get('cpu_pct', '?')}% | "
                f"Disco {saude.get('disco_pct', '?')}% | Internet: {'ok' if saude.get('internet_ok') else 'off'}"
            )
            linhas.append(
                f"Operações: {resumo.get('total', 0)} (abertas {resumo.get('abertas', 0)}) | "
                f"Resultado: {resumo.get('resultado', 0)} | Acerto: {resumo.get('taxa_acerto', 0)}%"
            )
            return "\n".join(linhas)
        if cmd == "/entrada" and len(partes) >= 3:
            ativo = partes[1].upper()
            preco = float(partes[2].replace(",", "."))
            qtd = float(partes[3].replace(",", ".")) if len(partes) >= 4 else 1.0
            op_id = repo.registrar_operacao(ativo=ativo, preco_entrada=preco, quantidade=qtd)
            return f"✅ Operação #{op_id} aberta: {ativo} @ {preco} x{qtd}"
        if cmd == "/saida" and len(partes) >= 3:
            op_id = int(partes[1])
            preco = float(partes[2].replace(",", "."))
            op = repo.fechar_operacao(op_id, preco)
            if not op:
                return f"Operação #{op_id} não encontrada."
            return (
                f"✅ Operação #{op_id} fechada: {op['ativo']} @ {preco}\n"
                f"Resultado: {op['resultado']} ({op['resultado_pct']}%)"
            )
        if cmd == "/operacoes":
            ops = repo.listar_operacoes(limite=10)
            if not ops:
                return "Nenhuma operação registrada."
            linhas = ["<b>Últimas operações</b>"]
            for op in ops:
                linhas.append(
                    f"#{op['id']} {op['ativo']} {op['status']} entrada={op['preco_entrada']} "
                    f"saida={op['preco_saida']} res={op['resultado']}"
                )
            return "\n".join(linhas)
        return None


if __name__ == "__main__":
    ServicoTelegram().executar(executar_uma_vez=modo_uma_vez())
