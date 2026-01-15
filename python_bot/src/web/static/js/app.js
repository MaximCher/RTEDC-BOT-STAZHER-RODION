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
  service_payments: "Международные платежи",
  service_credits: "Льготные кредиты",
  service_subsidies: "Субсидии",
  service_logistics: "Логистика",
  service_check: "Проверка контрагента",
  service_translate: "Лингвистические переводы",
  subsidies_financing: "Субсидии и льготное финансирование",
  logistics_ved: "Логистика и ВЭД",
  international_payments: "Международные платежи",
  analytics_tnved: "Аналитика и ТН ВЭД",
  quick_audit_inn: "Проверка по ИНН (quick audit)",
  club_partnership: "Клуб экспортёров и партнёрство",
  unknown: "Неизвестно",
};

const FUNNEL_STEP_LABELS = {
  entry_service: "1) Вошли в услугу",
  engagement_start: "2) Старт квиза/калькулятора/заявки",
  engagement_complete: "3) Дошли до результата",
  cta_lead_start: "4) Нажали «Оставить заявку»",
  contact_submitted: "5) Оставили контакт",
  meeting_window: "6) Выбрали/ввели время для созвона",
  lead_created: "7) Лид создан",
};

const CONV_LABELS = {
  entry_to_start: "Вход → старт",
  start_to_complete: "Старт → результат",
  complete_to_cta: "Результат → «заявка»",
  cta_to_contact: "«Заявка» → контакт",
  contact_to_meeting: "Контакт → время",
  meeting_to_lead: "Время → лид",
  entry_to_lead: "Вход → лид",
};

const EVENT_LABELS = {
  entry_service: "Выбор услуги",
  engagement_start: "Старт сценария",
  engagement_complete: "Получили результат",
  cta_lead_start: "Нажали «Оставить заявку»",
  contact_submitted: "Оставили контакт",
  meeting_window_selected: "Выбрали время для созвона",
  meeting_window_submitted: "Ввели время для созвона",
  lead_created: "Лид создан (Bitrix)",
  subsidy_calc_complete: "Калькулятор субсидий завершён",
  finance_calc_complete: "Калькулятор финансирования завершён",
  logistics_quote_complete: "Запрос логистики завершён",
  payments_precheck_complete: "Предчек платежа завершён",
  analytics_report_complete: "Запрос аналитики завершён",
  audit_quick_complete: "Быстрый аудит завершён",
  club_apply_complete: "Заявка в клуб отправлена",
};

function safeJsonParse(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function formatEventMessage(messageText) {
  const raw = String(messageText || "");
  const body = raw.startsWith("event:") ? raw.slice("event:".length) : raw;
  const payload = safeJsonParse(body);
  if (!payload || typeof payload !== "object") return null;

  const event = payload.event ? String(payload.event) : "";
  const serviceKey = payload.service ? String(payload.service) : "";
  const meta = payload.meta && typeof payload.meta === "object" ? payload.meta : null;

  const eventLabel = EVENT_LABELS[event] || event || "Событие";
  const serviceLabel = serviceKey ? SERVICE_LABELS[serviceKey] || serviceKey : "";

  const metaParts = [];
  if (serviceLabel) metaParts.push(`Услуга: ${serviceLabel}`);
  if (meta && meta.value) metaParts.push(`Значение: ${String(meta.value)}`);

  const metaHtml = metaParts.length
    ? `<div class="event-meta">${escapeHtml(metaParts.join(" · "))}</div>`
    : "";
  return `<div class="event-title">${escapeHtml(eventLabel)}</div>${metaHtml}`;
}

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
  await Promise.all([
    loadWebappUrl(),
    loadStats(),
    loadFunnel(),
    loadUsers(),
    loadStaff(),
    loadVirality(),
    loadBroadcasts(),
    loadEvents(),
    loadActions(),
  ]);
}

async function loadBroadcasts() {
  const container = qs("broadcast-list");
  if (!container) return;
  try {
    const data = await api(`/api/broadcast`);
    const items = data.items || [];
    if (!items.length) {
      container.innerHTML = `<div class="text-secondary">Пока нет запланированных рассылок.</div>`;
      return;
    }
    container.innerHTML = `
      <div class="list-group">
        ${items
          .map((it) => {
            const id = Number(it.id);
            const text = String(it.text || "");
            const sendAt = it.send_at ? String(it.send_at) : "";
            const createdAt = it.created_at ? String(it.created_at) : "";
            const when = sendAt ? escapeHtml(sendAt) : "—";
            const created = createdAt ? escapeHtml(createdAt) : "—";
            return `
              <div class="list-group-item">
                <div class="d-flex justify-content-between align-items-start gap-2">
                  <div style="min-width: 0;">
                    <div class="fw-bold">Отправка: <span class="text-secondary">${when}</span></div>
                    <div class="text-secondary small">создано: ${created}</div>
                    <div class="mt-2" style="white-space: pre-wrap;">${escapeHtml(text)}</div>
                  </div>
                  <div class="text-end">
                    <button class="btn btn-sm btn-outline-danger" onclick="removeBroadcast(${id}); return false;">Удалить</button>
                  </div>
                </div>
              </div>
            `;
          })
          .join("")}
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="text-danger small">Не удалось загрузить рассылки.</div>`;
  }
}

async function addBroadcast() {
  const text = (qs("broadcast-text")?.value || "").trim();
  const sendAt = (qs("broadcast-send-at")?.value || "").trim();
  if (!text) {
    alert("Введите текст рассылки.");
    return;
  }
  if (!sendAt) {
    alert("Выберите время отправки.");
    return;
  }
  await api(`/api/broadcast`, {
    method: "POST",
    body: JSON.stringify({ text, send_at: sendAt }),
  });
  qs("broadcast-text").value = "";
  await loadBroadcasts();
}

async function removeBroadcast(id) {
  await api(`/api/broadcast/${Number(id)}`, { method: "DELETE" });
  await loadBroadcasts();
}

async function loadActions() {
  const container = qs("actions-top");
  if (!container) return;
  try {
    const q = getDatesQuery();
    const data = await api(`/api/actions${q}`);
    const topActions = data.top_actions || [];
    const topHuman = data.top_human || [];

    const renderList = (items, labelKey, countKey) => {
      if (!items.length) return `<div class="text-secondary">—</div>`;
      return `
        <div class="list-group">
          ${items
            .map((it) => {
              const label = String(it.desc || it[labelKey] || "");
              const cnt = Number(it[countKey] || 0);
              return `
                <div class="list-group-item">
                  <div class="d-flex justify-content-between gap-2">
                    <div style="min-width: 0;">
                      <div class="fw-bold text-truncate">${escapeHtml(label)}</div>
                    </div>
                    <div class="badge bg-blue-lt">${escapeHtml(String(cnt))}</div>
                  </div>
                </div>
              `;
            })
            .join("")}
        </div>
      `;
    };

    container.innerHTML = `
      <div>
        <div class="text-secondary small mb-1">Top action</div>
        ${renderList(topActions, "action", "count")}
      </div>
      <div>
        <div class="text-secondary small mb-1">Top (human)</div>
        ${renderList(topHuman, "desc", "count")}
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="text-danger small">Не удалось загрузить топ действий.</div>`;
  }
}

async function loadEvents() {
  const container = qs("events-list");
  if (!container) return;
  const userIdRaw = (qs("events-user-id")?.value || "").trim();
  const action = (qs("events-action")?.value || "").trim();
  const limit = Number((qs("events-limit")?.value || "200").trim());
  const params = new URLSearchParams();
  const start = qs("start-date")?.value || "";
  const end = qs("end-date")?.value || "";
  if (start) params.set("start_date", start);
  if (end) params.set("end_date", end);
  if (userIdRaw) params.set("user_id", userIdRaw);
  if (action) params.set("action", action);
  if (Number.isFinite(limit)) params.set("limit", String(limit));
  const qsStr = params.toString() ? `?${params.toString()}` : "";

  try {
    const data = await api(`/api/events${qsStr}`);
    const items = data.items || [];
    if (!items.length) {
      container.innerHTML = `<div class="text-secondary">Событий нет.</div>`;
      return;
    }
    container.innerHTML = `
      <div class="list-group">
        ${items
          .map((e) => {
            const uid = Number(e.user_id || 0);
            const who = e.full_name || (e.username ? `@${e.username}` : `user_id=${uid}`);
            const when = fmtDate(e.timestamp);
            const desc = String(e.desc || e.action || "");
            return `
              <a href="#" class="list-group-item list-group-item-action" onclick="openConversation(${uid}); return false;">
                <div class="d-flex justify-content-between align-items-start gap-2">
                  <div style="min-width: 0;">
                    <div class="fw-bold text-truncate">${escapeHtml(who)}</div>
                    <div class="text-secondary">${escapeHtml(desc)}</div>
                  </div>
                  <div class="text-secondary small text-end">${escapeHtml(when)}</div>
                </div>
              </a>
            `;
          })
          .join("")}
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="text-danger small">Не удалось загрузить события.</div>`;
  }
}

async function loadUserJourney(userId) {
  const container = qs("journey");
  if (!container) return;
  if (!userId) {
    container.innerHTML = `<div class="text-secondary">Выберите пользователя.</div>`;
    return;
  }
  try {
    const data = await api(`/api/user-journey/${Number(userId)}?limit=1500`);
    const events = data.events || [];
    if (!events.length) {
      container.innerHTML = `<div class="text-secondary">Событий по пользователю нет.</div>`;
      return;
    }
    container.innerHTML = events
      .map((e) => {
        const when = fmtDate(e.timestamp);
        const desc = String(e.desc || e.action || "");
        return `
          <div class="msg event">
            <div class="head">
              <div>${escapeHtml("Событие")}</div>
              <div>${escapeHtml(when)}</div>
            </div>
            <div>${escapeHtml(desc)}</div>
          </div>
        `;
      })
      .join("");
    container.scrollTop = container.scrollHeight;
  } catch (e) {
    container.innerHTML = `<div class="text-danger small">Не удалось загрузить путь пользователя.</div>`;
  }
}

function toggleJourney(show) {
  const messages = qs("messages");
  const journey = qs("journey");
  if (!messages || !journey) return;
  if (show) {
    messages.style.display = "none";
    journey.style.display = "block";
    const userId = window.__currentUserId || 0;
    if (userId) loadUserJourney(userId);
  } else {
    journey.style.display = "none";
    messages.style.display = "block";
  }
}

async function loadVirality() {
  const container = qs("virality-list");
  if (!container) return;
  try {
    const data = await api(`/api/virality`);
    const items = data.items || [];
    const toggle = qs("ask-contact-toggle");
    if (toggle) toggle.checked = Boolean(data.ask_contact_on_start);

    if (!items.length) {
      container.innerHTML = `<div class="text-secondary">Список пуст — проверка отключена.</div>`;
      return;
    }

    container.innerHTML = `
      <div class="list-group">
        ${items
          .map((it) => {
            const title = it.title ? String(it.title) : "";
            const chatRef = String(it.chat_ref || "");
            const kind = String(it.kind || "other");
            const url = it.url ? String(it.url) : "";
            const label = [title || chatRef, kind].filter(Boolean).join(" · ");
            const link = url
              ? `<a class="small" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(url)}</a>`
              : `<span class="text-secondary small">url: —</span>`;
            return `
              <div class="list-group-item">
                <div class="d-flex justify-content-between align-items-start gap-2">
                  <div>
                    <div class="fw-bold">${escapeHtml(label)}</div>
                    <div class="text-secondary small">chat_ref: ${escapeHtml(chatRef)}</div>
                    <div class="mt-1">${link}</div>
                  </div>
                  <div class="text-end">
                    <button class="btn btn-sm btn-outline-danger" onclick="removeViralitySub(${Number(
                      it.id
                    )}); return false;">Удалить</button>
                  </div>
                </div>
              </div>
            `;
          })
          .join("")}
      </div>
    `;
  } catch (e) {
    container.innerHTML = `<div class="text-danger small">Не удалось загрузить настройки.</div>`;
  }
}

async function addViralitySub() {
  const kind = (qs("virality-kind")?.value || "channel").trim();
  const chatRef = (qs("virality-chat-ref")?.value || "").trim();
  const title = (qs("virality-title")?.value || "").trim();
  const url = (qs("virality-url")?.value || "").trim();
  if (!chatRef) {
    alert("Вставьте ссылку https://t.me/... или @username или -100...");
    return;
  }
  await api(`/api/virality/subscriptions`, {
    method: "POST",
    body: JSON.stringify({ kind, chat_ref: chatRef, title: title || null, url: url || null }),
  });
  qs("virality-chat-ref").value = "";
  qs("virality-title").value = "";
  qs("virality-url").value = "";
  await loadVirality();
}

async function removeViralitySub(id) {
  await api(`/api/virality/subscriptions/${id}`, { method: "DELETE" });
  await loadVirality();
}

async function saveAskContact() {
  const enabled = Boolean(qs("ask-contact-toggle")?.checked);
  await api(`/api/virality/ask-contact`, {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });
}

async function loadWebappUrl() {
  const a = qs("current-webapp-url");
  if (!a) return;
  try {
    const data = await api("/api/webapp-url");
    const url = String(data?.url || "").trim();
    if (!url) return;
    // Keep full URL for opening/copying, but show short host for readability.
    window.__currentWebappUrl = url;
    try {
      const u = new URL(url);
      a.textContent = u.host;
    } catch {
      a.textContent = url;
    }
    a.href = url;
  } catch {
    // ignore
  }
}

function copyCurrentWebappUrl() {
  const url = window.__currentWebappUrl || (qs("current-webapp-url")?.href || "");
  if (!url || url === "#") return;
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(url).catch(() => {});
    return;
  }
  // Fallback
  try {
    const tmp = document.createElement("input");
    tmp.value = url;
    document.body.appendChild(tmp);
    tmp.select();
    document.execCommand("copy");
    document.body.removeChild(tmp);
  } catch (e) {
    // ignore
  }
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
    if (!entries.length) return `<div class="text-secondary">—</div>`;
    return `
      <div class="table-responsive">
        <table class="table table-vcenter table-sm">
          <tbody>
            ${entries
              .sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0))
              .map(
                ([k, v]) => `
                  <tr>
                    <td class="text-secondary">${escapeHtml(SERVICE_LABELS[k] || k)}</td>
                    <td class="text-end fw-bold">${escapeHtml(String(v))}</td>
                  </tr>
                `
              )
              .join("")}
          </tbody>
        </table>
      </div>
    `;
  };

  container.innerHTML = `
    <div class="col-6 col-lg-3">
      <div class="card">
        <div class="card-body">
          <div class="subheader">Уникальные пользователи</div>
          <div class="h1 mb-0">${stats.dialogs_total}</div>
        </div>
      </div>
    </div>
    <div class="col-6 col-lg-3">
      <div class="card">
        <div class="card-body">
          <div class="subheader">Сообщения</div>
          <div class="h1 mb-0">${stats.messages_total}</div>
        </div>
      </div>
    </div>
    <div class="col-6 col-lg-3">
      <div class="card">
        <div class="card-body">
          <div class="subheader">Лиды (Bitrix log)</div>
          <div class="h1 mb-0">${stats.leads_total}</div>
        </div>
      </div>
    </div>
    <div class="col-6 col-lg-3">
      <div class="card">
        <div class="card-body">
          <div class="subheader">Конверсия в лид</div>
          <div class="h1 mb-0">${convPct}%</div>
        </div>
      </div>
    </div>
    <div class="col-12">
      <div class="card">
        <div class="card-header">
          <div class="card-title">Пользователи по услугам</div>
        </div>
        <div class="card-body">
          ${renderKvList(usersByService)}
        </div>
      </div>
    </div>
    <div class="col-12">
      <div class="card">
        <div class="card-header">
          <div class="card-title">Лиды по услугам</div>
        </div>
        <div class="card-body">
          ${renderKvList(leadsByService)}
        </div>
      </div>
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
    <div class="col-12">
      <div class="card">
        <div class="card-header">
          <div class="card-title">Воронка (уникальные пользователи по шагам)</div>
        </div>
        <div class="card-body">
          <div class="chart-wrap tall">
            <canvas id="chart-funnel-counts"></canvas>
          </div>
          <div class="table-responsive mt-3">
            <table class="table table-vcenter table-sm">
              <tbody>
                <tr><td class="text-secondary">1) Вошли в услугу</td><td class="text-end fw-bold">${counts.entry_service || 0}</td></tr>
                <tr><td class="text-secondary">2) Старт квиза/калькулятора/заявки</td><td class="text-end fw-bold">${counts.engagement_start || 0}</td></tr>
                <tr><td class="text-secondary">3) Дошли до результата</td><td class="text-end fw-bold">${counts.engagement_complete || 0}</td></tr>
                <tr><td class="text-secondary">4) Нажали «Оставить заявку»</td><td class="text-end fw-bold">${counts.cta_lead_start || 0}</td></tr>
                <tr><td class="text-secondary">5) Оставили контакт</td><td class="text-end fw-bold">${counts.contact_submitted || 0}</td></tr>
                <tr><td class="text-secondary">6) Выбрали/ввели время для созвона</td><td class="text-end fw-bold">${counts.meeting_window || 0}</td></tr>
                <tr><td class="text-secondary">7) Лид создан</td><td class="text-end fw-bold">${counts.lead_created || 0}</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <div class="col-12">
      <div class="card">
        <div class="card-header">
          <div class="card-title">Конверсия по этапам</div>
        </div>
        <div class="card-body">
          <div class="chart-wrap">
            <canvas id="chart-funnel-conv"></canvas>
          </div>
          <div class="table-responsive mt-3">
            <table class="table table-vcenter table-sm">
              <tbody>
                <tr><td class="text-secondary">Вход → старт</td><td class="text-end fw-bold">${pct(conv.entry_to_start)}</td></tr>
                <tr><td class="text-secondary">Старт → результат</td><td class="text-end fw-bold">${pct(conv.start_to_complete)}</td></tr>
                <tr><td class="text-secondary">Результат → «заявка»</td><td class="text-end fw-bold">${pct(conv.complete_to_cta)}</td></tr>
                <tr><td class="text-secondary">«Заявка» → контакт</td><td class="text-end fw-bold">${pct(conv.cta_to_contact)}</td></tr>
                <tr><td class="text-secondary">Контакт → время</td><td class="text-end fw-bold">${pct(conv.contact_to_meeting)}</td></tr>
                <tr><td class="text-secondary">Время → лид</td><td class="text-end fw-bold">${pct(conv.meeting_to_lead)}</td></tr>
                <tr><td class="text-secondary">Вход → лид</td><td class="text-end fw-bold">${pct(conv.entry_to_lead)}</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <div class="col-12">
      <div class="card">
        <div class="card-header">
          <div class="card-title">Конверсия в лид по услугам</div>
        </div>
        <div class="card-body">
          <div class="chart-wrap">
            <canvas id="chart-service-lead"></canvas>
          </div>
          <div class="text-secondary mt-2">
            Метрика: «Вход → лид» (уникальные пользователи). Чем выше — тем лучше.
          </div>
        </div>
      </div>
    </div>

    <div class="col-12">
      <div class="card">
        <div class="card-header">
          <div class="card-title">Где отваливаются (уникальные)</div>
        </div>
        <div class="card-body">
          <div class="table-responsive">
            <table class="table table-vcenter table-sm">
              <tbody>
                <tr><td class="text-secondary">После входа (не стартуют)</td><td class="text-end fw-bold">${drops.drop_entry || 0}</td></tr>
                <tr><td class="text-secondary">После старта (не доходят до результата)</td><td class="text-end fw-bold">${drops.drop_start || 0}</td></tr>
                <tr><td class="text-secondary">После результата (не жмут «заявка»)</td><td class="text-end fw-bold">${drops.drop_complete || 0}</td></tr>
                <tr><td class="text-secondary">После «заявка» (не оставляют контакт)</td><td class="text-end fw-bold">${drops.drop_cta || 0}</td></tr>
                <tr><td class="text-secondary">После контакта (не выбирают время)</td><td class="text-end fw-bold">${drops.drop_contact || 0}</td></tr>
                <tr><td class="text-secondary">После выбора времени (лид не создан)</td><td class="text-end fw-bold">${drops.drop_meeting || 0}</td></tr>
              </tbody>
            </table>
          </div>
          <div class="text-secondary mt-2">
            Примечание: это метрики по событиям. Если пользователей пока мало — цифры могут быть нулевые.
          </div>
        </div>
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
            borderRadius: 8,
            borderSkipped: false,
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
          x: {
            beginAtZero: true,
            ticks: { precision: 0 },
            grid: { color: "rgba(148, 163, 184, 0.25)" },
          },
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
    const maxPct = Math.max(0, ...svcVals);
    const maxX = Math.max(5, Math.ceil(maxPct / 10) * 10);
    const bg = svcVals.map((v) => {
      // greener for higher conversion
      const a = Math.min(0.55, Math.max(0.18, v / 100 + 0.18));
      return `rgba(34, 197, 94, ${a})`;
    });
    __charts.serviceLead = new Chart(ctxSvc, {
      type: "bar",
      data: {
        labels: svcLabels,
        datasets: [
          {
            label: "Вход → лид, %",
            data: svcVals,
            borderWidth: 1,
            backgroundColor: bg,
            borderColor: "rgba(34, 197, 94, 1)",
            borderRadius: 8,
            borderSkipped: false,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return `${Number(ctx.parsed.x || 0).toFixed(2)}%`;
              },
              afterLabel: function (ctx) {
                const idx = ctx.dataIndex;
                const row = svcRows[idx];
                return row ? `Входов: ${row.entry}` : "";
              },
            },
          },
        },
        scales: {
          x: {
            beginAtZero: true,
            max: maxX,
            ticks: { callback: (v) => `${v}%` },
            grid: { color: "rgba(148, 163, 184, 0.25)" },
          },
          y: { ticks: { autoSkip: false } },
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
    container.innerHTML = `<div class="text-secondary">Пока нет диалогов.</div>`;
    return;
  }
  container.innerHTML = `
    <div class="list-group list-group-flush">
      ${data.users
        .map((u) => {
          const title = u.full_name || `User ${u.user_id}`;
          const phone = u.phone ? `📞 ${u.phone}` : "";
          const username = u.username ? `@${u.username}` : "";
          const meta = [phone, username].filter(Boolean).join(" · ");
          return `
            <a href="#" class="list-group-item list-group-item-action" onclick="openConversation(${u.user_id}); return false;">
              <div class="d-flex justify-content-between align-items-start gap-2">
                <div class="fw-bold">${escapeHtml(title)}</div>
                <span class="badge bg-blue-lt">${escapeHtml(String(u.message_count || 0))}</span>
              </div>
              <div class="text-secondary small mt-1">${escapeHtml(meta || "—")}</div>
              <div class="text-secondary small">Последнее: ${fmtDate(u.last_message_at)}</div>
            </a>
          `;
        })
        .join("")}
    </div>
  `;
}

async function loadStaff() {
  const data = await api(`/api/staff`);
  const container = qs("staff-list");
  if (!data.items || !data.items.length) {
    container.innerHTML = `<div class="text-secondary">Список пуст.</div>`;
    return;
  }
  container.innerHTML = `
    <div class="list-group">
      ${data.items
        .map((m) => {
          const name = m.tg_full_name || "";
          const username = m.tg_username ? `@${m.tg_username}` : "";
          const who = [name, username].filter(Boolean).join(" · ") || String(m.tg_user_id);
          const seen = m.last_seen_at ? `Активен: ${fmtDate(m.last_seen_at)}` : "Активность: —";
          return `
            <div class="list-group-item">
              <div class="d-flex justify-content-between align-items-start gap-2">
                <div>
                  <div class="fw-bold">${escapeHtml(who)}</div>
                  <div class="text-secondary small">${escapeHtml(String(m.tg_user_id))}</div>
                  <div class="text-secondary small">${escapeHtml(seen)}</div>
                  <div class="text-secondary small">Добавлен: ${fmtDate(m.created_at)}</div>
                </div>
                <div class="text-end">
                  <div class="badge bg-azure-lt">${escapeHtml(m.role)}</div>
                  <div class="mt-2">
                    <button class="btn btn-sm btn-outline-danger" onclick="removeStaff(${m.tg_user_id}); return false;">
                      Удалить
                    </button>
                  </div>
                </div>
              </div>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

async function createInvite() {
  const role = (qs("invite-role").value || "manager").trim();
  const ttlHours = Number((qs("invite-ttl").value || "168").trim());
  if (!Number.isFinite(ttlHours) || ttlHours <= 0) {
    alert("Введите корректный TTL (часов).");
    return;
  }
  const data = await api(`/api/staff/invites`, {
    method: "POST",
    body: JSON.stringify({ role, ttl_hours: ttlHours }),
  });
  const url = String(data?.url || "").trim();
  window.__currentInviteUrl = url;
  const a = qs("invite-link");
  if (a) {
    a.href = url || "#";
    a.textContent = url || "Ссылка появится здесь…";
  }
}

function copyInvite() {
  const url = window.__currentInviteUrl || "";
  if (!url) return;
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(url).catch(() => {});
    return;
  }
  try {
    const tmp = document.createElement("input");
    tmp.value = url;
    document.body.appendChild(tmp);
    tmp.select();
    document.execCommand("copy");
    document.body.removeChild(tmp);
  } catch (e) {}
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
  window.__currentUserId = Number(userId);

  const container = qs("messages");
  if (!messages.length) {
    container.innerHTML = `<div class="text-secondary">Сообщений нет.</div>`;
    return;
  }
  container.innerHTML = messages
    .map((m) => {
      const role = m.role || "user";
      const who =
        role === "assistant"
          ? "Бот"
          : role === "system"
            ? "Система"
            : role === "staff"
              ? "Менеджер"
              : "Пользователь";
      const rawText = String(m.message_text || "");
      const bodyHtml = escapeHtml(rawText);
      return `
        <div class="msg ${role}">
          <div class="head">
            <div>${escapeHtml(who)}</div>
            <div>${fmtDate(m.created_at)}</div>
          </div>
          <div>${bodyHtml}</div>
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
