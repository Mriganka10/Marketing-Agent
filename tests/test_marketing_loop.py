def test_end_to_end_agent_loop_and_lead_capture(client):
    business_response = client.post(
        "/api/businesses",
        json={
            "name": "Northstar Growth Labs",
            "website": "https://example.com",
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
                cta="{'text': 'Request Demo', 'url': 'https://example.com'}",
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
    assert overview["top_queries"]


def test_seo_sync_uses_live_google_rows_when_configured(client, monkeypatch):
    from datetime import date

    from app.core.config import get_settings
    from app.integrations.google_marketing import GA4PageRow, GoogleMarketingData, SearchConsoleRow

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
                    page_url=f"https://agenticgrowthlabs.com/p/{page['slug']}",
                    query="automated seo agents",
                    country="IN",
                    device="DESKTOP",
                    clicks=12,
                    impressions=240,
                    ctr=0.05,
                    position=4.2,
                )
            ],
            analytics_rows=[
                GA4PageRow(
                    path=f"/p/{page['slug']}",
                    sessions=33,
                    engaged_sessions=24,
                    event_count=80,
                    conversions=3,
                    traffic_source="Organic Search",
                    device="DESKTOP",
                    country="India",
                )
            ],
        )

    monkeypatch.setattr("app.agents.seo_analytics.GoogleMarketingIntegration.fetch", fake_fetch)

    sync = client.post("/api/seo/sync")
    assert sync.status_code == 200
    assert sync.json()["mode"] == "live_google_integrated"
    assert sync.json()["records_written"] == 2

    overview = client.get("/api/seo/overview").json()
    assert overview["integration_status"]["mode"] == "live_google_integrated"
    assert any(item["query"] == "automated seo agents" for item in overview["top_queries"])
    assert overview["organic_impressions"] == 240
    assert overview["sessions"] == 33


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
