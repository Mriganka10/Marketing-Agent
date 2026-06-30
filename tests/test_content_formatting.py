from app.core.content_formatting import coerce_text, normalize_sections


def test_coerce_text_formats_structured_hero_as_prose():
    raw = (
        "{'heading': 'Drive Qualified Leads with AI-Powered Marketing Automation', "
        "'body': 'Northstar Growth Labs helps SaaS teams capture demand through focused "
        "landing pages and continuous optimization.', 'cta': 'Request Your Demo'}"
    )

    text = coerce_text(raw)

    assert "{'heading'" not in text
    assert "Drive Qualified Leads" in text
    assert "Northstar Growth Labs helps SaaS teams" in text
    assert "Request Your Demo" in text


def test_normalize_sections_accepts_dict_items():
    sections = normalize_sections(
        [{"heading": "Buyer intent", "body": "Turn search demand into qualified pipeline."}],
        [],
    )

    assert sections == [
        {"heading": "Buyer intent", "body": "Turn search demand into qualified pipeline."}
    ]

