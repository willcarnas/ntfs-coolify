-- Schema do banco local (SQLite) do sistema de trading.
-- Toda tabela carrega auditoria de origem: `fonte` e `coletado_em` (secao 13).

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Cotações pontuais (snapshot por ciclo de coleta).
CREATE TABLE IF NOT EXISTS cotacoes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo             TEXT    NOT NULL,
    classe            TEXT    NOT NULL,      -- b3 | forex | cripto
    preco             REAL,
    abertura          REAL,
    maxima            REAL,
    minima            REAL,
    volume            REAL,
    variacao_pct      REAL,
    bid               REAL,
    ask               REAL,
    extra_json        TEXT,
    fonte             TEXT    NOT NULL,
    coletado_em       TEXT    NOT NULL       -- ISO-8601 UTC
);
CREATE INDEX IF NOT EXISTS idx_cotacoes_ativo_ts ON cotacoes (ativo, coletado_em DESC);
CREATE INDEX IF NOT EXISTS idx_cotacoes_classe_ts ON cotacoes (classe, coletado_em DESC);

-- Velas OHLCV usadas no cálculo de indicadores técnicos.
CREATE TABLE IF NOT EXISTS velas (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo             TEXT    NOT NULL,
    classe            TEXT    NOT NULL,
    timeframe         TEXT    NOT NULL,      -- 1d | 1h | 5m
    ts                TEXT    NOT NULL,      -- abertura da vela, ISO-8601 UTC
    abertura          REAL,
    maxima            REAL,
    minima            REAL,
    fechamento        REAL,
    volume            REAL,
    fonte             TEXT    NOT NULL,
    coletado_em       TEXT    NOT NULL,
    UNIQUE (ativo, timeframe, ts)
);
CREATE INDEX IF NOT EXISTS idx_velas_ativo_tf ON velas (ativo, timeframe, ts DESC);

-- Indicadores técnicos (último valor por ativo/timeframe/nome).
CREATE TABLE IF NOT EXISTS indicadores (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo             TEXT    NOT NULL,
    classe            TEXT    NOT NULL,
    timeframe         TEXT    NOT NULL,
    nome              TEXT    NOT NULL,      -- sma_20, rsi_14, macd, ...
    valor             REAL,
    fonte             TEXT,
    coletado_em       TEXT    NOT NULL,
    UNIQUE (ativo, timeframe, nome)
);
CREATE INDEX IF NOT EXISTS idx_indicadores_ativo ON indicadores (ativo);

-- Sinais gerados pelo motor de sinais.
CREATE TABLE IF NOT EXISTS sinais (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo                  TEXT    NOT NULL,
    classe                 TEXT    NOT NULL,
    tipo                   TEXT    NOT NULL,   -- compra | venda | observacao
    confianca              REAL    NOT NULL,   -- 0..1
    preco                  REAL,
    justificativa          TEXT,
    fatores_json           TEXT,               -- [{nome, valor, peso, contribuicao}]
    fontes_json            TEXT,               -- ["yfinance@ts", ...]
    dados_desatualizados   INTEGER NOT NULL DEFAULT 0,
    status                 TEXT    NOT NULL DEFAULT 'pendente', -- pendente|aprovado|bloqueado|enviado
    criado_em              TEXT    NOT NULL,
    UNIQUE (ativo, classe, tipo, criado_em)
);
CREATE INDEX IF NOT EXISTS idx_sinais_status ON sinais (status, criado_em DESC);

-- Fila de alertas consumida pelo serviço de Telegram.
CREATE TABLE IF NOT EXISTS fila_alertas (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    sinal_id          INTEGER,
    payload_json      TEXT    NOT NULL,
    status            TEXT    NOT NULL DEFAULT 'pendente', -- pendente|enviado|erro|bloqueado
    motivo_bloqueio   TEXT,
    tentativas        INTEGER NOT NULL DEFAULT 0,
    criado_em         TEXT    NOT NULL,
    atualizado_em     TEXT,
    FOREIGN KEY (sinal_id) REFERENCES sinais (id)
);
CREATE INDEX IF NOT EXISTS idx_fila_status ON fila_alertas (status, criado_em);

-- Notícias coletadas com classificação de sentimento.
CREATE TABLE IF NOT EXISTS noticias (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo            TEXT    NOT NULL,
    link              TEXT,
    resumo            TEXT,
    fonte             TEXT    NOT NULL,
    sentimento        TEXT,                  -- positivo | negativo | neutro
    score             REAL,
    publicado_em      TEXT,
    coletado_em       TEXT    NOT NULL,
    hash              TEXT    UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_noticias_ts ON noticias (coletado_em DESC);

-- Operações registradas manualmente pelo usuário (RF-12).
CREATE TABLE IF NOT EXISTS operacoes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo             TEXT    NOT NULL,
    classe            TEXT,
    lado              TEXT,                  -- compra | venda
    quantidade        REAL,
    preco_entrada     REAL    NOT NULL,
    preco_saida       REAL,
    sinal_id          INTEGER,
    status            TEXT    NOT NULL DEFAULT 'aberta', -- aberta | fechada
    resultado         REAL,
    resultado_pct     REAL,
    observacao        TEXT,
    aberta_em         TEXT    NOT NULL,
    fechada_em        TEXT,
    fonte             TEXT    NOT NULL DEFAULT 'manual',
    coletado_em       TEXT    NOT NULL,
    FOREIGN KEY (sinal_id) REFERENCES sinais (id)
);
CREATE INDEX IF NOT EXISTS idx_operacoes_status ON operacoes (status, aberta_em DESC);

-- Estimativa de preço justo de pré-abertura (RF-06).
CREATE TABLE IF NOT EXISTS pre_abertura (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ativo             TEXT    NOT NULL,
    valor_estimado    REAL,
    confianca         REAL,
    entradas_json     TEXT    NOT NULL,      -- [{nome, valor, fonte, peso, disponivel}]
    faltantes_json    TEXT,
    fonte             TEXT,
    coletado_em       TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pre_abertura_ts ON pre_abertura (ativo, coletado_em DESC);

-- Heartbeat / status de cada serviço (dashboard mostra staleness).
CREATE TABLE IF NOT EXISTS servico_status (
    servico           TEXT    PRIMARY KEY,
    status            TEXT    NOT NULL,      -- ok | degradado | erro | parado
    mensagem          TEXT,
    pid               INTEGER,
    iniciado_em       TEXT,
    heartbeat_em      TEXT    NOT NULL
);

-- Amostras de saúde do sistema (RF-14).
CREATE TABLE IF NOT EXISTS saude (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    cpu_pct           REAL,
    ram_pct           REAL,
    ram_usada_mb      REAL,
    disco_pct         REAL,
    internet_ok       INTEGER,
    latencia_ms       REAL,
    alerta            TEXT,
    coletado_em       TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_saude_ts ON saude (coletado_em DESC);

-- Log genérico de eventos / auditoria entre módulos.
CREATE TABLE IF NOT EXISTS eventos (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo              TEXT    NOT NULL,
    origem            TEXT    NOT NULL,
    payload_json      TEXT,
    criado_em         TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_eventos_tipo ON eventos (tipo, criado_em DESC);

-- Controle interno de circuit breaker persistente (opcional).
CREATE TABLE IF NOT EXISTS circuit_breaker (
    fonte             TEXT    PRIMARY KEY,
    estado            TEXT    NOT NULL DEFAULT 'fechado', -- fechado|aberto|meio_aberto
    falhas            INTEGER NOT NULL DEFAULT 0,
    aberto_em         TEXT,
    atualizado_em     TEXT    NOT NULL
);
