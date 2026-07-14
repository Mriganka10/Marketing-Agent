const state = { businesses: [], campaigns: [], pages: [], leads: [], audit: [], seo: null, growth: null, googleReports: null, googleCompany: "all", googlePage: "all", googlePageQuery: "", adPlans: [], seoBusiness: "all", growthBusiness: localStorage.getItem("growthBusiness") || "" };
const $ = (selector) => document.querySelector(selector);
const routes = new Set(["overview", "growth", "launch", "seo", "google", "pages", "activity"]);
const routeTitles = {
  overview: "Command center",
  growth: "Growth suite",
  launch: "Launch workspace",
  seo: "SEO intelligence",
  google: "Google reports",
  pages: "Content operations",
  activity: "Activity control room",
};

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

function parseApiDate(value) {
  if (!value) return null;
  const text = String(value);
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(text);
  return new Date(hasTimezone || !text.includes("T") ? text : `${text}Z`);
}

function formatDate(value) {
  const parsed = parseApiDate(value);
  return parsed ? parsed.toLocaleString([], {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }) : "-";
}

function formatIstDate(value) {
  const parsed = parseApiDate(value);
  if (!parsed) return "-";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
    timeZoneName: "short",
  }).format(parsed).replace(/\b(am|pm)\b/gi, (match) => match.toUpperCase());
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
  $("#route-title").textContent = routeTitles[route];
  document.body.classList.remove("nav-open");
  $("#mobile-nav-toggle").setAttribute("aria-expanded", "false");
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
  renderOverviewCharts(data);
  renderRecommendations(data.recommendations);
}

function renderOverviewCharts(data) {
  const metrics = [
    ["Businesses", data.businesses],
    ["Campaigns", data.campaigns],
    ["Pages", data.pages],
    ["Leads", data.leads],
    ["Visits", data.visits],
  ];
  const maxValue = Math.max(...metrics.map(([, value]) => Number(value) || 0), 1);
  $("#overview-volume-chart").innerHTML = metrics.map(([label, value]) => `
    <div class="chart-column">
      <strong>${Number(value).toLocaleString()}</strong>
      <span class="chart-bar" style="--bar-size: ${Math.max(8, Math.round((Number(value) / maxValue) * 100))}%"></span>
      <small>${escapeHtml(label)}</small>
    </div>
  `).join("");
  const visits = Number(data.visits) || 0;
  const leads = Number(data.leads) || 0;
  const leadWidth = visits ? Math.max(8, Math.min(100, (leads / visits) * 100)) : 8;
  $("#overview-funnel-rate").textContent = `${Number(data.conversion_rate || 0)}% conversion`;
  $("#overview-funnel").innerHTML = `
    <div><span>Visits</span><strong>${visits.toLocaleString()}</strong><i style="--funnel-size: 100%"></i></div>
    <div><span>Leads</span><strong>${leads.toLocaleString()}</strong><i style="--funnel-size: ${leadWidth}%"></i></div>
  `;
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
  setMetricSource("#seo-indexed-source", state.seo.metric_sources.indexed_pages);
  setMetricSource("#seo-impressions-source", state.seo.metric_sources.organic_impressions);
  setMetricSource("#seo-clicks-source", state.seo.metric_sources.organic_clicks);
  setMetricSource("#seo-ctr-source", state.seo.metric_sources.ctr);
  setMetricSource("#seo-position-source", state.seo.metric_sources.average_position);
  setMetricSource("#seo-sessions-source", state.seo.metric_sources.sessions);
  setMetricSource("#seo-leads-source", state.seo.metric_sources.leads);
  renderSeoReadiness(state.seo.integration_status);
  renderSeoBusinessFilter(state.seo.page_scores);
  renderSeoPages(filteredSeoPages());
  renderSeoQueries(state.seo.top_queries);
  renderActivityEvents(state.seo.page_scores);
}

async function loadGoogleReports() {
  state.googleReports = await api("/api/google-reports");
  renderGoogleCompanyFilter();
  renderGooglePageFilter();
  renderGoogleReports();
}

function setMetricSource(selector, source) {
  const element = $(selector);
  if (!element) return;
  element.textContent = source || "Source pending";
  element.className = `metric-source ${sourceTone(source)}`;
  element.title = sourceHelp(source);
}

function sourceBadge(source) {
  return `<em class="metric-source ${escapeHtml(sourceTone(source))}" title="${escapeHtml(sourceHelp(source))}">${escapeHtml(source || "Source pending")}</em>`;
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
    <article class="row-card refresh-plan-card">
      <div class="refresh-plan-copy">
        <div class="refresh-plan-status">
          <span class="severity ${escapeHtml(item.severity)}">${escapeHtml(item.severity)}</span>
          <span class="approval-state ${escapeHtml(item.refresh_plan?.status || "not_drafted")}">${escapeHtml((item.refresh_plan?.status || "not drafted").replaceAll("_", " "))}</span>
        </div>
        <h3>${escapeHtml(item.recommendation)}</h3>
        <p>${escapeHtml(item.expected_impact)}</p>
        ${item.refresh_plan ? `
          ${item.refresh_plan.proposed_content.performance_snapshot?.overall_score !== undefined ? `
            <div class="performance-snapshot">
              <strong>Performance snapshot</strong>
              <span>SEO score ${escapeHtml(item.refresh_plan.proposed_content.performance_snapshot.overall_score)}/100</span>
              <span>${escapeHtml(item.refresh_plan.proposed_content.performance_snapshot.impressions || 0)} impressions</span>
              <span>${escapeHtml(item.refresh_plan.proposed_content.performance_snapshot.ctr || 0)}% CTR</span>
              <span>${escapeHtml(item.refresh_plan.proposed_content.performance_snapshot.sessions || 0)} sessions</span>
              <span>${escapeHtml(item.refresh_plan.proposed_content.performance_snapshot.conversion_rate || 0)}% conversion</span>
              <p>${escapeHtml(item.refresh_plan.proposed_content.performance_snapshot.diagnosis || "")}</p>
            </div>
          ` : ""}
          <div class="rewrite-preview">
            <small>Proposed rewrite</small>
            <strong>${escapeHtml(item.refresh_plan.proposed_content.title)}</strong>
            <span>${escapeHtml(item.refresh_plan.change_summary)}</span>
            ${item.refresh_plan.proposed_content.exact_changes?.length ? `
              <div class="exact-change-list">
                <small>Exact changes queued for approval</small>
                ${item.refresh_plan.proposed_content.exact_changes.map((change) => `
                  <div class="exact-change">
                    <strong>${escapeHtml(change.field)}</strong>
                    <span><b>Current:</b> ${escapeHtml(change.current)}</span>
                    <span><b>Recommended:</b> ${escapeHtml(change.recommended)}</span>
                    <em>${escapeHtml(change.reason)}</em>
                  </div>
                `).join("")}
              </div>
            ` : ""}
            ${item.refresh_plan.approved_by ? `<em>Approved by ${escapeHtml(item.refresh_plan.approved_by)}</em>` : ""}
            ${item.refresh_plan.rejection_reason ? `<em>Rejected: ${escapeHtml(item.refresh_plan.rejection_reason)}</em>` : ""}
          </div>
        ` : ""}
      </div>
      <div class="refresh-plan-actions">
        ${!item.refresh_plan && item.page_id ? `<button data-refresh-action="rewrite" data-recommendation-id="${item.id}">Generate rewrite</button>` : ""}
        ${item.refresh_plan?.status === "pending_approval" ? `
          <button data-refresh-action="approve" data-recommendation-id="${item.id}">Approve rewrite</button>
          <button class="ghost danger" data-refresh-action="reject" data-recommendation-id="${item.id}">Reject</button>
        ` : ""}
        ${item.refresh_plan?.status === "approved" ? `
          <button data-refresh-action="publish" data-recommendation-id="${item.id}">Publish approved version</button>
          <button class="ghost danger" data-refresh-action="reject" data-recommendation-id="${item.id}">Reject</button>
        ` : ""}
        ${item.refresh_plan?.status === "rejected" ? `<button data-refresh-action="rewrite" data-recommendation-id="${item.id}">Generate revised rewrite</button>` : ""}
        ${item.refresh_plan?.status === "published" ? `<a class="button-link" href="#pages">Review published page</a>` : ""}
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
      ${renderIndexHelper(page)}
      <div class="seo-report-action">
        <span>${escapeHtml(page.diagnosis)}</span>
        <strong>Recommendation: ${escapeHtml(page.next_action)}</strong>
      </div>
    </article>
  `).join("") : `<p class="empty">Run a campaign and sync SEO metrics to populate page scores.</p>`;
}

function googleCompanies() {
  const pages = state.googleReports?.search_console?.pages || [];
  return [...new Set(pages.map((page) => page.business).filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

function renderGoogleCompanyFilter() {
  const companies = googleCompanies();
  if (state.googleCompany !== "all" && !companies.includes(state.googleCompany)) state.googleCompany = "all";
  $("#google-company-options").innerHTML = companies.map((company) => `<option value="${escapeHtml(company)}"></option>`).join("");
  const input = $("#google-company-search");
  if (document.activeElement !== input) input.value = state.googleCompany === "all" ? "" : state.googleCompany;
  $("#google-company-search-status").textContent = state.googleCompany === "all"
    ? `${companies.length} companies available · start typing for suggestions`
    : `Showing landing pages for ${state.googleCompany}`;
}

function googleCompanyPages() {
  const pages = state.googleReports?.search_console?.pages || [];
  return state.googleCompany === "all" ? pages : pages.filter((page) => page.business === state.googleCompany);
}

function applyGoogleCompany(company) {
  const nextCompany = company || "all";
  const changed = state.googleCompany !== nextCompany;
  state.googleCompany = nextCompany;
  if (changed) {
    state.googlePage = "all";
    state.googlePageQuery = "";
    $("#google-page-search").value = "";
  }
  $("#google-company-search").value = nextCompany === "all" ? "" : nextCompany;
  renderGoogleCompanyFilter();
  renderGooglePageFilter();
  renderGoogleReports();
}

function resolveGoogleCompanyInput(value, useSingleMatch = false) {
  const query = value.trim().toLowerCase();
  const companies = googleCompanies();
  if (!query) return "all";
  const exact = companies.find((company) => company.toLowerCase() === query);
  if (exact) return exact;
  const matches = companies.filter((company) => company.toLowerCase().includes(query));
  return useSingleMatch && matches.length === 1 ? matches[0] : null;
}

function renderGooglePageFilter() {
  const select = $("#google-page-filter");
  const pages = googleCompanyPages();
  const queryTokens = state.googlePageQuery.toLowerCase().trim().split(/\s+/).filter(Boolean);
  const sortedPages = [...pages].sort((a, b) => `${a.business} ${a.title}`.localeCompare(`${b.business} ${b.title}`));
  const matches = queryTokens.length ? sortedPages.filter((page) => {
    const haystack = `${page.business} ${page.title} ${page.url}`.toLowerCase();
    return queryTokens.every((token) => haystack.includes(token));
  }) : sortedPages;
  const optionLimit = 75;
  const visiblePages = matches.slice(0, optionLimit);
  const selectedPage = matches.find((page) => page.page_id === state.googlePage);
  select.innerHTML = `<option value="all">All ${state.googleCompany === "all" ? "" : `${escapeHtml(state.googleCompany)} `}landing pages (${pages.length})</option>${visiblePages.map((page) => (
    `<option value="${escapeHtml(page.page_id)}">${escapeHtml(page.business)} · ${escapeHtml(formatPath(page.url))}</option>`
  )).join("")}${matches.length > optionLimit ? `<option value="" disabled>Type more to narrow ${matches.length - optionLimit} additional matches</option>` : ""}`;
  if (selectedPage) select.value = state.googlePage;
  else {
    state.googlePage = "all";
    select.value = "all";
  }
  const displayedMatches = Math.min(matches.length, optionLimit);
  $("#google-page-search-status").textContent = queryTokens.length
    ? `${matches.length.toLocaleString()} matching pages · showing ${displayedMatches.toLocaleString()}`
    : pages.length > optionLimit
      ? `Showing ${optionLimit} of ${pages.length.toLocaleString()} pages · type above to filter all pages`
      : `${pages.length.toLocaleString()} ${state.googleCompany === "all" ? "" : `${state.googleCompany} `}landing pages available`;
}

function selectedGooglePage() {
  if (state.googlePage === "all") return null;
  return googleCompanyPages().find((page) => page.page_id === state.googlePage) || null;
}

function aggregateGooglePages(pages) {
  const searchDays = new Map();
  const eventDays = new Map();
  const events = {};
  let impressions = 0, clicks = 0, weightedPosition = 0, positionWeight = 0;
  let sessions = 0, acceptedLeads = 0, qualifiedLeads = 0;
  pages.forEach((page) => {
    impressions += Number(page.impressions) || 0;
    clicks += Number(page.clicks) || 0;
    const weight = Number(page.impressions) || 0;
    if (weight > 0) {
      weightedPosition += (Number(page.average_position) || 0) * weight;
      positionWeight += weight;
    }
    sessions += Number(page.sessions) || 0;
    acceptedLeads += Number(page.accepted_leads) || 0;
    qualifiedLeads += Number(page.qualified_leads) || 0;
    Object.entries(page.events || {}).forEach(([name, count]) => { events[name] = (events[name] || 0) + Number(count || 0); });
    (page.search_daily || []).forEach((row) => {
      const day = searchDays.get(row.date) || { date: row.date, impressions: 0, clicks: 0 };
      day.impressions += Number(row.impressions) || 0;
      day.clicks += Number(row.clicks) || 0;
      searchDays.set(row.date, day);
    });
    (page.event_daily || []).forEach((row) => {
      const day = eventDays.get(row.date) || { date: row.date, page_views: 0, form_submits: 0 };
      day.page_views += Number(row.page_views) || 0;
      day.form_submits += Number(row.form_submits) || 0;
      eventDays.set(row.date, day);
    });
  });
  return {
    searchTotals: { impressions, clicks, ctr: impressions ? (clicks / impressions) * 100 : 0, average_position: positionWeight ? weightedPosition / positionWeight : 0 },
    searchDaily: [...searchDays.values()].sort((a, b) => a.date.localeCompare(b.date)),
    gaTotals: { page_views: events.page_view || 0, sessions, cta_clicks: events.cta_click || 0, form_starts: events.form_start || 0, form_submits: events.form_submit || 0 },
    gaDaily: [...eventDays.values()].sort((a, b) => a.date.localeCompare(b.date)),
    eventRows: Object.entries(events).map(([event_name, event_count]) => ({ event_name, event_count, source: "Google Analytics" })).sort((a, b) => b.event_count - a.event_count),
    acceptedLeads,
    qualifiedLeads,
  };
}

function renderGoogleReports() {
  const report = state.googleReports;
  if (!report) return;
  const selected = selectedGooglePage();
  const companyPages = googleCompanyPages();
  const companyAggregate = state.googleCompany === "all" ? null : aggregateGooglePages(companyPages);
  const searchTotals = selected ? {
    impressions: selected.impressions,
    clicks: selected.clicks,
    ctr: selected.ctr,
    average_position: selected.average_position,
  } : companyAggregate?.searchTotals || report.search_console.totals;
  const searchDaily = selected ? selected.search_daily : companyAggregate?.searchDaily || report.search_console.daily;
  const pages = selected ? [selected] : companyPages;
  const gaTotals = selected ? {
    page_views: selected.events.page_view || 0,
    sessions: selected.sessions || 0,
    cta_clicks: selected.events.cta_click || 0,
    form_starts: selected.events.form_start || 0,
    form_submits: selected.events.form_submit || 0,
  } : companyAggregate?.gaTotals || report.ga4.totals;
  const gaDaily = selected ? selected.event_daily : companyAggregate?.gaDaily || report.ga4.daily;
  const eventRows = selected
    ? Object.entries(selected.events).map(([event_name, event_count]) => ({ event_name, event_count, source: "Google Analytics" })).sort((a, b) => b.event_count - a.event_count)
    : companyAggregate?.eventRows || report.ga4.events;
  const acceptedLeads = selected ? selected.accepted_leads : (companyAggregate?.acceptedLeads ?? report.ga4.pages.reduce((sum, page) => sum + page.accepted_leads, 0));
  const qualifiedLeads = selected ? selected.qualified_leads : (companyAggregate?.qualifiedLeads ?? report.ga4.pages.reduce((sum, page) => sum + page.qualified_leads, 0));

  $("#google-date-label").textContent = report.date_range.label || "Reporting period";
  $("#google-date-range").textContent = `${shortDate(report.date_range.start)} – ${shortDate(report.date_range.end)}`;
  $("#google-date-through").textContent = `Google data through ${shortDate(report.date_range.end)} · ${Number(report.date_range.reporting_lag_days || 2)}-day reporting lag`;
  $("#google-last-sync").textContent = `Last synced ${formatIstDate(report.last_synced_at)}`;
  $("#google-schedule").textContent = report.schedule.enabled ? report.schedule.label : "Automatic sync disabled";
  $("#gsc-impressions").textContent = Number(searchTotals.impressions).toLocaleString();
  $("#gsc-clicks").textContent = Number(searchTotals.clicks).toLocaleString();
  $("#gsc-ctr").textContent = `${Number(searchTotals.ctr).toFixed(1)}%`;
  $("#gsc-position").textContent = Number(searchTotals.average_position).toFixed(1);
  $("#gsc-daily-chart").innerHTML = lineChart(searchDaily, "clicks", "impressions");
  $("#gsc-pages-table").innerHTML = pages.length ? pages.map((page) => `
    <tr><td><strong>${escapeHtml(page.title)}</strong><small>${escapeHtml(formatPath(page.url))}</small></td><td>${Number(page.impressions).toLocaleString()}</td><td>${Number(page.clicks).toLocaleString()}</td><td>${Number(page.ctr).toFixed(1)}%</td><td>${Number(page.average_position).toFixed(1)}</td></tr>
  `).join("") : `<tr><td colspan="5">No Search Console page totals in this date range.</td></tr>`;
  $("#gsc-privacy-note").textContent = report.search_console.privacy_note;

  $("#ga4-pageviews").textContent = Number(gaTotals.page_views).toLocaleString();
  $("#ga4-sessions").textContent = Number(gaTotals.sessions).toLocaleString();
  $("#ga4-submits").textContent = Number(gaTotals.form_submits).toLocaleString();
  $("#ga4-cta").textContent = Number(gaTotals.cta_clicks).toLocaleString();
  renderGa4Funnel(gaTotals);
  $("#ga4-event-chart").innerHTML = barChart(gaDaily);
  $("#ga4-compare-submits").textContent = Number(gaTotals.form_submits).toLocaleString();
  $("#app-accepted-leads").textContent = Number(acceptedLeads).toLocaleString();
  $("#app-qualified-leads").textContent = Number(qualifiedLeads).toLocaleString();
  $("#ga4-events-table").innerHTML = eventRows.length ? eventRows.map((event) => `
    <tr><td><strong>${escapeHtml(event.event_name)}</strong></td><td>${Number(event.event_count).toLocaleString()}</td><td>${sourceBadge(event.source)}</td></tr>
  `).join("") : `<tr><td colspan="3">No GA4 events in this date range.</td></tr>`;
}

function shortDate(value) {
  return new Date(`${value}T00:00:00`).toLocaleDateString([], { day: "numeric", month: "short" });
}

function lineChart(rows, primaryKey, secondaryKey) {
  if (!rows?.length) return `<p class="empty">Google data will appear after the next sync.</p>`;
  const width = 900, height = 220, padX = 42, padY = 24;
  const max = Math.max(...rows.flatMap((row) => [Number(row[primaryKey]) || 0, Number(row[secondaryKey]) || 0]), 1);
  const coordinates = (row, index, key) => {
    const x = padX + (index * (width - padX * 2)) / Math.max(rows.length - 1, 1);
    const y = height - padY - ((Number(row[key]) || 0) / max) * (height - padY * 2);
    return { x: x.toFixed(1), y: y.toFixed(1) };
  };
  const points = (key) => rows.map((row, index) => {
    const { x, y } = coordinates(row, index, key);
    return `${x},${y}`;
  }).join(" ");
  const markers = (key, tone) => rows.map((row, index) => {
    const value = Number(row[key]) || 0;
    if (value === 0 && rows.length > 1) return "";
    const { x, y } = coordinates(row, index, key);
    return `<circle class="chart-point ${tone}" cx="${x}" cy="${y}" r="4.5"><title>${escapeHtml(shortDate(row.date))}: ${value.toLocaleString()}</title></circle>`;
  }).join("");
  const labels = rows.filter((_, index) => index === 0 || index === rows.length - 1 || index % Math.max(1, Math.ceil(rows.length / 5)) === 0);
  return `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
    ${[0,1,2,3].map((line) => `<line x1="${padX}" y1="${padY + line * 54}" x2="${width-padX}" y2="${padY + line * 54}" class="grid-line" />`).join("")}
    <polyline class="chart-line secondary" points="${points(secondaryKey)}" />
    <polyline class="chart-line primary" points="${points(primaryKey)}" />
    ${markers(secondaryKey, "secondary")}
    ${markers(primaryKey, "primary")}
  </svg><div class="chart-axis">${labels.map((row) => `<span>${escapeHtml(shortDate(row.date))}</span>`).join("")}</div>`;
}

function barChart(rows) {
  if (!rows?.length) return `<p class="empty">GA4 events will appear after the next sync.</p>`;
  const max = Math.max(...rows.flatMap((row) => [Number(row.page_views) || 0, Number(row.form_submits) || 0]), 1);
  return `<div class="bar-columns">${rows.map((row) => `
    <div class="bar-column"><div><i style="--height:${Math.max(3,(Number(row.page_views)||0)/max*100)}%"></i><i class="submit" style="--height:${Math.max(3,(Number(row.form_submits)||0)/max*100)}%"></i></div><small>${escapeHtml(shortDate(row.date))}</small></div>
  `).join("")}</div>`;
}

function renderGa4Funnel(totals) {
  const metrics = [["Page views", totals.page_views], ["Form starts", totals.form_starts], ["CTA clicks", totals.cta_clicks], ["Form submits", totals.form_submits]];
  const baseline = Math.max(Number(totals.page_views) || 0, 1);
  $("#ga4-funnel").innerHTML = metrics.map(([label, value], index) => `
    <div><span>${escapeHtml(label)}</span><strong>${Number(value).toLocaleString()}</strong><small>${Math.round((Number(value)/baseline)*100)}%</small><em>GA4</em>${index < metrics.length - 1 ? `<b>→</b>` : ""}</div>
  `).join("");
}

function renderFirstPartyFunnel(page) {
  const events = page.first_party_events;
  const sources = events.metric_sources || {};
  const metrics = [
    ["Page views", events.page_views, sources.page_views],
    ["CTA clicks", events.cta_clicks, sources.cta_clicks],
    ["Form starts", events.form_starts, sources.form_starts],
    ["Form submits", events.form_submits, sources.form_submits],
    ["Leads", events.leads, sources.leads],
  ];
  return `
    <div class="first-party-funnel">
      <div class="mini-head"><h4>First-party app event funnel</h4><span>Last event ${escapeHtml(formatDate(events.last_event_at))}</span></div>
      <div>${metrics.map(([label, value, source]) => `
        <span><small>${escapeHtml(label)}</small><strong>${Number(value).toLocaleString()}</strong>${sourceBadge(source)}</span>
      `).join("")}</div>
    </div>
  `;
}

function renderIndexHelper(page) {
  const helper = page.google_index_status;
  return `
    <details class="index-helper">
      <summary>
        <span>Google index status helper</span>
        <strong class="index-status ${escapeHtml(helper.status)}">${escapeHtml(helper.status_label)}</strong>
        ${sourceBadge(helper.status_source)}
      </summary>
      <div class="index-helper-grid">
        <span><small>Sitemap presence</small><strong>${helper.in_sitemap ? "Included" : "Not included"}</strong>${sourceBadge(helper.sitemap_source)}</span>
        <span><small>Last Search Console sync</small><strong>${escapeHtml(formatDate(helper.last_synced_at))}</strong>${sourceBadge(helper.status_source)}</span>
        <span><small>Sync status</small><strong>${escapeHtml(helper.last_sync_status.replaceAll("_", " "))}</strong>${sourceBadge("Integration status")}</span>
      </div>
      <div class="index-helper-actions">
        <a class="button-link" href="${escapeHtml(helper.search_console_inspect_url)}" target="_blank" rel="noreferrer">Inspect URL in Search Console</a>
        <a class="button-link subtle" href="${escapeHtml(helper.sitemap_url)}" target="_blank" rel="noreferrer">Open sitemap</a>
      </div>
      <p>${escapeHtml(helper.manual_guidance)}</p>
    </details>
  `;
}

function renderSeoQueries(items) {
  $("#seo-queries-list").innerHTML = items.length ? items.map((item) => `
    <article class="query-card">
      <strong>${escapeHtml(item.query)}</strong>
      <span>${Number(item.impressions).toLocaleString()} impressions · ${Number(item.clicks).toLocaleString()} clicks · avg. ${Number(item.average_position).toFixed(1)}</span>
      ${sourceBadge(item.source)}
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
  if (value.includes("live") || value.includes("google analytics") || value.includes("search console")) return "live";
  if (value.includes("app db") || value.includes("app event") || value.includes("audit db")) return "db";
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
  if (normalized.includes("app event")) return "First-party browser or server event recorded by this application.";
  if (normalized.includes("app calculation")) return "Calculated inside the application from page content and stored metrics.";
  if (normalized.includes("app-generated sitemap")) return "Presence in the sitemap generated by this application.";
  if (normalized.includes("integration status")) return "Connection and last-sync state stored by the integration layer.";
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
    "refresh_rewrite_drafted",
    "refresh_rewrite_approved",
    "refresh_rewrite_rejected",
    "refresh_rewrite_published",
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
      <td>${sourceBadge("App DB")}</td>
    </tr>
  `).join("") : `<tr><td colspan="5">Captured leads will appear here.</td></tr>`;
}

function renderActivityEvents(items) {
  const container = $("#page-events-list");
  if (!container) return;
  $("#page-event-count").textContent = items.reduce((total, page) => {
    const events = page.first_party_events;
    return total + events.page_views + events.cta_clicks + events.form_starts + events.form_submits;
  }, 0);
  container.innerHTML = items.length ? items.map((page) => `
    <article class="activity-event-card">
      <div>
        <strong>${escapeHtml(page.title)}</strong>
        <span>${escapeHtml(page.business_name || "Unknown company")} · ${escapeHtml(formatPath(page.url))}</span>
      </div>
      ${renderFirstPartyFunnel(page)}
    </article>
  `).join("") : `<p class="empty">First-party landing-page events will appear here.</p>`;
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
      <td>${sourceBadge("App audit DB")}</td>
    </tr>
  `).join("") : `<tr><td colspan="4">Audit events will appear here.</td></tr>`;
}

async function refreshAll() {
  await Promise.all([loadBusinesses(), loadCampaigns(), loadDashboard(), loadPages(), loadLeads(), loadAudit(), loadSeoOverview(), loadGoogleReports(), loadGrowthOverview(), loadAdPlans()]);
}

$("#mobile-nav-toggle").addEventListener("click", () => {
  const open = document.body.classList.toggle("nav-open");
  $("#mobile-nav-toggle").setAttribute("aria-expanded", String(open));
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && document.body.classList.contains("nav-open")) {
    document.body.classList.remove("nav-open");
    $("#mobile-nav-toggle").setAttribute("aria-expanded", "false");
  }
});

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
$("#recommendations-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-refresh-action]");
  if (!button) return;
  const recommendationId = button.dataset.recommendationId;
  const action = button.dataset.refreshAction;
  let body = {};
  if (action === "approve") {
    if (!window.confirm("Approve this exact rewrite draft? The live page will remain unchanged until you publish it.")) return;
    body = { approved_by: "owner" };
  }
  if (action === "reject") {
    const reason = window.prompt("Why are you rejecting this rewrite?");
    if (!reason) return;
    body = { reason };
  }
  if (action === "publish") {
    if (!window.confirm("Publish the approved rewrite now? The previous content will remain in version history.")) return;
    body = { confirm_publish: true };
  }
  const labels = {
    rewrite: ["Generating rewrite", "The agent is rewriting the full page and preserving the current version for review."],
    approve: ["Approving rewrite", "Recording explicit owner approval without changing the live page."],
    reject: ["Rejecting rewrite", "Closing the draft and recording the review reason."],
    publish: ["Publishing approved rewrite", "Applying the approved draft and saving immutable before/after history."],
  };
  await withProcessing(labels[action][0], labels[action][1], async () => {
    await api(`/api/recommendations/${recommendationId}/${action}`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    await refreshAll();
  });
  toast(`${labels[action][0]} completed`);
});
$("#sync-seo").addEventListener("click", async () => {
  await withProcessing("Syncing SEO analytics", "The SEO Analytics Agent is collecting page, query, engagement, and conversion metrics.", async () => {
    await api("/api/seo/sync", { method: "POST", body: JSON.stringify({}) });
    await refreshAll();
  });
  toast("SEO metrics synced");
});
$("#sync-google-reports").addEventListener("click", async () => {
  await withProcessing("Syncing Google reports", "Search Console page totals, query details, GA4 sessions, and GA4 events are being refreshed.", async () => {
    await api("/api/seo/sync", { method: "POST", body: JSON.stringify({}) });
    await Promise.all([loadGoogleReports(), loadSeoOverview(), loadAudit()]);
  });
  toast("Google reports synced");
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
$("#google-page-filter").addEventListener("change", (event) => {
  state.googlePage = event.target.value;
  renderGoogleReports();
});
$("#google-page-search").addEventListener("input", (event) => {
  state.googlePageQuery = event.target.value;
  state.googlePage = "all";
  renderGooglePageFilter();
  renderGoogleReports();
});
$("#google-company-search").addEventListener("input", (event) => {
  const resolved = resolveGoogleCompanyInput(event.target.value);
  if (resolved) {
    applyGoogleCompany(resolved);
    return;
  }
  const query = event.target.value.trim().toLowerCase();
  const matches = googleCompanies().filter((company) => company.toLowerCase().includes(query));
  $("#google-company-search-status").textContent = matches.length
    ? `${matches.length} company suggestions · select one to refresh landing pages`
    : "No matching company";
});
$("#google-company-search").addEventListener("change", (event) => {
  const resolved = resolveGoogleCompanyInput(event.target.value, true);
  if (resolved) applyGoogleCompany(resolved);
  else $("#google-company-search-status").textContent = "Choose a company from the autocomplete suggestions";
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

document.querySelectorAll(".google-report-tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".google-report-tab").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".google-report-panel").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    $(`#${button.dataset.googleTab}-report`).classList.add("active");
  });
});

loadHealth().catch((error) => toast(error.message));
refreshAll().catch((error) => toast(error.message));
window.addEventListener("hashchange", setRoute);
setRoute();
