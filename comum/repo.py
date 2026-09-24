"""Camada de acesso a dados compartilhada.

Concentra todo o SQL usado pelos módulos. Como é parte da biblioteca comum,
pode ser importada por qualquer módulo — a restrição do PRD é não importar
código de um *domínio* dentro de outro, o que aqui não ocorre.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Optional

from . import db
from .contratos_dados import (
    Cotacao,
    EstimativaPreAbertura,
    Noticia,
    Sinal,
    Vela,
)

# ── Cotações e velas ────────────────────────────────────────────────────────
_INSERT_COTACAO = """
INSERT INTO cotacoes
    (ativo, classe, preco, abertura, maxima, minima, volume, variacao_pct,
     bid, ask, extra_json, fonte, coletado_em)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def inserir_cotacao(cot: Cotacao) -> int:
    cur = db.execute(_INSERT_COTACAO, cot.to_row())
    return int(cur.lastrowid)


def inserir_cotacoes(cotacoes: Iterable[Cotacao]) -> int:
    total = 0
    with db.transacao() as conn:
        for cot in cotacoes:
            conn.execute(_INSERT_COTACAO, cot.to_row())
            total += 1
    return total


def ultima_cotacao(ativo: str) -> Optional[dict[str, Any]]:
    row = db.query_one(
        "SELECT * FROM cotacoes WHERE ativo = ? ORDER BY coletado_em DESC LIMIT 1",
        (ativo,),
    )
    return dict(row) if row else None


def cotacoes_mais_recentes() -> list[dict[str, Any]]:
    """Uma linha por ativo (a mais recente), com idade em segundos."""
    rows = db.query(
        """
        SELECT c.* FROM cotacoes c
        WHERE c.id = (
            SELECT c2.id FROM cotacoes c2
            WHERE c2.ativo = c.ativo
            ORDER BY c2.coletado_em DESC, c2.id DESC
            LIMIT 1
        )
        ORDER BY c.classe, c.ativo
        """
    )
    resultado = []
    for r in rows:
        d = dict(r)
        d["idade_segundos"] = db.idade_segundos(d.get("coletado_em"))
        resultado.append(d)
    return resultado


_UPSERT_VELA = """
INSERT INTO velas
    (ativo, classe, timeframe, ts, abertura, maxima, minima, fechamento,
     volume, fonte, coletado_em)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(ativo, timeframe, ts) DO UPDATE SET
    abertura = excluded.abertura,
    maxima = excluded.maxima,
    minima = excluded.minima,
    fechamento = excluded.fechamento,
    volume = excluded.volume,
    fonte = excluded.fonte,
    coletado_em = excluded.coletado_em
"""


def inserir_velas(velas: Iterable[Vela]) -> int:
    total = 0
    with db.transacao() as conn:
        for v in velas:
            conn.execute(
                _UPSERT_VELA,
                (
                    v.ativo,
                    v.classe,
                    v.timeframe,
                    v.ts,
                    v.abertura,
                    v.maxima,
                    v.minima,
                    v.fechamento,
                    v.volume,
                    v.fonte,
                    v.coletado_em,
                ),
            )
            total += 1
    return total


def obter_velas(ativo: str, timeframe: str, limite: int = 300) -> list[dict[str, Any]]:
    rows = db.query(
        """
        SELECT * FROM velas
        WHERE ativo = ? AND timeframe = ?
        ORDER BY ts DESC LIMIT ?
        """,
        (ativo, timeframe, limite),
    )
    return [dict(r) for r in reversed(rows)]


def ativos_monitorados() -> list[dict[str, Any]]:
    rows = db.query(
        """
        SELECT ativo, classe, COUNT(*) AS n,
               MIN(ts) AS desde, MAX(ts) AS ate
        FROM velas GROUP BY ativo, classe ORDER BY classe, ativo
        """
    )
    return [dict(r) for r in rows]


# ── Indicadores ─────────────────────────────────────────────────────────────
_UPSERT_INDICADOR = """
INSERT INTO indicadores (ativo, classe, timeframe, nome, valor, fonte, coletado_em)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(ativo, timeframe, nome) DO UPDATE SET
    valor = excluded.valor,
    classe = excluded.classe,
    fonte = excluded.fonte,
    coletado_em = excluded.coletado_em
"""


def salvar_indicadores(
    ativo: str,
    classe: str,
    timeframe: str,
    indicadores: dict[str, Any],
    fonte: str,
) -> int:
    ts = db.iso()
    total = 0
    with db.transacao() as conn:
        for nome, valor in indicadores.items():
            conn.execute(
                _UPSERT_INDICADOR,
                (ativo, classe, timeframe, nome, valor, fonte, ts),
            )
            total += 1
    return total


def obter_indicadores(ativo: str, timeframe: Optional[str] = None) -> dict[str, Any]:
    if timeframe:
        rows = db.query(
            "SELECT * FROM indicadores WHERE ativo = ? AND timeframe = ?",
            (ativo, timeframe),
        )
    else:
        rows = db.query("SELECT * FROM indicadores WHERE ativo = ?", (ativo,))
    return {r["nome"]: r["valor"] for r in rows}


def obter_indicadores_detalhado(ativo: str, timeframe: Optional[str] = None) -> list[dict[str, Any]]:
    if timeframe:
        rows = db.query(
            "SELECT * FROM indicadores WHERE ativo = ? AND timeframe = ? ORDER BY nome",
            (ativo, timeframe),
        )
    else:
        rows = db.query(
            "SELECT * FROM indicadores WHERE ativo = ? ORDER BY nome", (ativo,)
        )
    return [dict(r) for r in rows]


# ── Sinais ──────────────────────────────────────────────────────────────────
_INSERT_SINAL = """
INSERT OR IGNORE INTO sinais
    (ativo, classe, tipo, confianca, preco, justificativa, fatores_json,
     fontes_json, dados_desatualizados, status, criado_em)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def inserir_sinal(sinal: Sinal) -> Optional[int]:
    """Insere um sinal; ignora duplicatas (mesma chave única). Retorna o id."""
    cur = db.execute(_INSERT_SINAL, sinal.to_row())
    if cur.rowcount == 0:
        row = db.query_one(
            """
            SELECT id FROM sinais
            WHERE ativo = ? AND classe = ? AND tipo = ? AND criado_em = ?
            """,
            (sinal.ativo, sinal.classe, sinal.tipo, sinal.criado_em),
        )
        return int(row["id"]) if row else None
    return int(cur.lastrowid)


def atualizar_status_sinal(sinal_id: int, status: str) -> None:
    db.execute("UPDATE sinais SET status = ? WHERE id = ?", (status, sinal_id))


def listar_sinais(limite: int = 50, status: Optional[str] = None) -> list[dict[str, Any]]:
    if status:
        rows = db.query(
            "SELECT * FROM sinais WHERE status = ? ORDER BY criado_em DESC LIMIT ?",
            (status, limite),
        )
    else:
        rows = db.query(
            "SELECT * FROM sinais ORDER BY criado_em DESC LIMIT ?", (limite,)
        )
    return [dict(r) for r in rows]


def sinal_por_id(sinal_id: int) -> Optional[dict[str, Any]]:
    row = db.query_one("SELECT * FROM sinais WHERE id = ?", (sinal_id,))
    return dict(row) if row else None


def ultimo_sinal(ativo: str) -> Optional[dict[str, Any]]:
    row = db.query_one(
        "SELECT * FROM sinais WHERE ativo = ? ORDER BY criado_em DESC LIMIT 1",
        (ativo,),
    )
    return dict(row) if row else None


# ── Fila de alertas ─────────────────────────────────────────────────────────
def enfileirar_alerta(
    sinal_id: Optional[int],
    payload: dict[str, Any],
    status: str = "pendente",
    motivo_bloqueio: Optional[str] = None,
) -> int:
    cur = db.execute(
        """
        INSERT INTO fila_alertas (sinal_id, payload_json, status, motivo_bloqueio, criado_em)
        VALUES (?, ?, ?, ?, ?)
        """,
        (sinal_id, json.dumps(payload, ensure_ascii=False), status, motivo_bloqueio, db.iso()),
    )
    return int(cur.lastrowid)


def alertas_pendentes(limite: int = 20) -> list[dict[str, Any]]:
    rows = db.query(
        "SELECT * FROM fila_alertas WHERE status = 'pendente' ORDER BY criado_em LIMIT ?",
        (limite,),
    )
    return [dict(r) for r in rows]


def marcar_alerta(
    alerta_id: int,
    status: str,
    motivo: Optional[str] = None,
) -> None:
    db.execute(
        """
        UPDATE fila_alertas
        SET status = ?, motivo_bloqueio = COALESCE(?, motivo_bloqueio),
            tentativas = tentativas + 1, atualizado_em = ?
        WHERE id = ?
        """,
        (status, motivo, db.iso(), alerta_id),
    )


def listar_alertas(limite: int = 50) -> list[dict[str, Any]]:
    rows = db.query("SELECT * FROM fila_alertas ORDER BY criado_em DESC LIMIT ?", (limite,))
    return [dict(r) for r in rows]


def alertas_enviados_hoje(ativo: Optional[str] = None) -> int:
    """Conta alertas enviados com sucesso desde 00:00 UTC de hoje (RF-09)."""
    inicio = db.agora_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    if ativo:
        row = db.query_one(
            """
            SELECT COUNT(*) AS n FROM fila_alertas a
            JOIN sinais s ON s.id = a.sinal_id
            WHERE a.status = 'enviado' AND a.atualizado_em >= ? AND s.ativo = ?
            """,
            (db.iso(inicio), ativo),
        )
    else:
        row = db.query_one(
            "SELECT COUNT(*) AS n FROM fila_alertas WHERE status = 'enviado' AND atualizado_em >= ?",
            (db.iso(inicio),),
        )
    return int(row["n"]) if row else 0


def ultimo_alerta_enviado(ativo: str) -> Optional[dict[str, Any]]:
    row = db.query_one(
        """
        SELECT a.*, s.ativo AS ativo, s.tipo AS tipo FROM fila_alertas a
        JOIN sinais s ON s.id = a.sinal_id
        WHERE s.ativo = ? AND a.status = 'enviado'
        ORDER BY a.atualizado_em DESC LIMIT 1
        """,
        (ativo,),
    )
    return dict(row) if row else None


# ── Notícias ────────────────────────────────────────────────────────────────
def _hash_noticia(titulo: str, link: Optional[str]) -> str:
    base = f"{(titulo or '').strip().lower()}|{(link or '').strip()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def inserir_noticia(noticia: Noticia) -> bool:
    """Insere se inédita; retorna True se inseriu."""
    h = noticia.hash or _hash_noticia(noticia.titulo, noticia.link)
    noticia.hash = h
    cur = db.execute(
        """
        INSERT OR IGNORE INTO noticias
            (titulo, link, resumo, fonte, sentimento, score, publicado_em, coletado_em, hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        noticia.to_row(),
    )
    return cur.rowcount > 0


def listar_noticias(limite: int = 50, apenas_com_sentimento: bool = False) -> list[dict[str, Any]]:
    if apenas_com_sentimento:
        rows = db.query(
            "SELECT * FROM noticias WHERE sentimento IS NOT NULL ORDER BY COALESCE(publicado_em, coletado_em) DESC LIMIT ?",
            (limite,),
        )
    else:
        rows = db.query(
            "SELECT * FROM noticias ORDER BY COALESCE(publicado_em, coletado_em) DESC LIMIT ?",
            (limite,),
        )
    return [dict(r) for r in rows]


def humor_mercado() -> dict[str, Any]:
    """Agrega sentimento das últimas notícias em um score simples de humor."""
    rows = db.query(
        """
        SELECT sentimento, COUNT(*) AS n FROM noticias
        WHERE sentimento IS NOT NULL
          AND coletado_em >= ?
        GROUP BY sentimento
        """,
        (db.iso(db.agora_utc().replace(hour=0, minute=0, second=0, microsecond=0)),),
    )
    contagem = {r["sentimento"]: int(r["n"]) for r in rows}
    pos = contagem.get("positivo", 0)
    neg = contagem.get("negativo", 0)
    total = pos + neg + contagem.get("neutro", 0)
    score = 0.0 if total == 0 else (pos - neg) / total
    if score > 0.2:
        rotulo = "positivo"
    elif score < -0.2:
        rotulo = "negativo"
    else:
        rotulo = "neutro"
    return {"score": round(score, 3), "rotulo": rotulo, "contagem": contagem, "total": total}


# ── Operações ───────────────────────────────────────────────────────────────
def registrar_operacao(
    ativo: str,
    preco_entrada: float,
    classe: Optional[str] = None,
    lado: str = "compra",
    quantidade: float = 1.0,
    sinal_id: Optional[int] = None,
    observacao: Optional[str] = None,
) -> int:
    cur = db.execute(
        """
        INSERT INTO operacoes
            (ativo, classe, lado, quantidade, preco_entrada, sinal_id, status,
             observacao, aberta_em, fonte, coletado_em)
        VALUES (?, ?, ?, ?, ?, ?, 'aberta', ?, ?, 'manual', ?)
        """,
        (ativo, classe, lado, quantidade, preco_entrada, sinal_id, observacao, db.iso(), db.iso()),
    )
    return int(cur.lastrowid)


def fechar_operacao(operacao_id: int, preco_saida: float, observacao: Optional[str] = None) -> Optional[dict[str, Any]]:
    op = db.query_one("SELECT * FROM operacoes WHERE id = ?", (operacao_id,))
    if not op:
        return None
    qtd = float(op["quantidade"] or 0)
    entrada = float(op["preco_entrada"] or 0)
    if (op["lado"] or "compra") == "venda":
        resultado = (entrada - preco_saida) * qtd
    else:
        resultado = (preco_saida - entrada) * qtd
    resultado_pct = 0.0 if entrada == 0 else (resultado / (entrada * qtd) * 100.0) if qtd else 0.0
    db.execute(
        """
        UPDATE operacoes
        SET preco_saida = ?, status = 'fechada', resultado = ?, resultado_pct = ?,
            observacao = COALESCE(?, observacao), fechada_em = ?
        WHERE id = ?
        """,
        (preco_saida, round(resultado, 2), round(resultado_pct, 2), observacao, db.iso(), operacao_id),
    )
    return dict(db.query_one("SELECT * FROM operacoes WHERE id = ?", (operacao_id,)))


def listar_operacoes(limite: int = 100, status: Optional[str] = None) -> list[dict[str, Any]]:
    if status:
        rows = db.query(
            "SELECT * FROM operacoes WHERE status = ? ORDER BY aberta_em DESC LIMIT ?",
            (status, limite),
        )
    else:
        rows = db.query(
            "SELECT * FROM operacoes ORDER BY aberta_em DESC LIMIT ?", (limite,)
        )
    return [dict(r) for r in rows]


def resumo_operacoes() -> dict[str, Any]:
    row = db.query_one(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'aberta' THEN 1 ELSE 0 END) AS abertas,
            SUM(CASE WHEN status = 'fechada' THEN 1 ELSE 0 END) AS fechadas,
            SUM(CASE WHEN status = 'fechada' THEN resultado ELSE 0 END) AS resultado,
            SUM(CASE WHEN status = 'fechada' AND resultado > 0 THEN 1 ELSE 0 END) AS vitorias,
            SUM(CASE WHEN status = 'fechada' AND resultado < 0 THEN 1 ELSE 0 END) AS derrotas
        FROM operacoes
        """
    )
    d = dict(row) if row else {}
    fechadas = d.get("fechadas") or 0
    d["taxa_acerto"] = round((d.get("vitorias") or 0) / fechadas * 100, 1) if fechadas else 0.0
    d["resultado"] = round(d.get("resultado") or 0.0, 2)
    return d


# ── Pré-abertura ────────────────────────────────────────────────────────────
def salvar_pre_abertura(est: EstimativaPreAbertura) -> int:
    cur = db.execute(
        """
        INSERT INTO pre_abertura
            (ativo, valor_estimado, confianca, entradas_json, faltantes_json, fonte, coletado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            est.ativo,
            est.valor_estimado,
            est.confianca,
            json.dumps([e.to_dict() for e in est.entradas], ensure_ascii=False),
            json.dumps(est.faltantes, ensure_ascii=False),
            est.fonte,
            est.coletado_em,
        ),
    )
    return int(cur.lastrowid)


def ultima_pre_abertura(ativo: str) -> Optional[dict[str, Any]]:
    row = db.query_one(
        "SELECT * FROM pre_abertura WHERE ativo = ? ORDER BY coletado_em DESC LIMIT 1",
        (ativo,),
    )
    return dict(row) if row else None


def listar_pre_aberturas() -> list[dict[str, Any]]:
    rows = db.query(
        """
        SELECT p.* FROM pre_abertura p
        JOIN (SELECT ativo, MAX(coletado_em) AS ts FROM pre_abertura GROUP BY ativo) u
          ON u.ativo = p.ativo AND u.ts = p.coletado_em
        ORDER BY p.ativo
        """
    )
    return [dict(r) for r in rows]


# ── Serviços (heartbeat) ────────────────────────────────────────────────────
def heartbeat(servico: str, status: str = "ok", mensagem: Optional[str] = None, pid: Optional[int] = None) -> None:
    existente = db.query_one("SELECT iniciado_em FROM servico_status WHERE servico = ?", (servico,))
    iniciado_em = existente["iniciado_em"] if existente and existente["iniciado_em"] else db.iso()
    db.execute(
        """
        INSERT INTO servico_status (servico, status, mensagem, pid, iniciado_em, heartbeat_em)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(servico) DO UPDATE SET
            status = excluded.status,
            mensagem = excluded.mensagem,
            pid = excluded.pid,
            heartbeat_em = excluded.heartbeat_em
        """,
        (servico, status, mensagem, pid, iniciado_em, db.iso()),
    )


def listar_servicos() -> list[dict[str, Any]]:
    rows = db.query("SELECT * FROM servico_status ORDER BY servico")
    resultado = []
    for r in rows:
        d = dict(r)
        d["idade_segundos"] = db.idade_segundos(d.get("heartbeat_em"))
        resultado.append(d)
    return resultado


# ── Saúde do sistema ────────────────────────────────────────────────────────
def registrar_saude(
    cpu_pct: float,
    ram_pct: float,
    ram_usada_mb: float,
    disco_pct: float,
    internet_ok: bool,
    latencia_ms: Optional[float] = None,
    alerta: Optional[str] = None,
) -> int:
    cur = db.execute(
        """
        INSERT INTO saude
            (cpu_pct, ram_pct, ram_usada_mb, disco_pct, internet_ok, latencia_ms, alerta, coletado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (cpu_pct, ram_pct, ram_usada_mb, disco_pct, 1 if internet_ok else 0, latencia_ms, alerta, db.iso()),
    )
    return int(cur.lastrowid)


def ultima_saude() -> Optional[dict[str, Any]]:
    row = db.query_one("SELECT * FROM saude ORDER BY coletado_em DESC LIMIT 1")
    return dict(row) if row else None


def historico_saude(limite: int = 60) -> list[dict[str, Any]]:
    rows = db.query("SELECT * FROM saude ORDER BY coletado_em DESC LIMIT ?", (limite,))
    return [dict(r) for r in rows]


# ── Eventos ─────────────────────────────────────────────────────────────────
def registrar_evento(tipo: str, origem: str, payload: Optional[dict[str, Any]] = None) -> int:
    cur = db.execute(
        "INSERT INTO eventos (tipo, origem, payload_json, criado_em) VALUES (?, ?, ?, ?)",
        (tipo, origem, json.dumps(payload, ensure_ascii=False) if payload else None, db.iso()),
    )
    return int(cur.lastrowid)
