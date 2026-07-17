/**
 * Chat UI — talks ONLY to backend APIs (/v1/auth, /v1/nlp).
 * No database connection strings or drivers in the browser.
 */

const STORAGE_KEY = "nlp_sql_chat";

/* ── Cumulative token tracking ── */
let sessionTokens = { prompt: 0, completion: 0, total: 0, queryCount: 0 };
const MODEL_CONTEXT_LIMIT = 131072; // Gemma 4 31B context window (128K)
const MODEL_DISPLAY_NAME = "gemma4:31b-cloud";

const els = {
  apiBase: document.getElementById("apiBase"),
  clientId: document.getElementById("clientId"),
  clientSecret: document.getElementById("clientSecret"),
  connectBtn: document.getElementById("connectBtn"),
  connectError: document.getElementById("connectError"),
  connectPanel: document.getElementById("connectPanel"),
  statusPanel: document.getElementById("statusPanel"),
  disconnectBtn: document.getElementById("disconnectBtn"),
  chatSubtitle: document.getElementById("chatSubtitle"),
  messages: document.getElementById("messages"),
  welcome: document.getElementById("welcome"),
  composerForm: document.getElementById("composerForm"),
  questionInput: document.getElementById("questionInput"),
  sendBtn: document.getElementById("sendBtn"),
  /* Token panel */
  tokenPanel: document.getElementById("tokenPanel"),
  tokenModelName: document.getElementById("tokenModelName"),
  tokenContextLimit: document.getElementById("tokenContextLimit"),
  tokenBar: document.getElementById("tokenBar"),
  tokenBarPct: document.getElementById("tokenBarPct"),
  tokenSessionTotal: document.getElementById("tokenSessionTotal"),
  tokenLastQuery: document.getElementById("tokenLastQuery"),
  tokenQueryCount: document.getElementById("tokenQueryCount"),
  tokenDetailRow: document.getElementById("tokenDetailRow"),
  tokenLastPrompt: document.getElementById("tokenLastPrompt"),
  tokenLastCompletion: document.getElementById("tokenLastCompletion"),
};

function fmtNum(n) {
  return n.toLocaleString();
}

function updateTokenPanel(usage) {
  if (usage && usage.total_tokens > 0) {
    sessionTokens.prompt += usage.prompt_tokens;
    sessionTokens.completion += usage.completion_tokens;
    sessionTokens.total += usage.total_tokens;
    sessionTokens.queryCount += 1;
  }

  els.tokenModelName.textContent = MODEL_DISPLAY_NAME;
  els.tokenContextLimit.textContent = fmtNum(MODEL_CONTEXT_LIMIT) + " tokens";

  els.tokenSessionTotal.textContent = fmtNum(sessionTokens.total);
  els.tokenLastQuery.textContent = usage ? fmtNum(usage.total_tokens) : "0";
  els.tokenQueryCount.textContent = sessionTokens.queryCount;

  /* Progress bar — shows the LAST query's prompt tokens as a % of context window */
  const lastPrompt = usage ? usage.prompt_tokens : 0;
  const pct = Math.min((lastPrompt / MODEL_CONTEXT_LIMIT) * 100, 100);
  els.tokenBar.style.width = pct.toFixed(2) + "%";
  els.tokenBarPct.textContent = pct.toFixed(1) + "%";
  els.tokenBar.classList.toggle("warn", pct > 75);
  els.tokenBarPct.style.color = pct > 75 ? "var(--error)" : "var(--accent)";

  /* Detail breakdown */
  if (usage && usage.total_tokens > 0) {
    els.tokenDetailRow.hidden = false;
    els.tokenLastPrompt.textContent = fmtNum(usage.prompt_tokens);
    els.tokenLastCompletion.textContent = fmtNum(usage.completion_tokens);
  }
}

function resetTokenPanel() {
  sessionTokens = { prompt: 0, completion: 0, total: 0, queryCount: 0 };
  els.tokenPanel.hidden = true;
  els.tokenBar.style.width = "0%";
  els.tokenBarPct.textContent = "0%";
  els.tokenBar.classList.remove("warn");
  els.tokenSessionTotal.textContent = "0";
  els.tokenLastQuery.textContent = "0";
  els.tokenQueryCount.textContent = "0";
  els.tokenDetailRow.hidden = true;
}

function loadState() {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveState(partial) {
  const next = { ...loadState(), ...partial };
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
}

function apiBase() {
  const base = (els.apiBase.value || window.location.origin).replace(/\/$/, "");
  return base;
}

function getToken() {
  return loadState().accessToken || null;
}

function setConnected(connected) {
  els.connectPanel.hidden = connected;
  els.statusPanel.hidden = !connected;
  els.questionInput.disabled = !connected;
  els.sendBtn.disabled = !connected;
  els.chatSubtitle.textContent = connected
    ? "Ask about your data — answers run through the secure API"
    : "Connect to start asking about your data";
  if (connected) {
    els.tokenPanel.hidden = false;
    updateTokenPanel(null);
  }
}

function showConnectError(msg) {
  els.connectError.hidden = !msg;
  els.connectError.textContent = msg || "";
}

async function fetchJson(path, options = {}) {
  const res = await fetch(`${apiBase()}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
          : `Request failed (${res.status})`;
    throw new Error(message);
  }
  return data;
}

async function connect() {
  showConnectError("");
  els.connectBtn.disabled = true;
  try {
    const data = await fetchJson("/v1/auth/token", {
      method: "POST",
      body: JSON.stringify({
        client_id: els.clientId.value.trim(),
        client_secret: els.clientSecret.value,
      }),
    });
    saveState({
      accessToken: data.access_token,
      apiBase: apiBase(),
      clientId: els.clientId.value.trim(),
    });
    resetTokenPanel();
    setConnected(true);
    appendMessage(
      "assistant",
      "You're connected. Ask a question about your data — I'll query through the API (read-only)."
    );
  } catch (e) {
    showConnectError(e.message);
  } finally {
    els.connectBtn.disabled = false;
  }
}

function disconnect() {
  sessionStorage.removeItem(STORAGE_KEY);
  setConnected(false);
  clearMessages();
  resetTokenPanel();
  els.welcome.hidden = false;
}

function clearMessages() {
  els.messages.querySelectorAll(".msg").forEach((n) => n.remove());
}

function appendMessage(role, html, extraClass = "") {
  els.welcome.hidden = true;
  const wrap = document.createElement("div");
  wrap.className = `msg ${role} ${extraClass}`.trim();
  wrap.innerHTML = `<div class="bubble">${html}</div>`;
  els.messages.appendChild(wrap);
  els.messages.scrollTop = els.messages.scrollHeight;
  return wrap;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderTable(columns, rows) {
  if (!columns?.length) {
    return "<p class=\"meta\">No rows returned.</p>";
  }
  const head = columns.map((c) => `<th>${escapeHtml(c)}</th>`).join("");
  const body = rows
    .map(
      (row) =>
        `<tr>${columns.map((c) => `<td>${escapeHtml(row[c] ?? "")}</td>`).join("")}</tr>`
    )
    .join("");
  return `<div class="data-table-wrap"><table class="data-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function renderAssistantResponse(data) {
  let html = "";
  if (data.explanation) {
    html += `<p>${escapeHtml(data.explanation)}</p>`;
  } else if (data.sql) {
    html += `<p>Here are the results from your query.</p>`;
  } else {
    html += `<p>${escapeHtml(data.explanation || "No SQL was generated.")}</p>`;
  }
  if (data.sql) {
    html += `<pre class="sql-block">${escapeHtml(data.sql)}</pre>`;
    let metaText = "";
    if (data.database_ids_used?.length) {
      metaText += `Database: ${escapeHtml(data.database_ids_used.join(", "))}`;
    }
    if (data.llm_usage && data.llm_usage.total_tokens > 0) {
      if (metaText) metaText += " &nbsp;·&nbsp; ";
      metaText += `Tokens: <strong>${fmtNum(data.llm_usage.total_tokens)}</strong> (Prompt: ${fmtNum(data.llm_usage.prompt_tokens)} | Completion: ${fmtNum(data.llm_usage.completion_tokens)})`;
    }
    if (metaText) {
      html += `<p class="meta">${metaText}</p>`;
    }
  }
  if (data.column_names?.length) {
    html += renderTable(data.column_names, data.rows || []);
  }
  return html;
}

async function sendQuestion(text) {
  const token = getToken();
  if (!token) {
    showConnectError("Connect first.");
    return;
  }

  appendMessage("user", `<p>${escapeHtml(text)}</p>`);
  const loading = appendMessage("assistant", "<p>Thinking…</p>", "loading");

  try {
    const data = await fetchJson("/v1/nlp/query", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ text }),
    });
    loading.remove();
    appendMessage("assistant", renderAssistantResponse(data));

    /* Update the cumulative token panel */
    if (data.llm_usage) {
      updateTokenPanel(data.llm_usage);
    }
  } catch (e) {
    loading.remove();
    appendMessage("assistant", `<p>${escapeHtml(e.message)}</p>`, "error");
  }
}

function init() {
  const state = loadState();
  els.apiBase.value = state.apiBase || window.location.origin;
  if (state.clientId) els.clientId.value = state.clientId;

  if (state.accessToken) {
    setConnected(true);
  } else {
    setConnected(false);
  }

  els.connectBtn.addEventListener("click", connect);
  els.disconnectBtn.addEventListener("click", disconnect);

  els.composerForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = els.questionInput.value.trim();
    if (!text) return;
    els.questionInput.value = "";
    sendQuestion(text);
  });

  els.questionInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      els.composerForm.requestSubmit();
    }
  });
}

init();

