const state = { businesses: [], campaigns: [], pages: [], leads: [], audit: [], seo: null, growth: null, adPlans: [], seoBusiness: "all", growthBusiness: localStorage.getItem("growthBusiness") || "" };
const $ = (selector) => document.querySelector(selector);
const routes = new Set(["overview", "growth", "launch", "seo", "pages", "activity"]);

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

function setProcessing(active, title = "Processing", message = "Please wait while the agent completes the workflow.") {
  const overlay = $("#processing-overlay");
  $("#processing-title").textContent = title;
  $("#processing-message").textContent = message;
  overlay.hidden = !active;
  document.body.classList.toggle("is-processing", active);
}

async function withProcessing(title, message, action) {
  setProcessing(true, title, message);
  try {
    return await action();
  } finally {
    setProcessing(false);
  }
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

function formatPath(url) {
  try {
    return new URL(url).pathname;
  } catch {
    return url;
  }
}

function setRoute() {
  const route = routes.has(location.hash.slice(1)) ? location.hash.slice(1) : "overview";
  document.querySelectorAll(".route-view").forEach((section) => {
    section.classList.toggle("active", section.id === route);
  });
  document.querySelectorAll("nav a").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === route);
  });
  $(".breadcrumb").textContent = `Marketing Agent / ${route.replaceAll("-", " ")}`;
}

async function loadHealth() {
  const health = await api("/health");
  const liveCount = [health.openai_configured, health.dataforseo_configured, health.google_ads_configured].filter(Boolean).length;
  $("#health").textContent = liveCount ? `${liveCount}/3 live integrations` : "Deterministic mode";
}

async function loadBusinesses() {
  const current = $("#business-select")?.value;
  state.businesses = await api("/api/businesses");
  const select = $("#business-select");
  select.innerHTML = state.businesses.map((b) => `<option value="${b.id}">${b.name}</option>`).join("");
  if (current && state.businesses.some((business) => business.id === current)) {
    select.value = current;
  }
  renderGrowthBusinessFilter();
}

async function loadCampaigns() {
  state.campaigns = await api("/api/campaigns");
  renderAdCampaignOptions();
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

async function loadSeoOverview() {
  state.seo = await api("/api/seo/overview");
  $("#seo-mode").textContent = state.seo.integration_status.mode.replaceAll("_", " ");
  $("#seo-indexed").textContent = state.seo.indexed_pages;
  $("#seo-impressions").textContent = state.seo.organic_impressions.toLocaleString();
  $("#seo-clicks").textContent = state.seo.organic_clicks.toLocaleString();
  $("#seo-ctr").textContent = `${state.seo.ctr}%`;
  $("#seo-position").textContent = Number(state.seo.average_position).toFixed(1);
  $("#seo-sessions").textContent = state.seo.sessions.toLocaleString();
  $("#seo-leads").textContent = state.seo.leads.toLocaleString();
  renderSeoReadiness(state.seo.integration_status);
  renderSeoBusinessFilter(state.seo.page_scores);
  renderSeoPages(filteredSeoPages());
  renderSeoQueries(state.seo.top_queries);
}

async function loadGrowthOverview() {
  const query = state.growthBusiness ? `?business_id=${encodeURIComponent(state.growthBusiness)}` : "";
  state.growth = await api(`/api/growth/overview${query}`);
  if (!state.growthBusiness && state.growth.selected_business?.id) {
    state.growthBusiness = state.growth.selected_business.id;
    localStorage.setItem("growthBusiness", state.growthBusiness);
  }
  renderGrowthBusinessFilter();
  renderGrowthReadiness(state.growth.readiness, state.growth.mode);
  renderGrowthAgents(state.growth.agents);
  renderWorkspaces(state.growth.client_workspaces);
  renderReportingSnapshot(state.growth.reporting);
  renderGrowthOrchestration(state.growth.orchestration);
  renderGrowthLogs();
}

async function loadAdPlans() {
  state.adPlans = await api("/api/ads/plans");
  renderPaidAdPlans(state.adPlans);
  renderGrowthLogs();
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

function scoreClass(score) {
  if (score >= 80) return "good";
  if (score >= 65) return "medium";
  return "high";
}

function renderSeoBusinessFilter(items) {
  const select = $("#seo-business-filter");
  const current = state.seoBusiness;
  const companies = [...new Map(items
    .filter((page) => page.business_id)
    .map((page) => [page.business_id, page.business_name || "Unknown company"])
  ).entries()].sort((a, b) => a[1].localeCompare(b[1]));
  select.innerHTML = `<option value="all">All companies</option>${companies.map(([id, name]) => (
    `<option value="${escapeHtml(id)}">${escapeHtml(name)}</option>`
  )).join("")}`;
  select.value = companies.some(([id]) => id === current) ? current : "all";
  state.seoBusiness = select.value;
}

function filteredSeoPages() {
  const pages = state.seo?.page_scores || [];
  return state.seoBusiness === "all"
    ? pages
    : pages.filter((page) => page.business_id === state.seoBusiness);
}

function renderSeoPages(items) {
  $("#seo-refresh-count").textContent = `${items.filter((page) => page.overall_score < 70).length} need refresh`;
  $("#seo-pages-list").innerHTML = items.length ? items.map((page) => `
    <article class="seo-report-card">
      <div class="seo-report-head">
        <div>
          <span class="severity ${scoreClass(page.overall_score)}">SEO score ${Number(page.overall_score).toFixed(0)}</span>
          <h3>${escapeHtml(page.title)}</h3>
          <p>${escapeHtml(page.business_name || "Unknown company")} · Page: <a href="${escapeHtml(page.url)}" target="_blank" rel="noreferrer">${escapeHtml(formatPath(page.url))}</a></p>
        </div>
        <a class="button-link" href="${escapeHtml(page.url)}" target="_blank" rel="noreferrer">Open page</a>
      </div>
      <div class="seo-report-metrics">
        <span><small>Google impressions</small><strong>${page.impressions.toLocaleString()}</strong></span>
        <span><small>Google clicks</small><strong>${page.clicks.toLocaleString()}</strong></span>
        <span><small>CTR</small><strong>${Number(page.ctr).toFixed(2)}%</strong></span>
        <span><small>Average position</small><strong>${Number(page.average_position).toFixed(1)}</strong></span>
        <span><small>GA4 sessions</small><strong>${page.sessions.toLocaleString()}</strong></span>
        <span><small>Leads</small><strong>${page.leads.toLocaleString()}</strong></span>
        <span><small>Conversion rate</small><strong>${Number(page.conversion_rate).toFixed(1)}%</strong></span>
      </div>
      <div class="seo-report-action">
        <span>${escapeHtml(page.diagnosis)}</span>
        <strong>Recommendation: ${escapeHtml(page.next_action)}</strong>
      </div>
    </article>
  `).join("") : `<p class="empty">Run a campaign and sync SEO metrics to populate page scores.</p>`;
}

function renderSeoQueries(items) {
  $("#seo-queries-list").innerHTML = items.length ? items.map((item) => `
    <article class="query-card">
      <strong>${escapeHtml(item.query)}</strong>
      <span>${Number(item.impressions).toLocaleString()} impressions · ${Number(item.clicks).toLocaleString()} clicks · avg. ${Number(item.average_position).toFixed(1)}</span>
    </article>
  `).join("") : `<p class="empty">Search queries appear after SEO metric sync.</p>`;
}

function renderSeoReadiness(status) {
  const steps = status.setup_steps || [];
  const connections = status.connections || [];
  $("#seo-readiness").innerHTML = `
    <div>
      <strong>${escapeHtml(status.mode.replaceAll("_", " "))}</strong>
      <span>${connections.length ? escapeHtml(connections.map((item) => `${item.provider}: ${item.status}`).join(" · ")) : "Waiting for GA4 and Search Console credentials"}</span>
    </div>
    <div class="readiness-checks">
      ${steps.map((step) => `
        <span class="${step.complete ? "complete" : "pending"}">
          ${step.complete ? "✓" : "!"} ${escapeHtml(step.label)}
        </span>
      `).join("")}
    </div>
  `;
}

function renderGrowthReadiness(readiness, mode) {
  const seoMode = readiness.seo?.mode || "checking";
  const dataforseoMode = readiness.dataforseo?.mode || "ready_for_credentials";
  const googleAdsMode = readiness.google_ads?.mode || "ready_for_google_ads_credentials";
  const items = [
    { label: "OpenAI visibility", complete: readiness.openai?.configured, value: readiness.openai?.model || "not configured" },
    { label: "DataForSEO authority", complete: readiness.dataforseo?.configured, value: dataforseoMode },
    { label: "Google Ads API", complete: readiness.google_ads?.configured, value: googleAdsMode },
    { label: "GA4 + Search Console", complete: seoMode.includes("live") || seoMode.includes("configured"), value: seoMode },
  ];
  $("#growth-readiness").innerHTML = `
    <div class="readiness-title">
      <span>Suite mode</span>
      <strong>${escapeHtml(mode.replaceAll("_", " "))}</strong>
    </div>
    <div class="integration-tiles">
      ${items.map((item) => `
        <article class="${item.complete ? "ready" : "pending"}">
          <span>${item.complete ? "Ready" : "Pending"}</span>
          <strong>${escapeHtml(item.label)}</strong>
          <small>${escapeHtml(String(item.value).replaceAll("_", " "))}</small>
        </article>
      `).join("")}
    </div>
  `;
}

function renderGrowthAgents(agents) {
  $("#growth-agent-grid").innerHTML = agents.map((agent, index) => {
    const profile = agentProfile(agent.key || agent.name);
    const sources = agent.metric_sources || {};
    const metricEntries = Object.entries(agent.metrics || {})
      .filter(([, value]) => value !== null && value !== undefined && value !== "")
      .slice(0, agent.key === "backlink_authority" ? 5 : 4);
    return `
      <article class="growth-agent-card premium-agent-card">
        <div class="agent-card-top">
          <div class="agent-identity">
            <span class="agent-visual ${escapeHtml(profile.tone)}">
              <img src="/static/marketing-agent-logo.svg?v=metric-sources-20260708-1" alt="" />
              <b>${escapeHtml(profile.initials)}</b>
            </span>
            <span class="agent-number">${String(index + 1).padStart(2, "0")}</span>
          </div>
          <span class="agent-status ${escapeHtml(agent.status)}">${escapeHtml(agent.status.replaceAll("_", " "))}</span>
        </div>
        <h3>${escapeHtml(agent.name)}</h3>
        <div class="agent-section">
          <small>Purpose</small>
          <p>${escapeHtml(profile.purpose || agent.summary)}</p>
        </div>
        <div class="signal-tags">
          ${profile.signals.map((signal) => `<span>${escapeHtml(signal)}</span>`).join("")}
        </div>
        <div class="agent-metrics signal-board">
          ${metricEntries.map(([key, value]) => `
            <span>
              <small>${escapeHtml(key.replaceAll("_", " "))}</small>
              <strong>${escapeHtml(formatMetricValue(value))}</strong>
              <em class="metric-source ${escapeHtml(sourceTone(sources[key]))}" title="${escapeHtml(sourceHelp(sources[key]))}">
                ${escapeHtml(sources[key] || "Source pending")}
              </em>
            </span>
          `).join("")}
        </div>
        <div class="agent-section next-action">
          <small>Primary action</small>
          <p>${escapeHtml(profile.action)}</p>
        </div>
        <div class="agent-recs">
          ${(agent.recommendations || []).slice(0, 2).map((rec) => `
            <div>
              <strong>${escapeHtml(rec.title || "Recommendation")}</strong>
              <span>${escapeHtml(rec.impact || "")}</span>
            </div>
          `).join("")}
        </div>
      </article>
    `;
  }).join("");
}

function sourceTone(source) {
  const value = String(source || "").toLowerCase();
  if (value.includes("live")) return "live";
  if (value.includes("app db")) return "db";
  if (value.includes("ai")) return "ai";
  if (value.includes("fallback") || value.includes("demo")) return "fallback";
  if (value.includes("configured") || value.includes("waiting")) return "pending";
  return "config";
}

function sourceHelp(source) {
  const value = String(source || "");
  const normalized = value.toLowerCase();
  if (normalized.includes("live google search console")) return "Real search performance from Google Search Console after sync.";
  if (normalized.includes("live ga4")) return "Real page/session analytics from GA4 after sync.";
  if (normalized.includes("live google ads")) return "Real campaign metrics returned by Google Ads API.";
  if (normalized.includes("live dataforseo")) return "Real backlink and authority metrics returned by DataForSEO for the selected business domain.";
  if (normalized.includes("app db")) return "Count or value stored inside the Marketing Agent database.";
  if (normalized.includes("ai estimate")) return "Calculated by the OpenAI-powered agent, not a direct Google metric.";
  if (normalized.includes("fallback") || normalized.includes("demo")) return "Temporary deterministic value used until the live provider has usable data.";
  if (normalized.includes("configured") || normalized.includes("waiting")) return "Credentials exist, but the provider has not returned usable page-level data yet.";
  if (normalized.includes("configuration")) return "Static product or governance setting controlled by the app.";
  return value || "Metric source has not been classified yet.";
}

function agentProfile(key) {
  const normalized = String(key || "").toLowerCase();
  const profiles = {
    ai_search_visibility: {
      initials: "AI",
      tone: "ai",
      purpose: "Audits whether your brand and pages are likely to appear in ChatGPT/OpenAI answer journeys.",
      signals: ["OpenAI answers", "Brand proof", "Top pages"],
      action: "Create answer-ready explainers, comparison pages, and structured proof blocks.",
    },
    backlink_authority: {
      initials: "BA",
      tone: "authority",
      purpose: "Finds backlink gaps, authority opportunities, and keyword demand from DataForSEO-backed signals.",
      signals: ["DataForSEO", "Referring domains", "Keyword gaps"],
      action: "Prioritize authority-building topics and partner outreach around high-intent demand.",
    },
    auto_refresh_approval: {
      initials: "AR",
      tone: "refresh",
      purpose: "Turns weak CTR, traffic, and lead signals into owner-approved page refresh plans.",
      signals: ["GSC CTR", "GA4 sessions", "Lead rate"],
      action: "Queue low-performing pages for content depth, internal links, and CTA improvements.",
    },
    paid_campaigns: {
      initials: "AD",
      tone: "ads",
      purpose: "Drafts, validates, and safely pushes paused Google Ads campaigns from proven SEO pages.",
      signals: ["Google Ads", "Budgets", "Search themes"],
      action: "Map winning organic pages to Search/Performance Max plans with manual approval.",
    },
    client_reporting: {
      initials: "CR",
      tone: "reporting",
      purpose: "Packages SEO, leads, paid activity, and refresh decisions into client-ready reporting.",
      signals: ["Client KPIs", "Page health", "Leads"],
      action: "Produce weekly summaries that explain what changed, why it changed, and what is next.",
    },
    client_workspace_access: {
      initials: "CW",
      tone: "workspace",
      purpose: "Partitions pages, leads, and metrics by business so each client view stays clean.",
      signals: ["Business ID", "Roles", "Governance"],
      action: "Keep reporting filtered by company and prepare role-based access for external rollout.",
    },
  };
  return profiles[normalized] || {
    initials: "AG",
    tone: "default",
    purpose: "Coordinates one part of the autonomous growth workflow.",
    signals: ["Automation", "Audit log", "Client output"],
    action: "Review recommendations and approve the next high-impact action.",
  };
}

function renderGrowthLogs() {
  const list = $("#growth-log-list");
  if (!list) return;
  const relevantActions = new Set([
    "growth_suite_synced",
    "seo_metrics_synced",
    "paid_ad_plan_drafted",
    "paid_ad_plan_validated",
    "paid_ad_plan_pushed",
    "campaign_created",
    "agent_loop_completed",
    "business_profile_saved",
    "landing_pages_created",
  ]);
  const events = state.audit
    .filter((event) => relevantActions.has(event.action) || String(event.actor || "").includes("agent"))
    .slice(0, 5);
  list.innerHTML = events.length ? events.map((event) => `
    <article class="agent-log-row">
      <span class="log-dot ${escapeHtml(logTone(event.action))}"></span>
      <div>
        <strong>${escapeHtml(actionLabel(event.action))}</strong>
        <small>${escapeHtml(event.actor || "system")} · ${escapeHtml(formatDate(event.created_at))}</small>
      </div>
    </article>
  `).join("") : `
    <p class="empty">Run the growth suite or agent loop to populate live operating logs.</p>
  `;
}

function actionLabel(action) {
  return String(action || "event").replaceAll("_", " ");
}

function logTone(action) {
  if (String(action).includes("paid")) return "ads";
  if (String(action).includes("seo")) return "seo";
  if (String(action).includes("growth")) return "growth";
  if (String(action).includes("business")) return "memory";
  return "default";
}

function formatMetricValue(value) {
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

function renderWorkspaces(workspaces) {
  $("#workspace-list").innerHTML = workspaces.length ? workspaces.map((workspace) => `
    <article class="workspace-row">
      <div>
        <strong>${escapeHtml(workspace.name)}</strong>
        <span>${escapeHtml(workspace.industry)} · ${workspace.campaigns} campaigns · ${workspace.pages} pages · ${workspace.leads} leads</span>
      </div>
      <a href="#seo" class="button-link subtle">Open metrics</a>
    </article>
  `).join("") : `<p class="empty">Create a business to generate its client workspace.</p>`;
}

function renderGrowthBusinessFilter() {
  const select = $("#growth-business-filter");
  if (!select) return;
  const current = state.growthBusiness || state.growth?.selected_business?.id || "";
  select.innerHTML = state.businesses.length
    ? state.businesses.map((business) => {
      const website = business.website ? ` · ${business.website.replace(/^https?:\/\//, "").replace(/^www\./, "")}` : " · no website";
      return `<option value="${escapeHtml(business.id)}">${escapeHtml(business.name)}${escapeHtml(website)}</option>`;
    }).join("")
    : `<option value="">Create a business first</option>`;
  if (current && state.businesses.some((business) => business.id === current)) {
    select.value = current;
  }
}

function renderReportingSnapshot(reporting) {
  const entries = [
    ["Clients", reporting.client_count],
    ["Campaigns", reporting.campaign_count],
    ["Published pages", reporting.published_pages],
    ["Leads", reporting.lead_count],
    ["Avg. page health", reporting.average_page_health],
  ];
  $("#reporting-snapshot").innerHTML = `
    <h3>${escapeHtml(reporting.headline || "Client report")}</h3>
    <p>${escapeHtml(reporting.next_board_action || "")}</p>
    <div>
      ${entries.map(([label, value]) => `
        <span><small>${escapeHtml(label)}</small><strong>${escapeHtml(formatMetricValue(value || 0))}</strong></span>
      `).join("")}
    </div>
  `;
}

function renderGrowthOrchestration(items) {
  $("#growth-orchestration").innerHTML = items.map((item) => `
    <article>
      <span>${String(item.step).padStart(2, "0")}</span>
      <div>
        <strong>${escapeHtml(item.agent)}</strong>
        <p>${escapeHtml(item.summary)}</p>
      </div>
      <em>${escapeHtml(item.status.replaceAll("_", " "))}</em>
    </article>
  `).join("");
}

function renderAdCampaignOptions() {
  const select = $("#ad-campaign-select");
  if (!select) return;
  const current = select.value;
  select.innerHTML = state.campaigns.length
    ? state.campaigns.map((campaign) => `<option value="${campaign.id}">${escapeHtml(campaign.name)}</option>`).join("")
    : `<option value="">Create a campaign first</option>`;
  if (current && state.campaigns.some((campaign) => campaign.id === current)) {
    select.value = current;
  }
}

function renderPaidAdPlans(plans) {
  const list = $("#paid-plan-list");
  if (!list) return;
  list.innerHTML = plans.length ? plans.slice(0, 6).map((plan) => {
    const keywords = (plan.plan?.keywords || []).slice(0, 5).map((item) => item.text || item).join(", ");
    const finalUrl = (plan.plan?.final_urls || [])[0] || "-";
    return `
      <article class="paid-plan-card">
        <div class="paid-plan-main">
          <div>
            <span class="status-chip ${escapeHtml(plan.status)}">${escapeHtml(plan.status.replaceAll("_", " "))}</span>
            <h3>${escapeHtml(plan.name)}</h3>
            <p>${escapeHtml(plan.objective)}</p>
          </div>
          <div class="paid-plan-metrics">
            <span><small>Budget/day</small><strong>${formatCurrency(plan.daily_budget_micros)}</strong></span>
            <span><small>Region</small><strong>${escapeHtml(plan.target_region)}</strong></span>
            <span><small>Approval</small><strong>${escapeHtml(plan.approval_status.replaceAll("_", " "))}</strong></span>
          </div>
        </div>
        <div class="paid-plan-assets">
          <span><strong>Keywords</strong>${escapeHtml(keywords || "No keywords")}</span>
          <span><strong>Landing URL</strong>${escapeHtml(finalUrl)}</span>
        </div>
        <div class="paid-plan-actions">
          <button type="button" data-ad-action="validate" data-plan-id="${escapeHtml(plan.id)}">Validate with Google</button>
          <button type="button" class="danger-soft" data-ad-action="push" data-plan-id="${escapeHtml(plan.id)}">Approve & push paused campaign</button>
        </div>
      </article>
    `;
  }).join("") : `<p class="empty">Draft a Google Ads plan from an existing campaign. Nothing is pushed to Google until you approve it.</p>`;
}

function formatCurrency(micros) {
  const value = Number(micros || 0) / 1_000_000;
  return `₹${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
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
  renderGrowthLogs();
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
  await Promise.all([loadBusinesses(), loadCampaigns(), loadDashboard(), loadPages(), loadLeads(), loadAudit(), loadSeoOverview(), loadGrowthOverview(), loadAdPlans()]);
}

$("#business-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await withProcessing("Saving business memory", "The Business Memory Agent is storing profile, website, audience, offers, and brand context.", async () => {
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
    await refreshAll();
  });
  toast("Business memory saved");
});

$("#campaign-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await withProcessing("Running agent loop", "Research, content creation, lead-page publishing, analytics, and audit events are being generated.", async () => {
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
    await api("/api/seo/sync", { method: "POST", body: JSON.stringify({}) });
    await refreshAll();
  });
  toast("Agent loop completed");
});

$("#refresh-pages").addEventListener("click", refreshAll);
$("#sync-seo").addEventListener("click", async () => {
  await withProcessing("Syncing SEO analytics", "The SEO Analytics Agent is collecting page, query, engagement, and conversion metrics.", async () => {
    await api("/api/seo/sync", { method: "POST", body: JSON.stringify({}) });
    await refreshAll();
  });
  toast("SEO metrics synced");
});
$("#sync-growth").addEventListener("click", async () => {
  await withProcessing("Running growth suite", "AI visibility, authority, paid campaign readiness, reporting, workspaces, and refresh approvals are being coordinated.", async () => {
    const query = state.growthBusiness ? `?business_id=${encodeURIComponent(state.growthBusiness)}` : "";
    await api(`/api/growth/sync${query}`, { method: "POST", body: JSON.stringify({}) });
    await refreshAll();
  });
  toast("Growth suite synced");
});
$("#ad-plan-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await withProcessing("Drafting Google Ads plan", "The Paid Campaign Agent is converting SEO pages and campaign goals into a paused Google Ads plan.", async () => {
    await api("/api/ads/plans/draft", {
      method: "POST",
      body: JSON.stringify({
        campaign_id: form.get("campaign_id") || null,
        daily_budget: Number(form.get("daily_budget") || 5),
        currency_code: "INR",
      }),
    });
    await Promise.all([loadAdPlans(), loadGrowthOverview(), loadAudit()]);
  });
  toast("Google Ads plan drafted");
});
$("#paid-plan-list").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-ad-action]");
  if (!button) return;
  const planId = button.dataset.planId;
  const action = button.dataset.adAction;
  if (action === "validate") {
    await withProcessing("Validating Google Ads plan", "Google Ads API is checking the plan without creating or changing live campaigns.", async () => {
      await api(`/api/ads/plans/${planId}/validate`, { method: "POST", body: JSON.stringify({}) });
      await Promise.all([loadAdPlans(), loadGrowthOverview(), loadAudit()]);
    });
    toast("Google Ads plan validated");
    return;
  }
  if (action === "push") {
    const approved = window.confirm("This will send the plan to Google Ads. Campaigns and ads are created/kept PAUSED by default, but this is still a live Google Ads account change. Continue?");
    if (!approved) return;
    await withProcessing("Pushing paused Google Ads campaign", "The Paid Campaign Agent is creating or updating paused Google Ads resources after owner approval.", async () => {
      await api(`/api/ads/plans/${planId}/push`, {
        method: "POST",
        body: JSON.stringify({ approve_google_push: true, mode: "publish" }),
      });
      await Promise.all([loadAdPlans(), loadGrowthOverview(), loadAudit()]);
    });
    toast("Google Ads push completed");
  }
});
$("#seo-business-filter").addEventListener("change", (event) => {
  state.seoBusiness = event.target.value;
  renderSeoPages(filteredSeoPages());
});
$("#growth-business-filter").addEventListener("change", async (event) => {
  state.growthBusiness = event.target.value;
  localStorage.setItem("growthBusiness", state.growthBusiness);
  await withProcessing("Switching authority target", "The Backlink / Authority Agent is loading DataForSEO metrics for the selected company.", async () => {
    await loadGrowthOverview();
  });
  toast("Authority target updated");
});
$("#refresh-businesses").addEventListener("click", async () => {
  await withProcessing("Refreshing businesses", "Loading the latest saved business profiles into the campaign dropdown.", loadBusinesses);
  toast("Business list refreshed");
});

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
window.addEventListener("hashchange", setRoute);
setRoute();
