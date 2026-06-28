const state = { businesses: [], campaigns: [], pages: [] };
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
  renderLeads(data.recent_leads);
}

async function loadPages() {
  state.pages = await api("/api/pages");
  const list = $("#pages-list");
  list.innerHTML = state.pages.length ? state.pages.map((page) => `
    <article class="row-card">
      <div>
        <h3>${page.title}</h3>
        <p>${page.hero}</p>
        <span>${page.status} · ${page.visits} visits · ${page.conversions} leads</span>
      </div>
      <a class="button-link" href="/p/${page.slug}" target="_blank" rel="noreferrer">Open</a>
    </article>
  `).join("") : `<p class="empty">No pages generated yet.</p>`;
}

function renderRecommendations(items) {
  $("#recommendations-list").innerHTML = items.length ? items.map((item) => `
    <article class="row-card">
      <div>
        <span class="severity ${item.severity}">${item.severity}</span>
        <h3>${item.recommendation}</h3>
        <p>${item.expected_impact}</p>
      </div>
    </article>
  `).join("") : `<p class="empty">Recommendations appear after a campaign run.</p>`;
}

function renderLeads(items) {
  $("#leads-list").innerHTML = items.length ? items.map((lead) => `
    <article class="row-card">
      <div>
        <h3>${lead.name}</h3>
        <p>${lead.email}${lead.company ? ` · ${lead.company}` : ""}</p>
        <span>${lead.status} · score ${lead.score}</span>
      </div>
    </article>
  `).join("") : `<p class="empty">Captured leads will appear here.</p>`;
}

async function loadAudit() {
  const events = await api("/api/audit");
  $("#audit-list").innerHTML = events.length ? events.map((event) => `
    <article>
      <strong>${event.actor}</strong>
      <span>${event.action}</span>
      <small>${new Date(event.created_at).toLocaleString()}</small>
    </article>
  `).join("") : `<p class="empty">No audit events yet.</p>`;
}

async function refreshAll() {
  await Promise.all([loadBusinesses(), loadDashboard(), loadPages(), loadAudit()]);
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

loadHealth().catch((error) => toast(error.message));
refreshAll().catch((error) => toast(error.message));

