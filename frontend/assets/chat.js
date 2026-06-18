/**
 * Chat UI — talks ONLY to backend APIs (/v1/auth, /v1/nlp).
 * No database connection strings or drivers in the browser.
 */

const STORAGE_KEY = "nlp_sql_chat";

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
};

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
    if (data.database_ids_used?.length) {
      html += `<p class="meta">Database: ${escapeHtml(data.database_ids_used.join(", "))}</p>`;
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
