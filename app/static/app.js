const state = { businesses: [], campaigns: [], pages: [], leads: [], audit: [] };
const $ = (selector) => document.querySelector(selector);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail || "Request failed");
  }
  return response.json();
}

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.hidden = false;
  setTimeout(() => { el.hidden = true; }, 3400);
}

function asList(value) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString([], {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }) : "-";
}

async function loadHealth() {
  const health = await api("/health");
  $("#health").textContent = health.openai_configured ? "OpenAI ready" : "Deterministic mode";
}

async function loadBusinesses() {
  state.businesses = await api("/api/businesses");
  const select = $("#business-select");
  select.innerHTML = state.businesses.map((b) => `<option value="${b.id}">${b.name}</option>`).join("");
}

async function loadDashboard() {
  const data = await api("/api/dashboard");
  $("#m-businesses").textContent = data.businesses;
  $("#m-campaigns").textContent = data.campaigns;
  $("#m-pages").textContent = data.pages;
  $("#m-leads").textContent = data.leads;
  $("#m-visits").textContent = data.visits;
  $("#m-rate").textContent = `${data.conversion_rate}%`;
  renderRecommendations(data.recommendations);
}

async function loadPages() {
  state.pages = await api("/api/pages");
  const list = $("#pages-list");
  list.innerHTML = state.pages.length ? state.pages.map((page) => `
    <article class="row-card">
      <div>
        <h3>${escapeHtml(page.title)}</h3>
        <p>${escapeHtml(page.hero)}</p>
        <span>${escapeHtml(page.status)} · ${page.visits} visits · ${page.conversions} leads</span>
      </div>
      <a class="button-link" href="/p/${escapeHtml(page.slug)}" target="_blank" rel="noreferrer">Open</a>
    </article>
  `).join("") : `<p class="empty">No pages generated yet.</p>`;
}

function renderRecommendations(items) {
  $("#recommendations-list").innerHTML = items.length ? items.map((item) => `
    <article class="row-card">
      <div>
        <span class="severity ${escapeHtml(item.severity)}">${escapeHtml(item.severity)}</span>
        <h3>${escapeHtml(item.recommendation)}</h3>
        <p>${escapeHtml(item.expected_impact)}</p>
      </div>
    </article>
  `).join("") : `<p class="empty">Recommendations appear after a campaign run.</p>`;
}

async function loadLeads() {
  state.leads = await api("/api/leads");
  renderLeadsTable(state.leads);
}

function renderLeadsTable(items) {
  $("#recent-lead-count").textContent = items.length;
  $("#leads-table-body").innerHTML = items.length ? items.slice(0, 8).map((lead) => `
    <tr>
      <td>
        <strong>${escapeHtml(lead.name)}</strong>
        <small>${escapeHtml(lead.email)}</small>
      </td>
      <td>${escapeHtml(lead.company || "-")}</td>
      <td><span class="status-chip ${escapeHtml(lead.status)}">${escapeHtml(lead.status)}</span></td>
      <td><strong>${Number(lead.score).toFixed(0)}</strong></td>
    </tr>
  `).join("") : `<tr><td colspan="4">Captured leads will appear here.</td></tr>`;
}

async function loadAudit() {
  state.audit = await api("/api/audit");
  renderAuditTable(state.audit);
}

function renderAuditTable(items) {
  $("#audit-count").textContent = items.length;
  $("#audit-table-body").innerHTML = items.length ? items.slice(0, 8).map((event) => `
    <tr>
      <td><strong>${escapeHtml(event.actor)}</strong></td>
      <td>${escapeHtml(event.action)}</td>
      <td>${escapeHtml(formatDate(event.created_at))}</td>
    </tr>
  `).join("") : `<tr><td colspan="3">Audit events will appear here.</td></tr>`;
}

async function refreshAll() {
  await Promise.all([loadBusinesses(), loadDashboard(), loadPages(), loadLeads(), loadAudit()]);
}

$("#business-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await api("/api/businesses", {
    method: "POST",
    body: JSON.stringify({
      name: form.get("name"),
      website: form.get("website") || null,
      industry: form.get("industry"),
      audience: form.get("audience"),
      value_proposition: form.get("value_proposition"),
      offers: asList(form.get("offers") || ""),
      competitors: asList(form.get("competitors") || ""),
      tone: form.get("tone") || "professional",
    }),
  });
  toast("Business memory saved");
  await refreshAll();
});

$("#campaign-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const campaign = await api("/api/campaigns", {
    method: "POST",
    body: JSON.stringify({
      business_id: form.get("business_id"),
      name: form.get("name"),
      goal: form.get("goal"),
      target_region: form.get("target_region") || "United States",
    }),
  });
  await api("/api/runs", {
    method: "POST",
    body: JSON.stringify({
      campaign_id: campaign.id,
      publish_pages: form.get("publish_pages") === "on",
    }),
  });
  toast("Agent loop completed");
  await refreshAll();
});

$("#refresh-pages").addEventListener("click", refreshAll);

document.querySelectorAll(".tab-button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab-button").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    $(`#${button.dataset.tab}-panel`).classList.add("active");
  });
});

loadHealth().catch((error) => toast(error.message));
refreshAll().catch((error) => toast(error.message));
