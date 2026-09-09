/* ===========================================================
   Telegram Panel – Frontend
   =========================================================== */

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const state = {
  accounts: [],
  pool: [],
  stats: null,
  opAccounts: [],
  devices: [],
  groups: [],
  jobs: [],
  activeJob: null,
  loginId: null,
  poller: null,
};

/* ── API ─────────────────────────────────────────────────── */

async function api(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw new Error(data?.detail || `Fehler ${res.status}`);
  return data;
}

/* ── Toasts ──────────────────────────────────────────────── */

function toast(message, kind = "") {
  const el = document.createElement("div");
  el.className = `toast${kind ? ` toast--${kind}` : ""}`;
  el.textContent = message;
  $("#toasts").append(el);
  setTimeout(() => {
    el.classList.add("toast--fade");
    setTimeout(() => el.remove(), 260);
  }, 4200);
}

/* ── Helfer ──────────────────────────────────────────────── */

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

const initials = (name) =>
  (name || "?").trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();

function timeAgo(ts) {
  if (!ts) return "nie";
  const diff = Math.max(0, Date.now() / 1000 - ts);
  if (diff < 60) return "gerade eben";
  if (diff < 3600) return `vor ${Math.floor(diff / 60)} Min.`;
  if (diff < 86400) return `vor ${Math.floor(diff / 3600)} Std.`;
  return `vor ${Math.floor(diff / 86400)} Tg.`;
}

const clock = (ts) =>
  new Date(ts * 1000).toLocaleTimeString("de-DE", {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });

/* ── Navigation ──────────────────────────────────────────── */

const VIEW_META = {
  dashboard: ["Übersicht", "Status deiner Accounts und deines Pools."],
  accounts:  ["Accounts", "Telegram-Accounts binden und verwalten."],
  pool:      ["@username Pool", "Deine gesammelten Namen an einem Ort."],
  operation: ["Vorgang", "Pool-Mitglieder in die Zielgruppe aufnehmen."],
  jobs:      ["Protokoll", "Laufende und abgeschlossene Jobs."],
};

function showView(name) {
  $$(".view").forEach((v) => v.classList.toggle("is-active", v.dataset.view === name));
  $$(".nav-item").forEach((b) => b.classList.toggle("is-active", b.dataset.view === name));
  const [title, subtitle] = VIEW_META[name] || ["", ""];
  $("#viewTitle").textContent = title;
  $("#viewSubtitle").textContent = subtitle;
  if (name === "jobs") loadJobs();
  if (name === "pool") loadPool();
}

$("#nav").addEventListener("click", (e) => {
  const item = e.target.closest(".nav-item");
  if (item) showView(item.dataset.view);
});

document.addEventListener("click", (e) => {
  const goto = e.target.closest("[data-goto]");
  if (goto) showView(goto.dataset.goto);
});

/* ── Dashboard ───────────────────────────────────────────── */

async function loadStats() {
  const s = await api("/stats");
  state.stats = s;
  $("#statAccounts").textContent = s.accounts;
  $("#statAccountsFoot").textContent =
    s.accounts ? `${s.accounts_online} online` : "keine gebunden";
  $("#statPremium").textContent = s.accounts_premium;
  $("#statPool").textContent = s.pool;
  $("#statPoolFoot").textContent =
    `${s.pool_valid} geprüft${s.pool_dead ? ` · ${s.pool_dead} tot` : ""}`;
  $("#statJoined").textContent = s.pool_joined;
  $("#badgeAccounts").textContent = s.accounts;
  $("#badgePool").textContent = s.pool;

  const badge = $("#badgeJobs");
  badge.hidden = !s.jobs_running;
  badge.textContent = s.jobs_running;

  renderAddEstimate();
}

/* ── Accounts ────────────────────────────────────────────── */

const STATUS_BADGE = {
  online:  ["badge-ok", "online"],
  pending: ["badge-warn", "wartet"],
  error:   ["badge-danger", "Fehler"],
};

function countdown(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return h
    ? `${h} Std. ${String(m).padStart(2, "0")} Min.`
    : `${m}:${String(sec).padStart(2, "0")} Min.`;
}

function renderQuota(account) {
  const q = account.quota;
  const percent = Math.min(100, Math.round((q.used / q.limit) * 100));
  const bar = `<div class="quota-bar"><i class="${
    q.blocked ? "is-full" : ""}" style="width:${percent}%"></i></div>`;

  if (q.blocked) {
    return `
      <div class="quota quota--blocked">
        <div class="quota-head">
          <span>Kontingent aufgebraucht — ${q.used}/${q.limit}</span>
          <strong data-until="${q.cooldown_until}">frei in ${esc(
            countdown(q.seconds_left))}</strong>
        </div>
        ${bar}
      </div>`;
  }

  return `
    <div class="quota">
      <div class="quota-head">
        <span>Kontingent</span>
        <strong>${q.used}/${q.limit}</strong>
      </div>
      ${bar}
    </div>`;
}

// Laesst die Countdowns weiterlaufen, ohne die Liste neu zu bauen.
setInterval(() => {
  $$("[data-until]").forEach((el) => {
    const left = Number(el.dataset.until) - Date.now() / 1000;
    if (left <= 0) {
      el.textContent = "Pause vorbei";
      return;
    }
    el.textContent = `frei in ${countdown(left)}`;
  });
}, 1000);

function renderAccounts() {
  const box = $("#accountList");
  if (!state.accounts.length) {
    box.innerHTML = '<div class="empty">Noch kein Account gebunden.</div>';
    return;
  }

  box.innerHTML = state.accounts.map((a) => {
    const [cls, text] = STATUS_BADGE[a.status] || ["badge-muted", a.status];
    const device = state.devices.find((d) => d.id === a.device_id);
    return `
      <div class="account">
        <div class="avatar">${esc(initials(a.first_name || a.label || a.phone))}</div>
        <div class="account-main">
          <div class="account-name">
            ${esc(a.label || a.first_name || a.phone)}
            <span class="badge ${cls}">${esc(text)}</span>
            ${a.is_premium ? '<span class="badge badge-premium">★ Premium</span>' : ""}
          </div>
          <div class="account-meta">
            <span>${esc(a.phone)}</span>
            ${a.username ? `<span>@${esc(a.username)}</span>` : ""}
            <span>${esc(device ? device.name : a.device_id)}</span>
            ${a.proxy ? `<span>Proxy ${esc(a.proxy.type)} ${esc(a.proxy.host)}:${esc(a.proxy.port)}</span>` : ""}
            <span>geprüft ${esc(timeAgo(a.last_check))}</span>
          </div>
        </div>
        <div class="account-actions">
          ${a.quota.blocked
            ? `<button class="btn btn-sm btn-primary" data-release="${a.id}">Freigeben</button>`
            : ""}
          <button class="btn btn-ghost btn-sm" data-refresh="${a.id}">Prüfen</button>
          <button class="btn btn-ghost btn-sm btn-danger" data-remove="${a.id}">Lösen</button>
        </div>
        ${renderQuota(a)}
        ${a.last_error ? `<div class="account-error">${esc(a.last_error)}</div>` : ""}
      </div>`;
  }).join("");
}

async function loadAccounts() {
  state.accounts = await api("/accounts");
  renderAccounts();
  fillAccountSelects();
  renderAddEstimate();
}

function fillAccountSelects() {
  const options = state.accounts.length
    ? state.accounts.map((a) =>
        `<option value="${a.id}">${esc(a.label || a.first_name || a.phone)}${a.is_premium ? " ★" : ""}</option>`
      ).join("")
    : '<option value="">– kein Account gebunden –</option>';

  const el = $("#fCheckAccount");
  const previous = el.value;
  el.innerHTML = options;
  if (previous) el.value = previous;

  // Abgemeldete Accounts nicht in der Auswahl stehen lassen.
  const alive = new Set(state.accounts.map((a) => a.id));
  state.opAccounts = state.opAccounts.filter((id) => alive.has(id));
  renderOpAccounts();
}

$("#accountList").addEventListener("click", async (e) => {
  const refresh = e.target.closest("[data-refresh]");
  const remove = e.target.closest("[data-remove]");
  const release = e.target.closest("[data-release]");

  if (release) {
    try {
      await api(`/accounts/${release.dataset.release}/release`, { method: "POST" });
      toast("Account freigegeben — Zähler zurückgesetzt.", "ok");
    } catch (err) {
      toast(err.message, "error");
    }
    await loadAccounts();
    loadStats();
  }

  if (refresh) {
    refresh.disabled = true;
    refresh.textContent = "…";
    try {
      await api(`/accounts/${refresh.dataset.refresh}/refresh`, { method: "POST" });
      toast("Status aktualisiert.", "ok");
    } catch (err) {
      toast(err.message, "error");
    }
    await loadAccounts();
    loadStats();
  }

  if (remove) {
    if (!confirm("Account lösen? Die Session wird bei Telegram abgemeldet.")) return;
    try {
      await api(`/accounts/${remove.dataset.remove}`, { method: "DELETE" });
      toast("Account gelöst.", "ok");
    } catch (err) {
      toast(err.message, "error");
    }
    await loadAccounts();
    loadStats();
  }
});

$("#btnRefreshAll").addEventListener("click", async () => {
  for (const a of state.accounts) {
    try {
      await api(`/accounts/${a.id}/refresh`, { method: "POST" });
    } catch { /* Fehler steht danach am Account */ }
  }
  await loadAccounts();
  loadStats();
  toast("Alle Accounts geprüft.", "ok");
});

/* ── Geräte + Proxy ──────────────────────────────────────── */

async function loadDevices() {
  state.devices = await api("/devices");
  const grouped = {};
  state.devices.forEach((d) => (grouped[d.platform] ||= []).push(d));
  $("#fDevice").innerHTML = Object.entries(grouped).map(([platform, list]) =>
    `<optgroup label="${esc(platform)}">${
      list.map((d) => `<option value="${d.id}">${esc(d.name)}</option>`).join("")
    }</optgroup>`
  ).join("");
}

$("#fProxyType").addEventListener("change", (e) => {
  const isMt = e.target.value === "mtproto";
  $("#proxySecret").hidden = !isMt;
  $("#proxyAuth").hidden = isMt;
});

function readProxy() {
  const host = $("#fProxyHost").value.trim();
  if (!host) return null;
  return {
    type: $("#fProxyType").value,
    host,
    port: Number($("#fProxyPort").value) || null,
    username: $("#fProxyUser").value.trim(),
    password: $("#fProxyPass").value,
    secret: $("#fProxySecret").value.trim(),
  };
}

/* ── Login-Flow ──────────────────────────────────────────── */

$("#bindForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#btnBind");
  btn.disabled = true;
  btn.textContent = "Verbinde…";

  try {
    const res = await api("/accounts/login/start", {
      method: "POST",
      body: {
        label: $("#fLabel").value.trim(),
        phone: $("#fPhone").value.trim(),
        api_id: Number($("#fApiId").value),
        api_hash: $("#fApiHash").value.trim(),
        device_id: $("#fDevice").value,
        proxy: readProxy(),
      },
    });
    state.loginId = res.login_id;
    openModal("code");
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Code anfordern";
  }
});

function openModal(step) {
  const modal = $("#loginModal");
  modal.hidden = false;
  $("#modalError").hidden = true;
  const input = $("#fModalInput");
  input.value = "";

  if (step === "code") {
    $("#modalTitle").textContent = "Bestätigungscode";
    $("#modalText").textContent = "Telegram hat einen Code an deine Nummer geschickt.";
    $("#modalLabel").textContent = "Code";
    input.type = "text";
    input.inputMode = "numeric";
  } else {
    $("#modalTitle").textContent = "Zwei-Faktor-Passwort";
    $("#modalText").textContent = "Dieser Account ist zusätzlich mit einem Cloud-Passwort geschützt.";
    $("#modalLabel").textContent = "Passwort";
    input.type = "password";
    input.inputMode = "text";
  }
  modal.dataset.step = step;
  input.focus();
}

async function closeModal(cancel = true) {
  $("#loginModal").hidden = true;
  if (cancel && state.loginId) {
    try { await api(`/accounts/login/cancel/${state.loginId}`, { method: "POST" }); } catch {}
  }
  state.loginId = null;
}

$("#btnCloseModal").addEventListener("click", () => closeModal(true));

$("#modalForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const modal = $("#loginModal");
  const value = $("#fModalInput").value.trim();
  if (!value) return;

  const btn = $("#btnModalSubmit");
  btn.disabled = true;
  btn.textContent = "Prüfe…";
  $("#modalError").hidden = true;

  try {
    const path = modal.dataset.step === "code"
      ? "/accounts/login/code"
      : "/accounts/login/password";
    const body = modal.dataset.step === "code"
      ? { login_id: state.loginId, code: value }
      : { login_id: state.loginId, password: value };

    const res = await api(path, { method: "POST", body });

    if (res.step === "password") {
      openModal("password");
    } else {
      await closeModal(false);
      $("#bindForm").reset();
      $("#proxySecret").hidden = true;
      $("#proxyAuth").hidden = false;
      toast("Account gebunden.", "ok");
      await loadAccounts();
      loadStats();
    }
  } catch (err) {
    const box = $("#modalError");
    box.textContent = err.message;
    box.hidden = false;
  } finally {
    btn.disabled = false;
    btn.textContent = "Bestätigen";
  }
});

/* ── Pool ────────────────────────────────────────────────── */

const POOL_BADGE = {
  new:    ["badge-muted", "ungeprüft"],
  valid:  ["badge-ok", "gültig"],
  dead:   ["badge-danger", "tot"],
  error:  ["badge-warn", "Fehler"],
  added:  ["badge-accent", "aufgenommen"],
  joined: ["badge-accent", "beigetreten"],
};

function assignedLabel(entry) {
  if (!entry.assigned_to) return "";
  const a = state.accounts.find((x) => x.id === entry.assigned_to);
  const name = a ? a.label || a.first_name || a.phone : `Account ${entry.assigned_to}`;
  return `${entry.status === "valid" ? "reserviert für" : "über"} ${esc(name)}`;
}

function renderPool() {
  const body = $("#poolTable tbody");
  if (!state.pool.length) {
    body.innerHTML = '<tr><td colspan="5"><div class="empty">Keine Einträge.</div></td></tr>';
    return;
  }

  body.innerHTML = state.pool.map((p) => {
    const [cls, text] = POOL_BADGE[p.status] || ["badge-muted", p.status];
    return `
      <tr>
        <td class="cell-user">@${esc(p.username)}</td>
        <td>${esc(p.display || "–")}${p.is_premium ? ' <span class="badge badge-premium">★</span>' : ""}</td>
        <td>
          <span class="badge ${cls}">${esc(text)}</span>
          ${p.reason ? `<span class="cell-reason">${esc(p.reason)}</span>` : ""}
          ${assignedLabel(p) ? `<span class="cell-reason">${assignedLabel(p)}</span>` : ""}
        </td>
        <td class="cell-dim">${esc(p.note || "–")}</td>
        <td>
          <button class="icon-btn" data-del="${p.id}" title="Entfernen">
            <svg viewBox="0 0 24 24"><path d="M6 7h12l-1 13H7L6 7Zm3-4h6l1 2h4v2H4V5h4l1-2Z"/></svg>
          </button>
        </td>
      </tr>`;
  }).join("");
}

async function loadPool() {
  const params = new URLSearchParams();
  const status = $("#poolFilter").value;
  const search = $("#poolSearch").value.trim();
  if (status !== "all") params.set("status", status);
  if (search) params.set("q", search);
  state.pool = await api(`/pool?${params}`);
  renderPool();
  renderAddEstimate();
}

$("#poolForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const raw = $("#fPoolNames").value.trim();
  if (!raw) return;
  try {
    const res = await api("/pool", {
      method: "POST",
      body: { usernames: raw, note: $("#fPoolNote").value.trim() },
    });
    toast(`${res.added} hinzugefügt, ${res.skipped} Duplikate übersprungen.`, "ok");
    $("#fPoolNames").value = "";
    await loadPool();
    loadStats();
  } catch (err) {
    toast(err.message, "error");
  }
});

$("#poolTable").addEventListener("click", async (e) => {
  const del = e.target.closest("[data-del]");
  if (!del) return;
  await api(`/pool/${del.dataset.del}`, { method: "DELETE" });
  await loadPool();
  loadStats();
});

let searchTimer;
$("#poolSearch").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadPool, 250);
});
$("#poolFilter").addEventListener("change", loadPool);

$("#btnPurgeDead").addEventListener("click", async () => {
  // Unabhaengig vom gerade eingestellten Filter zaehlen.
  const dead = (await api("/pool?status=dead")).length;
  if (!dead) return toast("Keine toten Einträge im Pool.", "error");
  if (!confirm(`${dead} tote Einträge endgültig aus dem Pool löschen?`)) return;

  try {
    await api("/pool?status=dead", { method: "DELETE" });
    toast(`${dead} tote Einträge gelöscht.`, "ok");
    await loadPool();
    loadStats();
  } catch (err) {
    toast(err.message, "error");
  }
});

$("#btnExportPool").addEventListener("click", () => {
  if (!state.pool.length) return toast("Pool ist leer.", "error");
  const rows = [
    "username,name,status,grund,premium,notiz",
    ...state.pool.map((p) =>
      [
        p.username,
        p.display || "",
        p.status,
        p.reason || "",
        p.is_premium ? "ja" : "nein",
        p.note || "",
      ]
        .map((v) => `"${String(v).replace(/"/g, '""')}"`)
        .join(",")
    ),
  ];
  const url = URL.createObjectURL(new Blob([rows.join("\n")], { type: "text/csv" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "pool.csv";
  link.click();
  URL.revokeObjectURL(url);
});

$("#btnPoolCheck").addEventListener("click", async () => {
  const accountId = Number($("#fCheckAccount").value);
  if (!accountId) return toast("Zuerst einen Account binden.", "error");
  try {
    const res = await api("/jobs/pool-check", {
      method: "POST",
      body: { account_id: accountId, only_new: $("#fOnlyNew").checked },
    });
    toast("Prüfung gestartet.", "ok");
    state.activeJob = res.job_id;
    showView("jobs");
  } catch (err) {
    toast(err.message, "error");
  }
});

/* ── Vorgang ─────────────────────────────────────────────── */

$("#btnLoadGroups").addEventListener("click", async () => {
  const accountId = primaryOpAccount()?.id;
  if (!accountId) return toast("Zuerst einen Account wählen.", "error");

  const btn = $("#btnLoadGroups");
  btn.disabled = true;
  btn.textContent = "…";
  try {
    state.groups = await api(`/accounts/${accountId}/groups`);
    $("#fOpGroup").innerHTML = state.groups.length
      ? state.groups.map((g) =>
          `<option value="${esc(g.id)}"${g.can_invite ? "" : " disabled"}>${
            esc(g.title)}${g.can_invite ? "" : " (keine Einladungsrechte)"}</option>`
        ).join("")
      : '<option value="">– keine Gruppen gefunden –</option>';
    toast(`${state.groups.length} Gruppen geladen.`, "ok");
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Laden";
  }
});

function addCandidateCount() {
  // Nur was keinem Account zugewiesen ist, und aus der Gesamtstatistik
  // statt aus der gefilterten Tabellenansicht.
  const s = state.stats;
  if (!s) return 0;
  return $("#fOnlyValid").checked ? s.pool_free_valid : s.pool_free_open;
}

function renderOpAccounts() {
  const box = $("#opAccounts");
  if (!state.accounts.length) {
    box.innerHTML = '<div class="empty">Noch kein Account gebunden.</div>';
    return;
  }

  const chosen = new Set(state.opAccounts);
  box.innerHTML = state.accounts.map((a) => {
    const q = a.quota;
    const info = q.blocked
      ? `<span class="pick-warn" data-until="${q.cooldown_until}">frei in ${
          esc(countdown(q.seconds_left))}</span>`
      : `<span class="pick-dim">${q.remaining} frei</span>`;
    return `
      <label class="pick${q.blocked ? " is-blocked" : ""}">
        <input type="checkbox" value="${a.id}"${
          chosen.has(a.id) ? " checked" : ""}${q.blocked ? " disabled" : ""}>
        <span class="pick-name">${esc(a.label || a.first_name || a.phone)}${
          a.is_premium ? " ★" : ""}</span>
        ${info}
      </label>`;
  }).join("");
}

$("#opAccounts").addEventListener("change", () => {
  state.opAccounts = $$("#opAccounts input:checked").map((i) => Number(i.value));
  renderAddEstimate();
});

function selectedOpAccounts() {
  return state.accounts.filter(
    (a) => state.opAccounts.includes(a.id) && !a.quota.blocked
  );
}

/** Für alles, was nur einen Account braucht: Gruppen laden, Link, Anfragen.
 *  Das Kontingent spielt hier keine Rolle, es wird nichts aufgenommen. */
function primaryOpAccount() {
  return state.accounts.find((a) => a.id === state.opAccounts[0]) || null;
}

/** Verteilt den freien Pool der Reihe nach auf die gewählten Accounts. */
function planRun() {
  const delay = Number($("#fAddDelay").value);
  const limit = Number($("#fAddLimit").value);
  const accounts = selectedOpAccounts();

  let pool = addCandidateCount();
  const shares = accounts.map((a) => {
    const share = Math.min(limit || pool, a.quota.remaining, pool);
    pool -= share;
    return { account: a, count: share };
  });

  const total = shares.reduce((sum, s) => sum + s.count, 0);
  // Parallel: es dauert so lange wie der längste Anteil, nicht die Summe.
  const longest = shares.reduce((max, s) => Math.max(max, s.count), 0);
  const minutes = Math.round(((longest - 1) * delay) / 60);
  return { shares, total, minutes, available: addCandidateCount() };
}

function renderAddEstimate() {
  const box = $("#addEstimate");
  const accounts = selectedOpAccounts();

  if (!accounts.length) {
    const blocked = state.accounts.filter((a) => a.quota.blocked).length;
    box.textContent = state.opAccounts.length && blocked
      ? "Gewählte Accounts pausieren — abwarten oder freigeben."
      : "Account wählen.";
    return;
  }

  const { shares, total, minutes, available } = planRun();

  if (!total) {
    box.textContent = $("#fOnlyValid").checked
      ? "Keine freien geprüften Einträge — erst den Pool prüfen."
      : "Keine freien Einträge im Pool.";
    return;
  }

  const duration = minutes < 1 ? "unter einer Minute" : `rund ${minutes} Minuten`;
  const split = shares.length > 1
    ? " — " + shares
        .map((s) => `${esc(s.account.label || s.account.phone)}: ${s.count}`)
        .join(", ")
    : "";
  box.textContent =
    `${total} von ${available} freien Einträgen · Dauer ${duration}${split}.`;
}

["#fAddDelay", "#fAddLimit", "#fOnlyValid"].forEach((sel) =>
  $(sel).addEventListener("change", renderAddEstimate)
);

$("#btnStartAdd").addEventListener("click", async () => {
  const target = $("#fOpGroup").value;
  const accounts = selectedOpAccounts();
  if (!accounts.length) return toast("Mindestens einen Account wählen.", "error");
  if (!target) return toast("Gruppe wählen.", "error");
  if (!addCandidateCount()) return toast("Keine freien Pool-Einträge.", "error");

  try {
    const res = await api("/jobs/add", {
      method: "POST",
      body: {
        account_ids: accounts.map((a) => a.id),
        target,
        delay: Number($("#fAddDelay").value),
        limit: Number($("#fAddLimit").value),
        only_valid: $("#fOnlyValid").checked,
      },
    });
    state.activeJob = res.job_ids[0];
    toast(
      res.job_ids.length > 1
        ? `${res.job_ids.length} Vorgänge gestartet — sie laufen parallel.`
        : "Vorgang gestartet.",
      "ok"
    );
    showView("jobs");
  } catch (err) {
    toast(err.message, "error");
  }
});

$("#btnInvite").addEventListener("click", async () => {
  const accountId = primaryOpAccount()?.id;
  const target = $("#fOpGroup").value;
  if (!accountId || !target) return toast("Account und Gruppe wählen.", "error");

  const btn = $("#btnInvite");
  btn.disabled = true;
  try {
    const res = await api("/invite", {
      method: "POST",
      body: {
        account_id: accountId,
        target,
        title: $("#fLinkTitle").value.trim(),
        request_needed: true,
      },
    });
    $("#inviteLink").textContent = res.link;
    $("#inviteResult").hidden = false;
    toast("Einladungslink erzeugt.", "ok");
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
});

$("#btnCopyLink").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("#inviteLink").textContent);
    toast("Link kopiert.", "ok");
  } catch {
    toast("Kopieren nicht möglich – bitte manuell markieren.", "error");
  }
});

$("#btnLoadRequests").addEventListener("click", async () => {
  const accountId = primaryOpAccount()?.id;
  const target = $("#fOpGroup").value;
  if (!accountId || !target) return toast("Account und Gruppe wählen.", "error");

  const box = $("#requestList");
  box.innerHTML = '<div class="empty">Lade…</div>';
  try {
    const requests = await api(
      `/join-requests?account_id=${accountId}&target=${encodeURIComponent(target)}`
    );
    const poolNames = new Set(state.pool.map((p) => p.username.toLowerCase()));
    box.innerHTML = requests.length
      ? requests.map((r) => {
          const inPool = r.username && poolNames.has(r.username.toLowerCase());
          return `
            <div class="mini">
              <div>
                <div class="mini-title">${esc(r.name || r.username || r.user_id)}</div>
                <div class="mini-sub">${r.username ? "@" + esc(r.username) : "kein Username"}</div>
              </div>
              <span class="badge ${inPool ? "badge-ok" : "badge-muted"}">${
                inPool ? "im Pool" : "nicht im Pool"}</span>
            </div>`;
        }).join("")
      : '<div class="empty">Keine offenen Anfragen.</div>';
  } catch (err) {
    box.innerHTML = `<div class="empty">${esc(err.message)}</div>`;
  }
});

$("#btnStartOp").addEventListener("click", async () => {
  const accountId = primaryOpAccount()?.id;
  const target = $("#fOpGroup").value;
  if (!accountId || !target) return toast("Account und Gruppe wählen.", "error");

  try {
    const res = await api("/jobs/approve", {
      method: "POST",
      body: {
        account_id: accountId,
        target,
        pool_only: $("#fPoolOnly").checked,
        watch_minutes: Number($("#fWatch").value),
      },
    });
    state.activeJob = res.job_id;
    toast("Vorgang gestartet.", "ok");
    showView("jobs");
  } catch (err) {
    toast(err.message, "error");
  }
});

/* ── Jobs ────────────────────────────────────────────────── */

const JOB_LABEL = {
  pool_check: "Pool-Prüfung",
  add: "Mitglieder aufnehmen",
  approve: "Anfragen genehmigen",
};
const JOB_BADGE = {
  running:     ["badge-accent", "läuft"],
  paused:      ["badge-warn", "pausiert"],
  done:        ["badge-ok", "fertig"],
  error:       ["badge-danger", "Fehler"],
  cancelled:   ["badge-warn", "abgebrochen"],
  interrupted: ["badge-warn", "unterbrochen"],
};

function jobAccount(job) {
  const a = state.accounts.find((x) => x.id === job.account_id);
  return a ? esc(a.label || a.first_name || a.phone) : "";
}

function jobSummary(job) {
  const s = job.stats || {};
  if (job.kind === "pool_check") {
    return `${s.done ?? 0}/${s.total ?? 0} geprüft · ${s.ok ?? 0} gültig`;
  }
  if (job.kind === "add") {
    return `${s.done ?? 0}/${s.total ?? 0} · ${s.added ?? 0} aufgenommen · ${
      (s.privacy ?? 0) + (s.failed ?? 0)} tot`;
  }
  return `${s.approved ?? 0} genehmigt · ${s.skipped ?? 0} übersprungen`;
}

function renderJobs() {
  const box = $("#jobList");
  if (!state.jobs.length) {
    box.innerHTML = '<div class="empty">Noch keine Jobs.</div>';
    return;
  }
  box.innerHTML = state.jobs.map((j) => {
    const [cls, text] = JOB_BADGE[j.status] || ["badge-muted", j.status];
    return `
      <div class="mini${j.id === state.activeJob ? " is-active" : ""}" data-job="${j.id}">
        <div>
          <div class="mini-title">${esc(JOB_LABEL[j.kind] || j.kind)}${
            jobAccount(j) ? ` · ${jobAccount(j)}` : ""}</div>
          <div class="mini-sub">${esc(jobSummary(j))} · ${esc(timeAgo(j.created_at))}</div>
        </div>
        <span class="badge ${cls}">${esc(text)}</span>
      </div>`;
  }).join("");

  const dash = $("#dashJobs");
  dash.innerHTML = state.jobs.slice(0, 4).map((j) => {
    const [cls, text] = JOB_BADGE[j.status] || ["badge-muted", j.status];
    return `
      <div class="mini" data-job="${j.id}">
        <div>
          <div class="mini-title">${esc(JOB_LABEL[j.kind] || j.kind)}</div>
          <div class="mini-sub">${esc(jobSummary(j))}</div>
        </div>
        <span class="badge ${cls}">${esc(text)}</span>
      </div>`;
  }).join("") || '<div class="empty">Noch keine Jobs.</div>';
}

async function loadJobs() {
  state.jobs = await api("/jobs");
  renderJobs();
  if (state.activeJob) loadJobDetail(state.activeJob);
}

async function loadJobDetail(jobId) {
  const job = await api(`/jobs/${jobId}`);
  state.activeJob = jobId;
  $("#btnCancelJob").hidden = !["running", "paused"].includes(job.status);
  $("#btnResumeJob").hidden = job.status !== "paused";

  const s = job.stats || {};
  const hasProgress = ["pool_check", "add"].includes(job.kind) && s.total;
  const progress = hasProgress
    ? `<div class="progress"><i style="width:${Math.round((s.done / s.total) * 100)}%"></i></div>`
    : "";

  const lines = job.log.length
    ? job.log.map((entry) =>
        `<div class="log-line"><span class="log-time">${esc(clock(entry.t))}</span>
         <span class="log-${esc(entry.level)}">${esc(entry.msg)}</span></div>`
      ).join("")
    : '<div class="empty">Noch keine Ausgabe.</div>';

  $("#jobDetail").innerHTML = progress + lines;
  $$(".mini", $("#jobList")).forEach((el) =>
    el.classList.toggle("is-active", Number(el.dataset.job) === jobId)
  );
}

document.addEventListener("click", (e) => {
  const mini = e.target.closest("[data-job]");
  if (!mini) return;
  showView("jobs");
  loadJobDetail(Number(mini.dataset.job));
});

$("#btnResumeJob").addEventListener("click", async () => {
  if (!state.activeJob) return;
  const btn = $("#btnResumeJob");
  btn.disabled = true;
  try {
    await api(`/jobs/${state.activeJob}/resume`, { method: "POST" });
    toast("Go — Vorgang läuft weiter.", "ok");
  } catch (err) {
    toast(err.message, "error");
  }
  btn.disabled = false;
  loadJobs();
});

$("#btnCancelJob").addEventListener("click", async () => {
  if (!state.activeJob) return;
  await api(`/jobs/${state.activeJob}/cancel`, { method: "POST" });
  toast("Abbruch angefordert.", "ok");
  loadJobs();
});

/* ── Start ───────────────────────────────────────────────── */

$("#btnReload").addEventListener("click", () => refresh(true));

async function refresh(manual = false) {
  try {
    await Promise.all([loadStats(), loadAccounts(), loadPool(), loadJobs()]);
    if (manual) toast("Aktualisiert.", "ok");
  } catch (err) {
    if (manual) toast(err.message, "error");
  }
}

async function boot() {
  try {
    await loadDevices();
  } catch (err) {
    toast(err.message, "error");
  }
  await refresh();

  // Laufende Jobs live mitschreiben.
  state.poller = setInterval(async () => {
    try {
      await loadStats();
      if (state.jobs.some((j) => j.status === "running")) await loadJobs();
    } catch { /* Panel bleibt bedienbar */ }
  }, 3000);
}

boot();
