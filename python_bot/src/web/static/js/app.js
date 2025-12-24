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

const SERVICE_LABELS = {
  subsidies_financing: "💰 Субсидии и льготное финансирование",
  logistics_ved: "🚚 Логистика и ВЭД",
  international_payments: "💸 Международные платежи",
  analytics_tnved: "🔎 Аналитика и ТН ВЭД",
  quick_audit_inn: "🧾 Проверка по ИНН",
  club_partnership: "🤝 Клуб и партнёрство",
  unknown: "unknown",
};

const FUNNEL_STEP_LABELS = {
  entry_service: "1) Вошли в услугу",
  engagement_start: "2) Старт квиза/калькулятора/анкеты",
  engagement_complete: "3) Дошли до результата",
  cta_lead_start: "4) Нажали «Оставить заявку»",
  contact_submitted: "5) Оставили контакт",
  meeting_window: "6) Выбрали/ввели окно созвона",
  lead_created: "7) Лид создан",
};

const CONV_LABELS = {
  entry_to_start: "Вход → старт",
  start_to_complete: "Старт → результат",
  complete_to_cta: "Результат → «заявка»",
  cta_to_contact: "«Заявка» → контакт",
  contact_to_meeting: "Контакт → окно",
  meeting_to_lead: "Окно → лид",
  entry_to_lead: "Вход → лид",
};

let __charts = {};

function destroyCharts() {
  for (const k of Object.keys(__charts)) {
    try {
      __charts[k].destroy();
    } catch {}
  }
  __charts = {};
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
  await Promise.all([loadStats(), loadFunnel(), loadUsers(), loadStaff()]);
}

async function loadStats() {
  const q = getDatesQuery();
  const stats = await api(`/api/statistics${q}`);
  const container = qs("stats");
  const convPct = (Number(stats.conversion_rate || 0) * 100).toFixed(2);
  const leadsByService = stats.leads_by_service || {};
  const usersByService = stats.users_by_service || {};

  const renderKvList = (obj) => {
    const entries = Object.entries(obj || {});
    if (!entries.length) return `<div class="muted">—</div>`;
    return `
      <div class="kv">
        ${entries
          .sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0))
          .map(([k, v]) => `<div class="kv-row"><div class="k">${escapeHtml(k)}</div><div class="v">${escapeHtml(String(v))}</div></div>`)
          .join("")}
      </div>
    `;
  };

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
    <div class="stat">
      <div class="label">Конверсия в лид</div>
      <div class="value">${convPct}%</div>
    </div>
    <div class="stat wide">
      <div class="label">Пользователи по услугам</div>
      ${renderKvList(usersByService)}
    </div>
    <div class="stat wide">
      <div class="label">Лиды по услугам</div>
      ${renderKvList(leadsByService)}
    </div>
  `;
}

async function loadFunnel() {
  const q = getDatesQuery();
  const data = await api(`/api/funnel${q}`);
  const container = qs("funnel");
  const overall = data.overall || {};
  const counts = overall.counts || {};
  const conv = overall.conversion || {};
  const drops = overall.drops || {};

  const pct = (x) => (Number(x || 0) * 100).toFixed(2) + "%";

  // Recreate charts safely on each reload (small data, low frequency).
  destroyCharts();

  container.innerHTML = `
    <div class="stat wide">
      <div class="label">Воронка (уникальные пользователи по шагам)</div>
      <div class="chart-wrap tall">
        <canvas id="chart-funnel-counts"></canvas>
      </div>
      <div class="kv">
        <div class="kv-row"><div class="k">1) Вошли в услугу</div><div class="v">${counts.entry_service || 0}</div></div>
        <div class="kv-row"><div class="k">2) Старт квиза/калькулятора/анкеты</div><div class="v">${counts.engagement_start || 0}</div></div>
        <div class="kv-row"><div class="k">3) Дошли до результата</div><div class="v">${counts.engagement_complete || 0}</div></div>
        <div class="kv-row"><div class="k">4) Нажали «Оставить заявку»</div><div class="v">${counts.cta_lead_start || 0}</div></div>
        <div class="kv-row"><div class="k">5) Оставили контакт</div><div class="v">${counts.contact_submitted || 0}</div></div>
        <div class="kv-row"><div class="k">6) Выбрали/ввели окно созвона</div><div class="v">${counts.meeting_window || 0}</div></div>
        <div class="kv-row"><div class="k">7) Лид создан</div><div class="v">${counts.lead_created || 0}</div></div>
      </div>
    </div>
    <div class="stat wide">
      <div class="label">Конверсия по этапам</div>
      <div class="chart-wrap">
        <canvas id="chart-funnel-conv"></canvas>
      </div>
      <div class="kv">
        <div class="kv-row"><div class="k">Вход → старт</div><div class="v">${pct(conv.entry_to_start)}</div></div>
        <div class="kv-row"><div class="k">Старт → результат</div><div class="v">${pct(conv.start_to_complete)}</div></div>
        <div class="kv-row"><div class="k">Результат → «заявка»</div><div class="v">${pct(conv.complete_to_cta)}</div></div>
        <div class="kv-row"><div class="k">«Заявка» → контакт</div><div class="v">${pct(conv.cta_to_contact)}</div></div>
        <div class="kv-row"><div class="k">Контакт → окно</div><div class="v">${pct(conv.contact_to_meeting)}</div></div>
        <div class="kv-row"><div class="k">Окно → лид</div><div class="v">${pct(conv.meeting_to_lead)}</div></div>
        <div class="kv-row"><div class="k">Вход → лид</div><div class="v">${pct(conv.entry_to_lead)}</div></div>
      </div>
    </div>
    <div class="stat wide">
      <div class="label">Конверсия в лид по услугам</div>
      <div class="chart-wrap">
        <canvas id="chart-service-lead"></canvas>
      </div>
      <div class="muted chart-note">
        Метрика: «Вход → лид» (уникальные пользователи). Чем выше — тем лучше.
      </div>
    </div>
    <div class="stat wide">
      <div class="label">Где отваливаются (уникальные)</div>
      <div class="kv">
        <div class="kv-row"><div class="k">После входа (не стартуют)</div><div class="v">${drops.drop_entry || 0}</div></div>
        <div class="kv-row"><div class="k">После старта (не доходят до результата)</div><div class="v">${drops.drop_start || 0}</div></div>
        <div class="kv-row"><div class="k">После результата (не жмут «заявка»)</div><div class="v">${drops.drop_complete || 0}</div></div>
        <div class="kv-row"><div class="k">После «заявка» (не оставляют контакт)</div><div class="v">${drops.drop_cta || 0}</div></div>
        <div class="kv-row"><div class="k">После контакта (не выбирают окно)</div><div class="v">${drops.drop_contact || 0}</div></div>
        <div class="kv-row"><div class="k">После окна (лид не создан)</div><div class="v">${drops.drop_meeting || 0}</div></div>
      </div>
      <div class="muted" style="margin-top:8px">
        Примечание: это метрики по событиям. Если пользователей пока мало — цифры могут быть нулевые.
      </div>
    </div>
  `;

  if (typeof Chart === "undefined") {
    console.warn("Chart.js is not loaded");
    return;
  }

  // Chart 1: funnel counts (horizontal bar)
  const funnelSteps = [
    "entry_service",
    "engagement_start",
    "engagement_complete",
    "cta_lead_start",
    "contact_submitted",
    "meeting_window",
    "lead_created",
  ];
  const funnelLabels = funnelSteps.map((k) => FUNNEL_STEP_LABELS[k] || k);
  const funnelValues = funnelSteps.map((k) => Number(counts[k] || 0));

  const ctxCounts = qs("chart-funnel-counts")?.getContext("2d");
  if (ctxCounts) {
    __charts.funnelCounts = new Chart(ctxCounts, {
      type: "bar",
      data: {
        labels: funnelLabels,
        datasets: [
          {
            label: "Уникальные пользователи",
            data: funnelValues,
            borderWidth: 1,
            backgroundColor: "rgba(37, 99, 235, 0.25)",
            borderColor: "rgba(37, 99, 235, 1)",
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { enabled: true },
        },
        scales: {
          x: { beginAtZero: true, ticks: { precision: 0 } },
          y: { ticks: { autoSkip: false } },
        },
      },
    });
  }

  // Chart 2: conversion by stage (line)
  const convKeys = [
    "entry_to_start",
    "start_to_complete",
    "complete_to_cta",
    "cta_to_contact",
    "contact_to_meeting",
    "meeting_to_lead",
    "entry_to_lead",
  ];
  const convLabels = convKeys.map((k) => CONV_LABELS[k] || k);
  const convValues = convKeys.map((k) => Number(conv[k] || 0) * 100);
  const ctxConv = qs("chart-funnel-conv")?.getContext("2d");
  if (ctxConv) {
    __charts.funnelConv = new Chart(ctxConv, {
      type: "line",
      data: {
        labels: convLabels,
        datasets: [
          {
            label: "Конверсия, %",
            data: convValues,
            fill: false,
            borderColor: "rgba(15, 23, 42, 0.9)",
            backgroundColor: "rgba(15, 23, 42, 0.9)",
            tension: 0.25,
            pointRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
        },
        scales: {
          y: { beginAtZero: true, max: 100, ticks: { callback: (v) => `${v}%` } },
        },
      },
    });
  }

  // Chart 3: conversion entry->lead by service
  const byService = data.by_service || {};
  const svcRows = Object.entries(byService).map(([k, v]) => {
    const c = v?.conversion || {};
    const cc = v?.counts || {};
    return {
      key: k,
      label: SERVICE_LABELS[k] || k,
      entry: Number(cc.entry_service || 0),
      pct: Number(c.entry_to_lead || 0) * 100,
    };
  });
  svcRows.sort((a, b) => b.pct - a.pct);
  const svcLabels = svcRows.map((r) => r.label);
  const svcVals = svcRows.map((r) => r.pct);

  const ctxSvc = qs("chart-service-lead")?.getContext("2d");
  if (ctxSvc) {
    __charts.serviceLead = new Chart(ctxSvc, {
      type: "bar",
      data: {
        labels: svcLabels,
        datasets: [
          {
            label: "Вход → лид, %",
            data: svcVals,
            borderWidth: 1,
            backgroundColor: "rgba(34, 197, 94, 0.25)",
            borderColor: "rgba(34, 197, 94, 1)",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              afterLabel: function (ctx) {
                const idx = ctx.dataIndex;
                const row = svcRows[idx];
                return row ? `Входов: ${row.entry}` : "";
              },
            },
          },
        },
        scales: {
          y: { beginAtZero: true, max: 100, ticks: { callback: (v) => `${v}%` } },
        },
      },
    });
  }
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
