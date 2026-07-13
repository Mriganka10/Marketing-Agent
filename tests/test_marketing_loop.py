def test_end_to_end_agent_loop_and_lead_capture(client):
    business_response = client.post(
        "/api/businesses",
        json={
            "name": "Northstar Growth Labs",
            "industry": "B2B marketing automation",
            "audience": "SaaS founders and revenue teams",
            "value_proposition": "We launch search-led landing pages and optimize them from lead data.",
            "offers": ["SEO pages", "Lead capture", "Analytics refresh"],
            "competitors": ["Clay"],
            "tone": "professional",
        },
    )
    assert business_response.status_code == 200
    business_id = business_response.json()["id"]

    campaign_response = client.post(
        "/api/campaigns",
        json={
            "business_id": business_id,
            "name": "AI growth pages",
            "goal": "Generate qualified demo requests from high-intent searches.",
            "target_region": "United States",
        },
    )
    assert campaign_response.status_code == 200
    campaign_id = campaign_response.json()["id"]

    run_response = client.post(
        "/api/runs",
        json={"campaign_id": campaign_id, "publish_pages": True},
    )
    assert run_response.status_code == 200
    run = run_response.json()
    assert len(run["demand_signals"]) >= 3
    assert len(run["pages"]) >= 3
    assert run["recommendations"]
    assert run["pages"][0]["seo"]["brand_theme"]["accent"] == "#0f766e"

    page = run["pages"][0]
    public_response = client.get(f"/p/{page['slug']}")
    assert public_response.status_code == 200
    assert page["title"] in public_response.text

    lead_response = client.post(
        "/api/leads",
        json={
            "campaign_id": campaign_id,
            "page_id": page["id"],
            "name": "Avery Buyer",
            "email": "avery@acme.com",
            "company": "Acme",
            "message": "We need a scalable content and lead capture engine for a new product line.",
        },
    )
    assert lead_response.status_code == 200
    assert lead_response.json()["status"] == "qualified"

    dashboard = client.get("/api/dashboard").json()
    assert dashboard["businesses"] == 1
    assert dashboard["campaigns"] == 1
    assert dashboard["pages"] >= 3
    assert dashboard["leads"] == 1
    assert dashboard["visits"] == 1
    assert dashboard["conversions"] == 1


def test_health_and_root(client):
    assert client.get("/health").json()["status"] == "ok"
    root = client.get("/")
    assert root.status_code == 200
    assert "Marketing Agent" in root.text
    assert "/static/redesign.css" in root.text
    assert 'id="mobile-nav-toggle"' in root.text
    assert 'id="overview-volume-chart"' in root.text


def test_page_listing_repairs_structured_content(client):
    business_id = client.post(
        "/api/businesses",
        json={
            "name": "Northstar Growth Labs",
            "industry": "B2B marketing automation",
            "audience": "SaaS founders and revenue teams",
            "value_proposition": "We turn search demand into qualified pipeline.",
        },
    ).json()["id"]
    campaign_id = client.post(
        "/api/campaigns",
        json={
            "business_id": business_id,
            "name": "Repair campaign",
            "goal": "Generate qualified pipeline.",
        },
    ).json()["id"]

    from app.core.database import SessionLocal
    from app.models.entities import LandingPage

    with SessionLocal() as db:
        db.add(
            LandingPage(
                campaign_id=campaign_id,
                slug="repair-page",
                title="Repair page",
                hero=(
                    "{'heading': 'Drive Qualified Leads', "
                    "'body': 'Create focused landing pages.', 'cta': 'Request Demo'}"
                ),
                sections=[],
                cta="{'text': 'Request Demo', 'url': 'https://northstar.test'}",
                seo={},
                status="published",
            )
        )
        db.commit()

    pages = client.get("/api/pages").json()
    repaired = next(page for page in pages if page["slug"] == "repair-page")

    assert "{'heading'" not in repaired["hero"]
    assert repaired["hero"] == "Drive Qualified Leads Create focused landing pages. Request Demo"
    assert repaired["cta"] == "Request Demo"


def test_seo_analytics_sync_sitemap_and_structured_public_page(client):
    business_id = client.post(
        "/api/businesses",
        json={
            "name": "Agentic Growth Labs",
            "website": "https://agenticgrowthlabs.com",
            "industry": "SEO automation",
            "audience": "SMB founders and marketing teams",
            "value_proposition": "We automate search analytics, content refresh, and lead attribution.",
            "offers": ["SEO automation", "GA4 analytics", "Search Console reporting"],
        },
    ).json()["id"]
    campaign_id = client.post(
        "/api/campaigns",
        json={
            "business_id": business_id,
            "name": "SEO automation demo",
            "goal": "Generate qualified SEO automation leads.",
            "target_region": "India",
        },
    ).json()["id"]

    run = client.post("/api/runs", json={"campaign_id": campaign_id, "publish_pages": True}).json()
    page = run["pages"][0]

    public = client.get(f"/p/{page['slug']}")
    assert public.status_code == 200
    assert 'rel="canonical"' in public.text
    assert 'application/ld+json' in public.text

    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Sitemap:" in robots.text

    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert f"/p/{page['slug']}" in sitemap.text

    sync = client.post("/api/seo/sync")
    assert sync.status_code == 200
    assert sync.json()["pages_synced"] >= 1

    overview = client.get("/api/seo/overview").json()
    assert overview["pages_published"] >= 1
    assert overview["organic_impressions"] > 0
    assert overview["page_scores"]
    assert overview["page_scores"][0]["business_id"] == business_id
    assert overview["page_scores"][0]["business_name"] == "Agentic Growth Labs"
    assert overview["top_queries"]


def test_seo_overview_exposes_sources_app_events_and_index_helper(client):
    business_id = client.post(
        "/api/businesses",
        json={
            "name": "Source Label Labs",
            "website": "https://sourcelabels.example",
            "industry": "SEO analytics",
            "audience": "Marketing teams that need trustworthy page-level reporting",
            "value_proposition": "We separate first-party, Google, and fallback marketing data.",
        },
    ).json()["id"]
    campaign_id = client.post(
        "/api/campaigns",
        json={
            "business_id": business_id,
            "name": "Metric provenance",
            "goal": "Generate qualified analytics implementation leads.",
        },
    ).json()["id"]
    page = client.post(
        "/api/runs", json={"campaign_id": campaign_id, "publish_pages": True}
    ).json()["pages"][0]

    for event_type in ["page_view", "page_view", "cta_click", "form_start", "form_submit"]:
        response = client.post(
            "/api/events",
            json={
                "page_id": page["id"],
                "campaign_id": campaign_id,
                "event_type": event_type,
                "session_id": "first-party-session",
                "path": f"/p/{page['slug']}",
            },
        )
        assert response.status_code == 200
    lead = client.post(
        "/api/leads",
        json={
            "campaign_id": campaign_id,
            "page_id": page["id"],
            "name": "First Party Lead",
            "email": "lead@example.com",
            "company": "Source Label Labs",
        },
    )
    assert lead.status_code == 200
    assert client.post("/api/seo/sync").status_code == 200

    overview = client.get("/api/seo/overview").json()
    score = next(item for item in overview["page_scores"] if item["page_id"] == page["id"])
    events = score["first_party_events"]
    index = score["google_index_status"]

    assert events["page_views"] == 2
    assert events["cta_clicks"] == 1
    assert events["form_starts"] == 1
    assert events["form_submits"] == 1
    assert events["leads"] == 1
    assert events["metric_sources"]["page_views"] == "App events"
    assert events["metric_sources"]["leads"] == "App DB"
    assert "Demo fallback" in score["metric_sources"]["impressions"]
    assert "App events" in score["metric_sources"]["sessions"]
    assert score["metric_sources"]["leads"] == "App DB"
    assert overview["metric_sources"]["organic_impressions"] == "Demo fallback"
    assert overview["indexed_pages"] == 0
    assert index["status"] == "awaiting_search_console_sync"
    assert index["in_sitemap"] is True
    assert index["sitemap_url"].endswith("/sitemap.xml")
    assert "search.google.com/search-console/inspect" in index["search_console_inspect_url"]
    assert index["last_synced_at"] is not None
    assert "Request Indexing" in index["manual_guidance"]
    assert overview["top_queries"][0]["source"] == "Demo fallback"


def test_seo_sync_uses_live_google_rows_when_configured(client, monkeypatch):
    from datetime import date

    from app.core.config import get_settings
    from app.integrations.google_marketing import (
        GA4EventRow,
        GA4PageRow,
        GoogleMarketingData,
        SearchConsoleRow,
    )

    monkeypatch.setenv("GA4_PROPERTY_ID", "153293282")
    monkeypatch.setenv("GOOGLE_SEARCH_CONSOLE_SITE_URL", "https://agenticgrowthlabs.com/")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
    get_settings.cache_clear()

    business_id = client.post(
        "/api/businesses",
        json={
            "name": "Agentic Growth Labs",
            "website": "https://agenticgrowthlabs.com",
            "industry": "SEO automation",
            "audience": "Marketing teams automating SEO operations",
            "value_proposition": "We automate demand research, page creation, and SEO refresh.",
        },
    ).json()["id"]
    campaign_id = client.post(
        "/api/campaigns",
        json={
            "business_id": business_id,
            "name": "Live Google sync",
            "goal": "Generate SEO automation demos.",
        },
    ).json()["id"]
    page = client.post("/api/runs", json={"campaign_id": campaign_id, "publish_pages": True}).json()[
        "pages"
    ][0]

    def fake_fetch(self, *, days=28, row_limit=25000):
        return GoogleMarketingData(
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 5),
            search_rows=[
                SearchConsoleRow(
                    date=date(2026, 7, 5),
                    page_url=f"https://agenticgrowthlabs.com/p/{page['slug']}",
                    query="",
                    country="ALL",
                    device="ALL",
                    clicks=12,
                    impressions=240,
                    ctr=0.05,
                    position=4.2,
                )
            ],
            search_query_rows=[
                SearchConsoleRow(
                    date=date(2026, 7, 5),
                    page_url=f"https://agenticgrowthlabs.com/p/{page['slug']}",
                    query="automated seo agents",
                    country="ALL",
                    device="ALL",
                    clicks=12,
                    impressions=240,
                    ctr=0.05,
                    position=4.2,
                )
            ],
            analytics_rows=[
                GA4PageRow(
                    date=date(2026, 7, 5),
                    path=f"/p/{page['slug']}",
                    sessions=33,
                    engaged_sessions=24,
                    traffic_source="Organic Search",
                    device="DESKTOP",
                    country="India",
                )
            ],
            analytics_event_rows=[
                GA4EventRow(
                    date=date(2026, 7, 5),
                    path=f"/p/{page['slug']}",
                    event_name="page_view",
                    event_count=80,
                ),
                GA4EventRow(
                    date=date(2026, 7, 5),
                    path=f"/p/{page['slug']}",
                    event_name="cta_click",
                    event_count=4,
                ),
                GA4EventRow(
                    date=date(2026, 7, 5),
                    path=f"/p/{page['slug']}",
                    event_name="form_start",
                    event_count=5,
                ),
                GA4EventRow(
                    date=date(2026, 7, 5),
                    path=f"/p/{page['slug']}",
                    event_name="form_submit",
                    event_count=3,
                ),
            ],
        )

    monkeypatch.setattr("app.agents.seo_analytics.GoogleMarketingIntegration.fetch", fake_fetch)

    sync = client.post("/api/seo/sync")
    assert sync.status_code == 200
    assert sync.json()["mode"] == "live_google_integrated"
    assert sync.json()["records_written"] == 7

    overview = client.get("/api/seo/overview").json()
    assert overview["integration_status"]["mode"] == "live_google_integrated"
    assert any(item["query"] == "automated seo agents" for item in overview["top_queries"])
    assert overview["organic_impressions"] == 240
    assert overview["sessions"] == 33
    live_page = next(item for item in overview["page_scores"] if item["page_id"] == page["id"])
    assert live_page["metric_sources"]["impressions"] == "Live Google Search Console"
    assert live_page["metric_sources"]["sessions"] == "Live GA4"
    assert live_page["google_index_status"]["status"] == "google_data_detected"
    assert overview["indexed_pages"] == 1

    reports = client.get("/api/google-reports").json()
    assert reports["search_console"]["totals"]["impressions"] == 240
    assert reports["search_console"]["totals"]["clicks"] == 12
    assert reports["schedule"]["label"] == "Daily at 8:30 AM IST"
    assert len(reports["search_console"]["daily"]) == 5
    assert reports["search_console"]["daily"][0] == {
        "date": "2026-07-01",
        "impressions": 0,
        "clicks": 0,
    }
    assert reports["search_console"]["daily"][-1] == {
        "date": "2026-07-05",
        "impressions": 240,
        "clicks": 12,
    }
    assert reports["ga4"]["totals"]["sessions"] == 33
    event_counts = {
        event["event_name"]: event["event_count"] for event in reports["ga4"]["events"]
    }
    assert event_counts["page_view"] == 80
    assert event_counts["form_submit"] == 3


def test_seo_sync_preserves_google_error_status(client, monkeypatch):
    from app.core.config import get_settings
    from app.integrations.google_marketing import GoogleMarketingIntegrationError

    monkeypatch.setenv("GA4_PROPERTY_ID", "544328945")
    monkeypatch.setenv("GA4_MEASUREMENT_ID", "G-KZ3N4G2S20")
    monkeypatch.setenv("GOOGLE_SEARCH_CONSOLE_SITE_URL", "https://agenticgrowthlabs.com/")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
    get_settings.cache_clear()

    business_id = client.post(
        "/api/businesses",
        json={
            "name": "Agentic Growth Labs",
            "website": "https://agenticgrowthlabs.com",
            "industry": "SEO automation",
            "audience": "Marketing teams automating SEO operations",
            "value_proposition": "We automate demand research, page creation, and SEO refresh.",
        },
    ).json()["id"]
    campaign_id = client.post(
        "/api/campaigns",
        json={
            "business_id": business_id,
            "name": "Permission fallback",
            "goal": "Generate SEO automation demos.",
        },
    ).json()["id"]
    client.post("/api/runs", json={"campaign_id": campaign_id, "publish_pages": True})

    def fake_fetch(self, *, days=28, row_limit=25000):
        raise GoogleMarketingIntegrationError("Search Console sync failed: permission denied")

    monkeypatch.setattr("app.agents.seo_analytics.GoogleMarketingIntegration.fetch", fake_fetch)

    sync = client.post("/api/seo/sync")
    assert sync.status_code == 200
    assert sync.json()["mode"] == "google_sync_error_fallback"
    assert "permission denied" in sync.json()["fallback_reason"]

    integrations = client.get("/api/seo/integrations").json()
    assert integrations["mode"] == "google_sync_error_fallback"
    assert all(item["status"] == "error" for item in integrations["connections"])


def test_public_landing_page_uses_business_brand_theme(client):
    business_id = client.post(
        "/api/businesses",
        json={
            "name": "Greyradius",
            "website": "https://greyradius.com/",
            "industry": "Growth consulting",
            "audience": "SaaS founders and revenue teams",
            "value_proposition": "We build your growth strategy and execute with you.",
        },
    ).json()["id"]
    campaign_id = client.post(
        "/api/campaigns",
        json={
            "business_id": business_id,
            "name": "GreyRadius growth pages",
            "goal": "Generate qualified growth consulting conversations.",
        },
    ).json()["id"]

    from app.core.database import SessionLocal
    from app.models.entities import LandingPage

    with SessionLocal() as db:
        db.add(
            LandingPage(
                campaign_id=campaign_id,
                slug="greyradius-growth",
                title="Greyradius growth consulting",
                hero="Build your growth strategy and execution engine.",
                sections=[],
                cta="Start a conversation",
                seo={"keywords": "growth consulting, revenue operations"},
                status="published",
            )
        )
        db.commit()

    public_response = client.get("/p/greyradius-growth")

    assert public_response.status_code == 200
    assert "--public-accent: #f2673b" in public_response.text
    assert "--public-text: #101f43" in public_response.text
    assert 'src="https://greyradius.com/assets/images/logo.png"' in public_response.text
    assert 'alt="Greyradius logo"' in public_response.text

    client.post("/api/seo/sync")
    overview = client.get("/api/seo/overview").json()
    assert any(item["query"] == "growth consulting" for item in overview["top_queries"])


def test_public_landing_page_uses_kairoz_teal_theme(client):
    business_id = client.post(
        "/api/businesses",
        json={
            "name": "Kairoz Corporation",
            "website": "https://kairozcorporation.com/",
            "industry": "Skill lab and consulting",
            "audience": "Founders and learners",
            "value_proposition": "Future-ready skills and consulting for tomorrow's leaders.",
        },
    ).json()["id"]
    campaign_id = client.post(
        "/api/campaigns",
        json={
            "business_id": business_id,
            "name": "Kairoz growth pages",
            "goal": "Generate qualified conversations.",
        },
    ).json()["id"]

    from app.core.database import SessionLocal
    from app.models.entities import LandingPage

    with SessionLocal() as db:
        db.add(
            LandingPage(
                campaign_id=campaign_id,
                slug="kairoz-growth",
                title="Kairoz growth consulting",
                hero="Build future-ready growth capability.",
                sections=[],
                cta="Contact Kairoz",
                seo={},
                status="published",
            )
        )
        db.commit()

    public_response = client.get("/p/kairoz-growth")

    assert public_response.status_code == 200
    assert "--public-accent: #008080" in public_response.text
    assert "--public-line: #cce6e6" in public_response.text
    assert "Green-Modern-Tree-Logo-Design-4-1.png" in public_response.text


def test_content_agent_stores_business_specific_brand_theme(client):
    business_id = client.post(
        "/api/businesses",
        json={
            "name": "Kairoz Corporation",
            "website": "https://kairozcorporation.com/",
            "industry": "Skill lab and consulting",
            "audience": "Founders and leadership teams",
            "value_proposition": "We help leaders build future-ready skills and growth systems.",
        },
    ).json()["id"]
    campaign_id = client.post(
        "/api/campaigns",
        json={
            "business_id": business_id,
            "name": "Kairoz business-specific pages",
            "goal": "Generate qualified consulting conversations.",
        },
    ).json()["id"]

    run = client.post("/api/runs", json={"campaign_id": campaign_id, "publish_pages": True}).json()

    assert run["pages"][0]["seo"]["brand_theme"]["accent"] == "#008080"
    assert "kairozcorporation.com" in run["pages"][0]["seo"]["brand_theme"]["logo_url"]


def test_growth_suite_overview_and_sync(client):
    business_id = client.post(
        "/api/businesses",
        json={
            "name": "Agentic Growth Labs",
            "website": "https://agenticgrowthlabs.com",
            "industry": "SEO and marketing automation",
            "audience": "Marketing teams replacing manual SEO operations",
            "value_proposition": "We automate content, search analytics, authority, and paid campaign readiness.",
            "offers": ["SEO automation", "DataForSEO authority checks", "Google Ads readiness"],
            "competitors": ["Gushwork", "Clay"],
        },
    ).json()["id"]
    campaign_id = client.post(
        "/api/campaigns",
        json={
            "business_id": business_id,
            "name": "Full growth suite",
            "goal": "Generate qualified marketing automation leads.",
            "target_region": "India",
        },
    ).json()["id"]
    client.post("/api/runs", json={"campaign_id": campaign_id, "publish_pages": True})
    client.post("/api/seo/sync")

    overview = client.get("/api/growth/overview")
    assert overview.status_code == 200
    payload = overview.json()
    assert payload["mode"] in {"demo_ready", "hybrid_live_ready", "production_integrated"}
    assert len(payload["agents"]) == 6
    assert {agent["key"] for agent in payload["agents"]} == {
        "ai_search_visibility",
        "backlink_authority",
        "auto_refresh_approval",
        "paid_campaigns",
        "client_reporting",
        "client_workspace_access",
    }
    ai_agent = next(agent for agent in payload["agents"] if agent["key"] == "ai_search_visibility")
    backlink_agent = next(agent for agent in payload["agents"] if agent["key"] == "backlink_authority")
    assert ai_agent["metric_sources"]["content_pages"] == "App DB"
    assert backlink_agent["metric_sources"]["backlinks"] == "Demo fallback"
    assert payload["client_workspaces"][0]["name"] == "Agentic Growth Labs"
    assert payload["readiness"]["google_ads"]["developer_token"] is False

    sync = client.post("/api/growth/sync")
    assert sync.status_code == 200
    assert len(sync.json()["orchestration"]) == 6

    audit = client.get("/api/audit").json()
    assert any(event["action"] == "growth_suite_synced" for event in audit)


def test_growth_suite_authority_target_never_crosses_company_domains(client):
    real_business_id = client.post(
        "/api/businesses",
        json={
            "name": "Kairoz Corporation",
            "website": "https://kairozcorporation.com",
            "industry": "Leadership consulting",
            "audience": "Enterprise HR leaders",
            "value_proposition": "We build future-ready leadership systems.",
            "offers": ["Leadership programs"],
            "competitors": ["BetterUp"],
        },
    ).json()["id"]
    placeholder_business_id = client.post(
        "/api/businesses",
        json={
            "name": "Website Pending",
            "industry": "Demo",
            "audience": "Internal demo",
            "value_proposition": "Temporary placeholder profile.",
            "offers": ["Demo pages"],
            "competitors": [],
        },
    ).json()["id"]

    default_payload = client.get("/api/growth/overview").json()
    default_authority = next(agent for agent in default_payload["agents"] if agent["key"] == "backlink_authority")

    assert default_payload["selected_business"]["id"] == real_business_id
    assert default_authority["metrics"]["business"] == "Kairoz Corporation"
    assert default_authority["metrics"]["domain"] == "kairozcorporation.com"

    explicit_payload = client.get(f"/api/growth/overview?business_id={placeholder_business_id}").json()
    explicit_authority = next(agent for agent in explicit_payload["agents"] if agent["key"] == "backlink_authority")

    assert explicit_payload["selected_business"]["id"] == placeholder_business_id
    assert explicit_authority["metrics"]["business"] == "Website Pending"
    assert explicit_authority["metrics"]["domain"] == "Not configured"
    assert explicit_authority["metrics"]["backlinks"] == 0
    assert explicit_authority["metric_sources"]["backlinks"] == "Configuration"


def test_paid_campaign_agent_drafts_and_guards_google_push(client):
    business_id = client.post(
        "/api/businesses",
        json={
            "name": "Agentic Growth Labs",
            "website": "https://agenticgrowthlabs.com",
            "industry": "SEO and marketing automation",
            "audience": "Marketing teams replacing manual ad and SEO operations",
            "value_proposition": "We connect SEO pages, analytics, and paid campaign execution.",
            "offers": ["SEO automation", "Google Ads launch planning"],
            "competitors": ["Gushwork"],
        },
    ).json()["id"]
    campaign_id = client.post(
        "/api/campaigns",
        json={
            "business_id": business_id,
            "name": "Paid growth validation",
            "goal": "Generate qualified demo requests from paid search.",
            "target_region": "India",
        },
    ).json()["id"]
    client.post("/api/runs", json={"campaign_id": campaign_id, "publish_pages": True})

    draft = client.post(
        "/api/ads/plans/draft",
        json={"campaign_id": campaign_id, "daily_budget": 7, "currency_code": "INR"},
    )
    assert draft.status_code == 200
    plan = draft.json()
    assert plan["status"] == "draft"
    assert plan["approval_status"] == "needs_review"
    assert plan["daily_budget_micros"] == 7_000_000
    assert plan["plan"]["campaign_status"] == "PAUSED"
    assert plan["plan"]["ad_group_status"] == "PAUSED"
    assert plan["plan"]["keywords"]

    blocked = client.post(
        f"/api/ads/plans/{plan['id']}/push",
        json={"approve_google_push": False, "mode": "publish"},
    )
    assert blocked.status_code == 400

    validate = client.post(f"/api/ads/plans/{plan['id']}/validate")
    assert validate.status_code == 200
    assert validate.json()["status"] == "validation_failed"

    audit = client.get("/api/audit").json()
    assert any(event["action"] == "paid_ad_plan_drafted" for event in audit)


def test_auto_refresh_rewrite_requires_approval_before_publish(client):
    business_id = client.post(
        "/api/businesses",
        json={
            "name": "Approval Flow Labs",
            "website": "https://approvalflow.example",
            "industry": "Marketing automation",
            "audience": "Growth teams that need controlled content operations",
            "value_proposition": "We turn analytics signals into reviewable content changes.",
            "offers": ["Content refresh automation"],
            "competitors": [],
        },
    ).json()["id"]
    campaign_id = client.post(
        "/api/campaigns",
        json={
            "business_id": business_id,
            "name": "Guarded refresh",
            "goal": "Generate qualified conversations from organic landing pages.",
            "target_region": "India",
        },
    ).json()["id"]

    run = client.post(
        "/api/runs", json={"campaign_id": campaign_id, "publish_pages": True}
    ).json()
    recommendation = run["recommendations"][0]
    page_id = recommendation["page_id"]
    original_page = next(page for page in run["pages"] if page["id"] == page_id)

    assert recommendation["status"] == "pending_approval"
    assert recommendation["refresh_plan"]["status"] == "pending_approval"
    assert recommendation["recommendation"].startswith("Low-performing page")
    assert recommendation["refresh_plan"]["original_content"]["title"] == original_page["title"]
    assert recommendation["refresh_plan"]["proposed_content"]["title"] != original_page["title"]
    snapshot = recommendation["refresh_plan"]["proposed_content"]["performance_snapshot"]
    assert snapshot["overall_score"] < snapshot["threshold"] == 70
    exact_changes = recommendation["refresh_plan"]["proposed_content"]["exact_changes"]
    assert {change["field"] for change in exact_changes} >= {"SEO title", "Hero", "CTA"}
    assert all(change["recommended"] and change["reason"] for change in exact_changes)

    blocked = client.post(
        f"/api/recommendations/{recommendation['id']}/publish",
        json={"confirm_publish": True},
    )
    assert blocked.status_code == 409
    assert "approved" in blocked.json()["detail"]

    approved = client.post(
        f"/api/recommendations/{recommendation['id']}/approve",
        json={"approved_by": "Marketing owner"},
    )
    assert approved.status_code == 200
    assert approved.json()["refresh_plan"]["status"] == "approved"
    assert approved.json()["refresh_plan"]["approved_by"] == "Marketing owner"
    unchanged_page = next(page for page in client.get("/api/pages").json() if page["id"] == page_id)
    assert unchanged_page["title"] == original_page["title"]

    missing_confirmation = client.post(
        f"/api/recommendations/{recommendation['id']}/publish",
        json={"confirm_publish": False},
    )
    assert missing_confirmation.status_code == 400

    published = client.post(
        f"/api/recommendations/{recommendation['id']}/publish",
        json={"confirm_publish": True},
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["refresh_plan"]["status"] == "published"
    refreshed_page = next(page for page in client.get("/api/pages").json() if page["id"] == page_id)
    assert refreshed_page["title"] == recommendation["refresh_plan"]["proposed_content"]["title"]

    second_recommendation = run["recommendations"][1]
    rejected = client.post(
        f"/api/recommendations/{second_recommendation['id']}/reject",
        json={"reason": "The positioning needs legal review first."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["refresh_plan"]["status"] == "rejected"

    revised = client.post(
        f"/api/recommendations/{second_recommendation['id']}/rewrite", json={}
    )
    assert revised.status_code == 200
    assert revised.json()["refresh_plan"]["status"] == "pending_approval"
    assert revised.json()["refresh_plan"]["rejection_reason"] is None

    audit_actions = {event["action"] for event in client.get("/api/audit").json()}
    assert "refresh_rewrite_approved" in audit_actions
    assert "refresh_rewrite_published" in audit_actions
    assert "refresh_rewrite_rejected" in audit_actions
