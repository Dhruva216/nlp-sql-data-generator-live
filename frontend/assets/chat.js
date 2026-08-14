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

  /* Progress bar — dynamically shows actual query context usage (prompt tokens) as % of context limit */
  const queryPromptTokens = usage ? usage.prompt_tokens : 0;
  const pct = Math.min((queryPromptTokens / MODEL_CONTEXT_LIMIT) * 100, 100);
  els.tokenBar.style.width = pct.toFixed(2) + "%";
  els.tokenBarPct.textContent = pct.toFixed(2) + "%";
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
  els.tokenBar.style.width = "0%";
  els.tokenBarPct.textContent = "0.00%";
  els.tokenBar.classList.remove("warn");
  els.tokenSessionTotal.textContent = "0";
  els.tokenLastQuery.textContent = "0";
  els.tokenQueryCount.textContent = "0";
  els.tokenLastPrompt.textContent = "0";
  els.tokenLastCompletion.textContent = "0";
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

function exportTableToExcel(btn) {
  const bubble = btn.closest(".bubble");
  if (!bubble) return;
  const table = bubble.querySelector("table.data-table");
  if (!table) return;

  const rows = [];
  table.querySelectorAll("tr").forEach((tr) => {
    const row = [];
    tr.querySelectorAll("th, td").forEach((td) => {
      let cellText = td.innerText.replace(/"/g, '""');
      row.push(`"${cellText}"`);
    });
    if (row.length > 0) {
      rows.push(row.join(","));
    }
  });

  const csvContent = "\ufeff" + rows.join("\r\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  link.setAttribute("href", url);
  link.setAttribute("download", `Report_Export_${timestamp}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function printReport(btn) {
  const msgDiv = btn.closest(".msg");
  if (!msgDiv) {
    window.print();
    return;
  }

  document.querySelectorAll(".msg.printing-target").forEach((el) => el.classList.remove("printing-target"));
  msgDiv.classList.add("printing-target");
  document.body.classList.add("printing-mode");

  window.print();

  document.body.classList.remove("printing-mode");
  msgDiv.classList.remove("printing-target");
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
    let metaText = "";
    if (data.database_ids_used?.length) {
      metaText += `Database: ${escapeHtml(data.database_ids_used.join(", "))}`;
    }
    if (data.llm_usage && data.llm_usage.total_tokens > 0) {
      if (metaText) metaText += " &nbsp;·&nbsp; ";
      metaText += `Tokens: <strong>${fmtNum(data.llm_usage.total_tokens)}</strong> (Prompt: ${fmtNum(data.llm_usage.prompt_tokens)} | Completion: ${fmtNum(data.llm_usage.completion_tokens)})`;
    }

    /* Collapsible SQL Query block — hidden by default, accessible via click */
    html += `
      <details class="sql-details">
        <summary class="sql-summary">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 5px;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
          View Generated SQL Query
        </summary>
        <pre class="sql-block">${escapeHtml(data.sql)}</pre>
        ${metaText ? `<p class="meta" style="margin-top: 0.4rem; padding: 0 0.75rem 0.5rem;">${metaText}</p>` : ""}
      </details>
    `;
  }

  if (data.column_names?.length && data.rows?.length) {
    html += `
      <div class="report-toolbar">
        <button type="button" class="action-btn excel-btn" onclick="exportTableToExcel(this)" title="Export report table to Excel (.csv)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Export to Excel
        </button>
        <button type="button" class="action-btn print-btn" onclick="printReport(this)" title="Print report or save as PDF">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
          Print Report
        </button>
      </div>
    `;
    html += renderTable(data.column_names, data.rows);
  } else if (data.sql) {
    html += `<p class="meta" style="color: var(--muted); font-style: italic; margin-top: 10px;">⚠️ Query executed successfully, but 0 matching records were found in the database.</p>`;
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

