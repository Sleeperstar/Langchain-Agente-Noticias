"use strict";

const $ = (sel) => document.querySelector(sel);
const NODE_LABELS = {
  researcher: "Buscar noticias",
  history_filter: "Filtrar repetidas",
  evaluator: "Evaluar",
  ranker: "Rankear",
  summarizer: "Resumir + concepto + chiste",
  email_writer: "Armar correo",
};

let NODES = [];
let topicIndex = null;

document.addEventListener("DOMContentLoaded", init);

async function init() {
  try {
    const cfg = await fetch("/api/config").then((r) => r.json());
    NODES = cfg.nodes || [];
    if (cfg.recipients && cfg.recipients.length) {
      $("#hero").querySelector(".hint").textContent =
        "Destinatarios: " + cfg.recipients.join(", ");
    }
  } catch (e) {
    /* ignore */
  }

  $("#btn-generate").addEventListener("click", generate);
  $("#btn-joke").addEventListener("click", regenJoke);
  $("#btn-concept").addEventListener("click", regenConcept);
  $("#btn-concept-custom").addEventListener("click", customConcept);
  $("#btn-preview").addEventListener("click", openPreview);
  $("#btn-send").addEventListener("click", sendEmail);
  $("#btn-close-preview").addEventListener("click", () => $("#preview-modal").classList.add("hidden"));
  $("#btn-close-topic").addEventListener("click", () => $("#topic-modal").classList.add("hidden"));
  $("#btn-topic-search").addEventListener("click", doTopicSearch);
}

/* ----------------------------- Generacion ----------------------------- */
function renderFlowNodes() {
  const cont = $("#flow-nodes");
  cont.innerHTML = "";
  NODES.forEach((n, i) => {
    if (i > 0) {
      const arr = document.createElement("span");
      arr.className = "flow-arrow";
      arr.textContent = "\u2192";
      cont.appendChild(arr);
    }
    const el = document.createElement("div");
    el.className = "flow-node";
    el.id = "node-" + n;
    el.innerHTML = `<span class="dot"></span><span>${NODE_LABELS[n] || n}</span>`;
    cont.appendChild(el);
  });
}

function setNodeState(name, state) {
  const el = $("#node-" + name);
  if (el) el.className = "flow-node " + state;
}

function flowLog(msg) {
  const log = $("#flow-log");
  log.textContent += msg + "\n";
  log.scrollTop = log.scrollHeight;
}

function generate() {
  $("#hero").classList.add("hidden");
  $("#draft").classList.add("hidden");
  $("#flow").classList.remove("hidden");
  renderFlowNodes();
  $("#flow-log").textContent = "";

  // Marca el primer nodo como corriendo.
  if (NODES.length) setNodeState(NODES[0], "running");

  const es = new EventSource("/api/generate/stream");
  let lastDoneIdx = -1;

  es.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === "start") {
      flowLog("Iniciando flujo de agentes...");
    } else if (data.type === "node") {
      const idx = NODES.indexOf(data.node);
      setNodeState(data.node, "done");
      flowLog("\u2713 " + (NODE_LABELS[data.node] || data.node));
      lastDoneIdx = Math.max(lastDoneIdx, idx);
      if (idx >= 0 && idx + 1 < NODES.length) {
        setNodeState(NODES[idx + 1], "running");
      }
    } else if (data.type === "error") {
      flowLog("ERROR: " + data.message);
      toast("Error generando el borrador: " + data.message, "err");
      es.close();
    } else if (data.type === "done") {
      es.close();
      flowLog("Borrador listo.");
      renderDraft(data.draft);
    }
  };

  es.onerror = () => {
    es.close();
  };
}

/* ----------------------------- Render borrador ----------------------------- */
function renderDraft(draft) {
  if (!draft || !draft.ready) {
    toast("No se pudo armar el borrador (sin noticias).", "err");
    return;
  }
  $("#draft").classList.remove("hidden");

  if (draft.run_id) {
    $("#langsmith-link").href =
      "https://smith.langchain.com/o/projects?searchModel=" + encodeURIComponent(draft.run_id);
  }

  $("#headline").textContent = draft.headline || "";
  const tldr = $("#tldr");
  tldr.innerHTML = "";
  (draft.tldr || []).forEach((b) => {
    const li = document.createElement("li");
    li.textContent = b;
    tldr.appendChild(li);
  });

  renderConcept(draft.concepto_titulo, draft.concepto_explicacion);

  $("#joke").textContent = draft.chiste || "";
  renderArticles(draft.articles || [], draft.pool_remaining);

  $("#draft").scrollIntoView({ behavior: "smooth" });
}

function renderArticles(articles, poolRemaining) {
  const cont = $("#articles");
  cont.innerHTML = "";
  articles.forEach((a) => {
    const card = document.createElement("div");
    card.className = "article";
    const pubd = a.published_date ? " &middot; " + escapeHtml(a.published_date) : "";
    const noPool = poolRemaining <= 0;
    card.innerHTML = `
      <span class="cat">${escapeHtml(a.category || "")}</span>
      <h3><a href="${escapeAttr(a.url)}" target="_blank" rel="noreferrer">${escapeHtml(a.title)}</a></h3>
      <div class="src">${escapeHtml(a.source || "fuente")}${pubd}</div>
      <p>${escapeHtml(a.summary_es || "")}</p>
      <div class="ensimple"><b>En simple:</b> ${escapeHtml(a.en_simple || "")}</div>
      <div class="relrow">
        <span class="lbl">Relevancia</span>
        <div class="reltrack"><div class="relfill" style="width:${(a.relevance_score || 0) * 10}%"></div></div>
        <span class="val">${a.relevance_score}/10</span>
      </div>
      <div class="article-actions">
        <button class="btn btn-ghost btn-mini" data-act="auto" data-i="${a.index}" ${noPool ? "title='Sin candidatos en cola; usa cambiar por tema'" : ""}>Regenerar con otra noticia</button>
        <button class="btn btn-ghost btn-mini" data-act="topic" data-i="${a.index}">Cambiar por un tema...</button>
      </div>
    `;
    cont.appendChild(card);
  });

  cont.querySelectorAll("button[data-act]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const i = parseInt(btn.dataset.i, 10);
      if (btn.dataset.act === "auto") regenAuto(i, btn);
      else openTopic(i);
    });
  });
}

/* ----------------------------- Acciones de edicion ----------------------------- */
async function regenAuto(index, btn) {
  setLoading(btn, true, "Buscando...");
  try {
    const res = await fetch(`/api/article/${index}/regenerate`, { method: "POST" }).then((r) => r.json());
    if (res.ok) {
      renderDraft(res.draft);
      toast("Noticia cambiada.", "ok");
    } else {
      toast(res.error || "No se pudo cambiar.", "err");
    }
  } catch (e) {
    toast("Error: " + e, "err");
  } finally {
    setLoading(btn, false);
  }
}

function openTopic(index) {
  topicIndex = index;
  $("#topic-input").value = "";
  $("#topic-status").textContent = "";
  $("#topic-modal").classList.remove("hidden");
  $("#topic-input").focus();
}

async function doTopicSearch() {
  const topic = $("#topic-input").value.trim();
  if (!topic) {
    $("#topic-status").textContent = "Escribe un tema.";
    return;
  }
  const btn = $("#btn-topic-search");
  setLoading(btn, true, "Buscando...");
  $("#topic-status").textContent = "Buscando y evaluando...";
  try {
    const res = await fetch(`/api/article/${topicIndex}/replace`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic }),
    }).then((r) => r.json());
    if (res.ok) {
      $("#topic-modal").classList.add("hidden");
      renderDraft(res.draft);
      toast("Seccion actualizada con el tema pedido.", "ok");
    } else {
      $("#topic-status").textContent = res.error || "No se pudo reemplazar.";
    }
  } catch (e) {
    $("#topic-status").textContent = "Error: " + e;
  } finally {
    setLoading(btn, false);
  }
}

function renderConcept(titulo, exp) {
  $("#concepto-titulo").textContent = titulo || "";
  $("#concepto-exp").textContent = exp || "";
}

async function regenConcept() {
  const btn = $("#btn-concept");
  setLoading(btn, true, "Generando...");
  try {
    const res = await fetch("/api/concept/regenerate", { method: "POST" }).then((r) => r.json());
    if (res.ok) {
      renderConcept(res.concepto_titulo, res.concepto_explicacion);
      toast("Concepto nuevo (sin repetir los anteriores).", "ok");
    } else {
      toast(res.error || "No se pudo regenerar.", "err");
    }
  } catch (e) {
    toast("Error: " + e, "err");
  } finally {
    setLoading(btn, false);
  }
}

async function customConcept() {
  const topic = $("#concept-input").value.trim();
  if (!topic) {
    toast("Escribe un concepto o tema.", "err");
    return;
  }
  const btn = $("#btn-concept-custom");
  setLoading(btn, true, "Generando...");
  try {
    const res = await fetch("/api/concept/custom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic }),
    }).then((r) => r.json());
    if (res.ok) {
      renderConcept(res.concepto_titulo, res.concepto_explicacion);
      $("#concept-input").value = "";
      toast("Concepto actualizado con tu tema.", "ok");
    } else {
      toast(res.error || "No se pudo generar.", "err");
    }
  } catch (e) {
    toast("Error: " + e, "err");
  } finally {
    setLoading(btn, false);
  }
}

async function regenJoke() {
  const btn = $("#btn-joke");
  setLoading(btn, true, "Generando...");
  try {
    const res = await fetch("/api/joke/regenerate", { method: "POST" }).then((r) => r.json());
    if (res.ok) {
      $("#joke").textContent = res.chiste;
      toast("Chiste nuevo (sin repetir los anteriores).", "ok");
    } else {
      toast(res.error || "No se pudo regenerar.", "err");
    }
  } catch (e) {
    toast("Error: " + e, "err");
  } finally {
    setLoading(btn, false);
  }
}

/* ----------------------------- Preview y envio ----------------------------- */
function openPreview() {
  $("#preview-frame").src = "/api/preview?t=" + Date.now();
  $("#preview-modal").classList.remove("hidden");
}

async function sendEmail() {
  if (!confirm("Enviar el correo a los directivos ahora?")) return;
  const btn = $("#btn-send");
  setLoading(btn, true, "Enviando...");
  $("#send-status").textContent = "";
  try {
    const res = await fetch("/api/send", { method: "POST" }).then((r) => r.json());
    if (res.ok) {
      $("#send-status").textContent = res.result + (res.briefing_id ? " (guardado en historial)" : "");
      toast("Correo enviado.", "ok");
      btn.disabled = true;
    } else {
      $("#send-status").textContent = res.error || "No se pudo enviar.";
      toast(res.error || "No se pudo enviar.", "err");
    }
  } catch (e) {
    toast("Error: " + e, "err");
  } finally {
    if (!$("#btn-send").disabled) setLoading(btn, false);
  }
}

/* ----------------------------- Utilidades ----------------------------- */
function setLoading(btn, loading, text) {
  if (!btn) return;
  if (loading) {
    btn.dataset.label = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span>${text || "..."}`;
  } else {
    btn.disabled = false;
    if (btn.dataset.label) btn.innerHTML = btn.dataset.label;
  }
}

let toastTimer = null;
function toast(msg, kind) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast " + (kind || "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 4000);
}

function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function escapeAttr(s) {
  return escapeHtml(s).replace(/"/g, "&quot;");
}
