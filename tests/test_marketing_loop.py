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
