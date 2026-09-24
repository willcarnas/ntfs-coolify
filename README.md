# TradingSystemWCN

Sistema pessoal de **suporte à decisão** para trading de opções na B3, forex e
cripto — implementação do PRD (`prd.md`). Coleta dados gratuitos, calcula
indicadores, estima pré-abertura, gera sinais explicáveis, filtra por risco,
alerta no Telegram e exibe tudo em uma dashboard web local.

> A execução das ordens é **manual**. O sistema apenas monitora, recomenda e
> registra. Nenhuma dependência paga na Fase 1.

## Arquitetura (isolamento de processos)

Cada domínio roda como processo independente e se comunica **apenas via banco
SQLite compartilhado** (nunca por import de outro domínio):

```
b3  forex  cripto  noticias      -> gravam cotações/velas/notícias no banco
        |            |
        v            v
   [ SQLite: data/trading.db ]
        |
   sinais  -> calcula indicadores + pré-abertura + gera sinais (status=pendente)
        |
   risco   -> aprova/bloqueia e enfileira alertas (fila_alertas)
        |
   telegram (consumidor)                dashboard (consumidor somente-leitura)
```

A pasta `comum/` é a **biblioteca compartilhada** (db, logger, circuit breaker,
contratos de dados, indicadores puros). É a única importação permitida entre
módulos.

## Estrutura

```
comum/        biblioteca compartilhada (schema.sql, db, repo, indica., breaker)
b3/           coleta B3 (mercados -> brapi -> yfinance) + macro BCB
forex/        coleta MT5 (com feed simulado claramente marcado quando ausente)
cripto/       coleta ccxt (OHLCV + fluxo do livro de ofertas)
noticias/     RSS -> scraping + sentimento
sinais/       indicadores + pré-abertura + regras de sinal (puro/testável)
risco/        regras de risco (puro/testável)
telegram/     envio de alertas + comandos (/entrada, /saida, /status)
dashboard/    FastAPI + frontend vanilla (somente leitura)
scripts/      run_all, setup, install_servicos (NSSM), backup, monitor_saude,
              verificar_isolamento
tests/        pytest (indicadores, sinais, risco, repo, isolamento)
docs/         data_sources.md, licensing.md
config/       dashboard.json
data/         banco + backups (ignorados no git)
logs/         logs por módulo
```

## Instalação rápida (Windows)

```powershell
# 1) Ambiente (cria .venv e instala dependências)
pwsh -File scripts\setup.ps1

# 2) Configuração (opcional: Telegram, token brapi)
Copy-Item .env.example .env
#   edite .env com TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID / BRAPI_TOKEN

# 3) Testes
.\.venv\Scripts\python.exe -m pytest tests -q

# 4) Subir todos os serviços (dev)
.\.venv\Scripts\python.exe scripts\run_all.py
```

A dashboard fica em **http://localhost:8080** (ou `http://<ip-do-mini-pc>:8080`
na rede local).

Para rodar um único conector manualmente (validação isolada, PRD secao 13):

```powershell
$env:TRADING_ONESHOT="1"; .\.venv\Scripts\python.exe b3\main.py
```

## Serviços Windows (produção, NSSM)

```powershell
# em PowerShell como Administrador
pwsh -File scripts\install_servicos.ps1 -Iniciar
```

Instala `ModuloB3`, `ModuloForex`, `ModuloCripto`, `ModuloNoticias`,
`MonitorSaude`, `MotorSinais`, `MotorRisco`, `ServicoTelegram`, `DashboardWeb`
como serviços independentes, com `SERVICE_AUTO_START` e reinício em falha. Usa
venv por módulo se existir (`scripts\setup.ps1 -Mode PerModule`), senão o `.venv`.

## Backup (RF-13)

```powershell
.\.venv\Scripts\python.exe scripts\backup_diario.py --retencao-dias 7
```

Agende no Agendador de Tarefas do Windows para rodar 1x/dia.

## Teste de isolamento (PRD secao 5.3)

```powershell
pwsh -File scripts\verificar_isolamento.ps1
```

Sobe tudo, **mata apenas o módulo cripto** e confirma que a dashboard continua
respondendo e passa a marcar o cripto como desatualizado. Também há a versão
automatizada: `tests/test_isolamento_cripto.py`.

## Requisitos funcionais cobertos

| RF | Descrição | Módulo |
|---|---|---|
| RF-01 | Coleta B3 | `b3` |
| RF-02 | Coleta Forex (MT5) | `forex` |
| RF-03 | Coleta cripto | `cripto` |
| RF-04 | Indicadores técnicos | `sinais` / `comum.indicadores` |
| RF-05 | Análise de fluxo (básico) | `cripto` (orderbook) |
| RF-06 | Pré-abertura | `sinais/pre_abertura.py` |
| RF-07 | Notícias + sentimento | `noticias` |
| RF-08 | Motor de sinais | `sinais` |
| RF-09 | Motor de risco | `risco` |
| RF-10 | Alertas Telegram | `telegram` |
| RF-11 | Dashboard web | `dashboard` |
| RF-12 | Registro manual de operações | `dashboard` + `telegram` |
| RF-13 | Backup | `scripts/backup_diario.py` |
| RF-14 | Saúde do sistema | `scripts/monitor_saude.py` |

## Transparência da fonte

Toda tabela carrega `fonte` e `coletado_em`. A dashboard exibe a origem e a
idade de cada dado e sinaliza (com aviso visual) quando um módulo está fora do
ar — sem preencher lacunas silenciosamente. O módulo de pré-abertura registra
quais entradas faltaram e reduz a confiança proporcionalmente.

## Degradação graciosa

- **Sem MT5**: o forex usa feed `simulado` (marcado como tal em `fonte`), para
  validar o pipeline até o terminal ser instalado.
- **Sem Telegram**: alertas permanecem em `fila_alertas`, visíveis na dashboard.
- **Fonte fora do ar**: circuit breaker por fonte evita tentativas contínuas.

## Documentação adicional

- `docs/data_sources.md` — status real de cada fonte (documento vivo).
- `docs/licensing.md` — licenças e conformidade.
- `prd.md` — especificação de referência.
