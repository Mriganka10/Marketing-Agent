from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.models.entities import LandingPage, Lead
from app.models.schemas import LeadCreate


class LeadCaptureAgent:
    name = "lead_capture_agent"

    def capture(self, db: Session, payload: LeadCreate) -> Lead:
        score = self._score(payload)
        lead = Lead(
            campaign_id=payload.campaign_id,
            page_id=payload.page_id,
            name=payload.name,
            email=str(payload.email),
            company=payload.company,
            message=payload.message,
            score=score,
            status="qualified" if score >= 70 else "new",
            source=payload.source,
        )
        if payload.page_id:
            page = db.get(LandingPage, payload.page_id)
            if page:
                page.conversions += 1
        db.add(lead)
        db.commit()
        db.refresh(lead)
        record_audit(
            db,
            actor=self.name,
            action="lead_captured",
            entity_type="lead",
            entity_id=lead.id,
            metadata={"score": score, "status": lead.status, "source": lead.source},
        )
        return lead

    def _score(self, payload: LeadCreate) -> float:
        score = 35.0
        if payload.company:
            score += 20
        if payload.message and len(payload.message) > 40:
            score += 25
        if payload.email.split("@")[-1].lower() not in {"gmail.com", "yahoo.com", "hotmail.com"}:
            score += 20
        return min(score, 100.0)

