function qs(id) {
  return document.getElementById(id);
}

function getDatesQuery() {
  const start = qs("start-date")?.value || "";
  const end = qs("end-date")?.value || "";
  const params = new URLSearchParams();
  if (start) params.set("start_date", start);
  if (end) params.set("end_date", end);
  const q = params.toString();
  return q ? `?${q}` : "";
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("ru-RU");
  } catch {
    return iso;
  }
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body?.detail ? String(body.detail) : "";
    } catch {}
    const err = new Error(detail || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return await res.json();
}

async function login() {
  qs("login-error").textContent = "";
  const password = qs("password-input").value || "";
  try {
    await api("/api/login", { method: "POST", body: JSON.stringify({ password }) });
    qs("login-screen").style.display = "none";
    qs("main-panel").style.display = "block";
    await reloadAll();
  } catch (e) {
    qs("login-error").textContent = "Неверный пароль или ошибка входа.";
  }
}

async function logout() {
  try {
    await api("/api/logout", { method: "POST" });
  } finally {
    location.reload();
  }
}

async function reloadAll() {
  await Promise.all([loadStats(), loadUsers(), loadStaff()]);
}

async function loadStats() {
  const q = getDatesQuery();
  const stats = await api(`/api/statistics${q}`);
  const container = qs("stats");
  container.innerHTML = `
    <div class="stat">
      <div class="label">Уникальные пользователи</div>
      <div class="value">${stats.dialogs_total}</div>
    </div>
    <div class="stat">
      <div class="label">Сообщения</div>
      <div class="value">${stats.messages_total}</div>
    </div>
    <div class="stat">
      <div class="label">Лиды (Bitrix log)</div>
      <div class="value">${stats.leads_total}</div>
    </div>
  `;
}

async function loadUsers() {
  const q = getDatesQuery();
  const data = await api(`/api/users${q}`);
  const container = qs("users-list");
  if (!data.users.length) {
    container.innerHTML = `<div class="muted">Пока нет диалогов.</div>`;
    return;
  }
  container.innerHTML = data.users
    .map((u) => {
      const title = u.full_name || `User ${u.user_id}`;
      const phone = u.phone ? `📞 ${u.phone}` : "";
      const username = u.username ? `@${u.username}` : "";
      const meta = [phone, username].filter(Boolean).join(" · ");
      return `
        <div class="user" onclick="openConversation(${u.user_id})">
          <div class="row">
            <div class="name">${escapeHtml(title)}</div>
            <div class="muted">${u.message_count}</div>
          </div>
          <div class="meta">${escapeHtml(meta || "—")}</div>
          <div class="meta">Последнее: ${fmtDate(u.last_message_at)}</div>
        </div>
      `;
    })
    .join("");
}

async function loadStaff() {
  const data = await api(`/api/staff`);
  const container = qs("staff-list");
  if (!data.items || !data.items.length) {
    container.innerHTML = `<div class="muted">Список пуст.</div>`;
    return;
  }
  container.innerHTML = data.items
    .map((m) => {
      return `
        <div class="user">
          <div class="row">
            <div class="name">${escapeHtml(String(m.tg_user_id))}</div>
            <div class="muted">${escapeHtml(m.role)}</div>
          </div>
          <div class="meta">Добавлен: ${fmtDate(m.created_at)}</div>
          <div class="meta">
            <a href="#" onclick="removeStaff(${m.tg_user_id}); return false;">Удалить</a>
          </div>
        </div>
      `;
    })
    .join("");
}

async function addStaff() {
  const idRaw = (qs("staff-tg-id").value || "").trim();
  const role = (qs("staff-role").value || "admin").trim();
  const tgUserId = Number(idRaw);
  if (!Number.isFinite(tgUserId) || tgUserId <= 0) {
    alert("Введите корректный Telegram user_id (число).");
    return;
  }
  await api(`/api/staff`, {
    method: "POST",
    body: JSON.stringify({ tg_user_id: tgUserId, role }),
  });
  qs("staff-tg-id").value = "";
  await loadStaff();
}

async function removeStaff(tgUserId) {
  await api(`/api/staff/${tgUserId}`, { method: "DELETE" });
  await loadStaff();
}

async function openConversation(userId) {
  const data = await api(`/api/conversation/${userId}?limit=400`);
  const messages = data.messages || [];
  const title = messages[0]?.full_name || `User ${userId}`;
  qs("conversation-title").textContent = title;
  qs("conversation-meta").textContent = `user_id=${userId} · сообщений=${messages.length}`;

  const container = qs("messages");
  if (!messages.length) {
    container.innerHTML = `<div class="muted">Сообщений нет.</div>`;
    return;
  }
  container.innerHTML = messages
    .map((m) => {
      const role = m.role || "user";
      const who = role === "assistant" ? "Бот" : role === "system" ? "Система" : "Пользователь";
      return `
        <div class="msg ${role}">
          <div class="head">
            <div>${escapeHtml(who)}</div>
            <div>${fmtDate(m.created_at)}</div>
          </div>
          <div>${escapeHtml(m.message_text)}</div>
        </div>
      `;
    })
    .join("");
  container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
  const s = String(text || "");
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function byId(id) {
  return document.getElementById(id);
}

function formatDate(value) {
  try {
    const d = new Date(value);
    return d.toLocaleString("ru-RU");
  } catch {
    return String(value);
  }
}

function getDateFilters() {
  const start = byId("start-date")?.value || "";
  const end = byId("end-date")?.value || "";
  const params = new URLSearchParams();
  if (start) params.set("start_date", start);
  if (end) params.set("end_date", end);
  return params.toString();
}

async function login() {
  const password = byId("password-input").value;
  byId("login-error").textContent = "";

  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });

  if (!res.ok) {
    byId("login-error").textContent = "Неверный пароль";
    return;
  }

  byId("login-screen").style.display = "none";
  byId("main-panel").style.display = "block";
  await reloadAll();
}

async function logout() {
  await fetch("/api/logout", { method: "POST" });
  byId("main-panel").style.display = "none";
  byId("conversation-view").style.display = "none";
  byId("login-screen").style.display = "block";
}

async function reloadAll() {
  await loadStats();
  await loadUsers();
}

async function loadStats() {
  const res = await fetch("/api/statistics");
  if (!res.ok) return;
  const data = await res.json();
  byId("dialogs-today").textContent = data.dialogs_today;
  byId("dialogs-total").textContent = data.dialogs_total;
  byId("leads-today").textContent = data.leads_today;
  byId("leads-total").textContent = data.leads_total;
}

async function loadUsers() {
  const query = getDateFilters();
  const res = await fetch("/api/users" + (query ? `?${query}` : ""));
  if (!res.ok) return;
  const data = await res.json();
  renderUsers(data.users || []);
}

function renderUsers(users) {
  const container = byId("users-list");
  container.innerHTML = users
    .map((u) => {
      const title = u.full_name || `Пользователь ${u.user_id}`;
      const meta = [
        u.phone ? `📞 ${u.phone}` : null,
        u.username ? `@${u.username}` : null,
        `${u.message_count} сообщений`,
        `последнее: ${formatDate(u.last_message_at)}`,
      ]
        .filter(Boolean)
        .join(" · ");
      return `
        <div class="user-card" onclick="openConversation(${u.user_id})">
          <div><strong>${escapeHtml(title)}</strong></div>
          <div class="user-meta">${escapeHtml(meta)}</div>
        </div>
      `;
    })
    .join("");
}

async function openConversation(userId) {
  const res = await fetch(`/api/conversation/${userId}?limit=400`);
  if (!res.ok) return;
  const data = await res.json();
  const messages = data.messages || [];

  byId("conversation-view").style.display = "block";
  byId("conversation-title").textContent = `Диалог: ${userId}`;

  byId("messages").innerHTML = messages
    .map((m) => {
      const who = m.role === "user" ? "Клиент" : m.role === "assistant" ? "Бот" : m.role;
      return `
        <div class="message ${escapeHtml(m.role)}">
          <div class="message-header">
            <strong>${escapeHtml(who)}</strong>
            <span>${escapeHtml(formatDate(m.created_at))}</span>
          </div>
          <div class="message-text">${escapeHtml(m.message_text)}</div>
        </div>
      `;
    })
    .join("");
}

function backToUsers() {
  byId("conversation-view").style.display = "none";
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}


