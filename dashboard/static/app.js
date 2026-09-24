const REFRESH_MS = 30000;
let dadosAtuais = null;

function fmtNum(v, casas = 2) {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

function fmtIdade(seg) {
  if (seg === null || seg === undefined) return "—";
  if (seg < 60) return `${Math.round(seg)}s`;
  if (seg < 3600) return `${Math.round(seg / 60)}min`;
  if (seg < 86400) return `${Math.round(seg / 3600)}h`;
  return `${Math.round(seg / 86400)}d`;
}

function classeCor(classe) {
  return { b3: "#2563eb", forex: "#16a34a", cripto: "#f59e0b", macro: "#7c3aed" }[classe] || "#64748b";
}

function tipoCor(tipo) {
  return { compra: "#16a34a", venda: "#dc2626", observacao: "#64748b" }[tipo] || "#64748b";
}

async function carregar() {
  try {
    const resp = await fetch("/api/resumo");
    const dados = await resp.json();
    dadosAtuais = dados;
    render(dados);
    document.getElementById("ultima-atualizacao").textContent =
      "atualizado " + new Date().toLocaleTimeString("pt-BR");
  } catch (e) {
    document.getElementById("ultima-atualizacao").textContent = "falha ao atualizar";
    console.error(e);
  }
}

function render(d) {
  renderAviso(d);
  renderHumor(d.humor);
  renderSaudeTopo(d.saude);
  renderCotacoes(d.cotacoes, d.indicadores);
  renderPreAbertura(d.pre_abertura);
  renderSinais(d.sinais);
  renderNoticias(d.noticias);
  renderServicos(d.servicos);
  renderSaude(d.saude);
  renderOperacoes(d.operacoes, d.resumo_operacoes);
}

function renderAviso(d) {
  const el = document.getElementById("aviso-sistema");
  const fora = (d.servicos || []).filter((s) => s.desatualizado && s.servico !== "dashboard");
  if (!fora.length) {
    el.style.display = "none";
    return;
  }
  el.style.display = "block";
  el.textContent = "⚠ Módulos desatualizados/fora do ar: " + fora.map((s) => s.servico).join(", ");
}

function renderHumor(h) {
  if (!h) return;
  const rotulo = { positivo: "otimista", negativo: "pessimista", neutro: "neutro" }[h.rotulo] || h.rotulo;
  const el = document.getElementById("humor");
  el.textContent = `humor: ${rotulo} (${h.score >= 0 ? "+" : ""}${h.score})`;
  el.style.borderColor = tipoCor(h.rotulo === "positivo" ? "compra" : h.rotulo === "negativo" ? "venda" : "observacao");
}

function renderSaudeTopo(s) {
  const el = document.getElementById("saude-topo");
  if (!s) {
    el.textContent = "saúde: sem dados";
    return;
  }
  el.textContent = `CPU ${fmtNum(s.cpu_pct, 0)}% · RAM ${fmtNum(s.ram_pct, 0)}% · Disco ${fmtNum(s.disco_pct, 0)}%`;
}

function renderCotacoes(cotacoes, indicadores) {
  const el = document.getElementById("cotacoes");
  if (!cotacoes || !cotacoes.length) {
    el.innerHTML = "<p class='vazio'>Sem cotações coletadas ainda.</p>";
    return;
  }
  el.innerHTML = cotacoes
    .map((c) => {
      const varClasse = (c.variacao_pct || 0) >= 0 ? "positivo" : "negativo";
      const ind = (indicadores && indicadores[c.ativo]) || {};
      const rsi = ind.rsi_14 !== undefined ? fmtNum(ind.rsi_14, 1) : "—";
      const sma20 = ind.sma_20 !== undefined ? fmtNum(ind.sma_20, 2) : "—";
      return `
      <div class="card ${c.desatualizado ? "stale" : ""}">
        <div class="card-topo">
          <span class="ativo"><i style="background:${classeCor(c.classe)}"></i>${c.ativo}</span>
          <span class="classe">${c.classe}</span>
        </div>
        <div class="preco">${fmtNum(c.preco, c.classe === "forex" ? 4 : 2)}
          <span class="${varClasse}">${c.variacao_pct != null ? fmtNum(c.variacao_pct, 2) + "%" : ""}</span>
        </div>
        <div class="meta">RSI ${rsi} · SMA20 ${sma20}</div>
        <div class="fonte" title="${c.coletado_em}">fonte: ${c.fonte} · ${fmtIdade(c.idade_segundos)} atrás${c.desatualizado ? " ⚠" : ""}</div>
      </div>`;
    })
    .join("");
}

function renderPreAbertura(lista) {
  const el = document.getElementById("pre-abertura");
  if (!lista || !lista.length) {
    el.innerHTML = "<p class='vazio'>Sem estimativa de pré-abertura (aguardando dados de referência).</p>";
    return;
  }
  el.innerHTML = lista
    .map((p) => {
      const faltantes = (p.faltantes || []).length ? `<div class="fonte">faltando: ${p.faltantes.join(", ")}</div>` : "";
      const entradas = (p.entradas || [])
        .map((e) => `<li>${e.nome}: ${e.disponivel ? fmtNum(e.valor, 3) + "%" : "indisponível"} (peso ${e.peso})</li>`)
        .join("");
      return `
      <div class="card">
        <div class="card-topo"><span class="ativo">${p.ativo}</span>
          <span class="classe">conf ${fmtNum((p.confianca || 0) * 100, 0)}%</span></div>
        <div class="preco">${fmtNum(p.valor_estimado, 4)}</div>
        <ul class="entradas">${entradas}</ul>
        ${faltantes}
        <div class="fonte">atualizado ${fmtIdade(p.idade_segundos)} atrás</div>
      </div>`;
    })
    .join("");
}

function renderSinais(sinais) {
  const el = document.getElementById("sinais");
  if (!sinais || !sinais.length) {
    el.innerHTML = "<p class='vazio'>Nenhum sinal de compra/venda gerado ainda.</p>";
    return;
  }
  el.innerHTML = sinais
    .map((s) => {
      const conf = Math.round((s.confianca || 0) * 100);
      const fatores = (s.fatores || [])
        .map((f) => `<li>${f.descricao || f.nome} <span class="peso">[${f.contribuicao >= 0 ? "+" : ""}${f.contribuicao}]</span></li>`)
        .join("");
      return `
      <div class="sinal" style="border-left-color:${tipoCor(s.tipo)}">
        <div class="sinal-topo">
          <span class="tipo" style="color:${tipoCor(s.tipo)}">${s.tipo.toUpperCase()}</span>
          <span class="ativo-sinal">${s.ativo} <small>(${s.classe})</small></span>
          <span class="status status-${s.status}">${s.status}</span>
          <span class="quando">${fmtIdade(s.idade_segundos)} atrás</span>
        </div>
        <div class="barra"><div style="width:${conf}%;background:${tipoCor(s.tipo)}"></div></div>
        <div class="conf">confiança ${conf}% · preço ${fmtNum(s.preco, 4)}</div>
        <ul class="fatores">${fatores}</ul>
        <div class="fontes">fontes: ${(s.fontes || []).join(", ")}${s.dados_desatualizados ? " ⚠ desatualizado" : ""}</div>
      </div>`;
    })
    .join("");
}

function renderNoticias(noticias) {
  const el = document.getElementById("noticias");
  if (!noticias || !noticias.length) {
    el.innerHTML = "<p class='vazio'>Sem notícias coletadas.</p>";
    return;
  }
  el.innerHTML = noticias
    .map(
      (n) => `
      <div class="noticia sent-${n.sentimento || "neutro"}">
        <a href="${n.link || "#"}" target="_blank" rel="noopener">${n.titulo}</a>
        <div class="meta">${n.fonte} · ${(n.sentimento || "neutro")} (${fmtNum(n.score, 2)})</div>
      </div>`
    )
    .join("");
}

function renderServicos(servicos) {
  const el = document.getElementById("servicos");
  if (!servicos || !servicos.length) {
    el.innerHTML = "<p class='vazio'>Nenhum serviço reportou heartbeat.</p>";
    return;
  }
  el.innerHTML = servicos
    .map((s) => {
      const cor = s.desatualizado ? "#dc2626" : s.status === "ok" ? "#16a34a" : "#f59e0b";
      return `<div class="servico">
        <span class="dot" style="background:${cor}"></span>
        <span class="nome-servico">${s.servico}</span>
        <span class="estado">${s.desatualizado ? "desatualizado" : s.status}</span>
        <span class="quando">${fmtIdade(s.idade_segundos)}</span>
      </div>`;
    })
    .join("");
}

function barra(nome, valor) {
  const pct = Math.max(0, Math.min(100, Number(valor) || 0));
  const cor = pct > 90 ? "#dc2626" : pct > 70 ? "#f59e0b" : "#16a34a";
  return `<div class="recurso"><span>${nome}</span>
    <div class="barra-rec"><div style="width:${pct}%;background:${cor}"></div></div>
    <span>${fmtNum(pct, 0)}%</span></div>`;
}

function renderSaude(s) {
  const el = document.getElementById("saude");
  if (!s) {
    el.innerHTML = "<p class='vazio'>Sem dados de saúde (monitor não executado).</p>";
    return;
  }
  el.innerHTML =
    barra("CPU", s.cpu_pct) +
    barra("RAM", s.ram_pct) +
    barra("Disco", s.disco_pct) +
    `<div class="recurso"><span>Internet</span><span>${s.internet_ok ? "ok" : "off"}</span>
      <span>${s.latencia_ms != null ? fmtNum(s.latencia_ms, 0) + "ms" : ""}</span></div>` +
    (s.alerta ? `<div class="alerta-saude">${s.alerta}</div>` : "");
}

function renderOperacoes(ops, resumo) {
  const rEl = document.getElementById("resumo-operacoes");
  if (resumo) {
    const cor = (resumo.resultado || 0) >= 0 ? "positivo" : "negativo";
    rEl.innerHTML = `Total ${resumo.total || 0} · abertas ${resumo.abertas || 0} · fechadas ${resumo.fechadas || 0} ·
      resultado <b class="${cor}">${fmtNum(resumo.resultado, 2)}</b> · acerto ${fmtNum(resumo.taxa_acerto, 1)}%`;
  }
  const el = document.getElementById("operacoes");
  if (!ops || !ops.length) {
    el.innerHTML = "<p class='vazio'>Nenhuma operação registrada.</p>";
    return;
  }
  el.innerHTML = ops
    .map((o) => {
      const res = o.resultado != null ? `<b class="${o.resultado >= 0 ? "positivo" : "negativo"}">${fmtNum(o.resultado, 2)}</b>` : "—";
      const acao =
        o.status === "aberta"
          ? `<button onclick="fecharOperacao(${o.id})">Fechar</button>`
          : "";
      return `<div class="operacao">
        <span>#${o.id}</span>
        <span>${o.ativo}</span>
        <span>${o.lado}</span>
        <span>${fmtNum(o.preco_entrada, 4)} → ${o.preco_saida != null ? fmtNum(o.preco_saida, 4) : "aberta"}</span>
        <span>${res}</span>
        <span class="status status-${o.status}">${o.status}</span>
        ${acao}
      </div>`;
    })
    .join("");
}

async function registrarOperacao(ev) {
  ev.preventDefault();
  const f = ev.target;
  const corpo = {
    ativo: f.ativo.value,
    preco_entrada: parseFloat(f.preco_entrada.value),
    quantidade: parseFloat(f.quantidade.value || "1"),
    lado: f.lado.value,
  };
  await fetch("/api/operacoes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  });
  f.reset();
  carregar();
}

async function fecharOperacao(id) {
  const preco = prompt("Preço de saída:");
  if (preco === null || preco === "") return;
  await fetch(`/api/operacoes/${id}/fechar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ preco_saida: parseFloat(preco.replace(",", ".")) }),
  });
  carregar();
}

carregar();
setInterval(carregar, REFRESH_MS);
