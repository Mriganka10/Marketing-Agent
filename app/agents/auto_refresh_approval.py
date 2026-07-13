from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.llm import LLMService
from app.core.audit import record_audit
from app.core.content_formatting import coerce_text, normalize_sections, normalize_seo
from app.models.entities import (
    LandingPage,
    PageRefreshVersion,
    RefreshApprovalPlan,
    RefreshRecommendation,
)


class AutoRefreshApprovalAgent:
    """Creates guarded page rewrites and publishes only an explicitly approved draft."""

    name = "auto_refresh_approval_agent"

    def __init__(self, llm: LLMService) -> None:
        self.llm = llm

    def draft_rewrite(
        self,
        db: Session,
        recommendation: RefreshRecommendation,
        *,
        performance: dict[str, object] | None = None,
        commit: bool = True,
    ) -> RefreshApprovalPlan:
        existing = (
            db.query(RefreshApprovalPlan)
            .filter(RefreshApprovalPlan.recommendation_id == recommendation.id)
            .first()
        )
        if existing and existing.status != "rejected":
            return existing
        if not recommendation.page_id:
            raise ValueError("This recommendation is not linked to a landing page.")
        page = db.get(LandingPage, recommendation.page_id)
        if not page:
            raise ValueError("The landing page for this recommendation no longer exists.")

        original = self._snapshot(page)
        fallback = self._fallback_rewrite(page, recommendation)
        payload = self.llm.json_completion(
            system=(
                "You are a conversion-focused SEO refresh agent. Rewrite the supplied landing "
                "page in JSON with keys title, hero, sections (array of heading/body), cta, seo "
                "(description and keywords), and change_summary. Preserve factual claims and brand "
                "identity. Do not invent statistics, customers, awards, or guarantees."
            ),
            user=(
                f"Recommendation: {recommendation.recommendation}\n"
                f"Expected impact: {recommendation.expected_impact}\n"
                f"Current page: {original}"
            ),
            fallback=fallback,
        )
        proposed = self._normalize_rewrite(payload, fallback, page)
        proposed["performance_snapshot"] = performance or {}
        proposed["exact_changes"] = self._exact_changes(original, proposed, performance)
        plan = existing or RefreshApprovalPlan(
            recommendation_id=recommendation.id,
            campaign_id=recommendation.campaign_id,
            page_id=page.id,
        )
        plan.original_content = original
        plan.proposed_content = proposed
        plan.change_summary = coerce_text(
            payload.get("change_summary"), str(fallback["change_summary"])
        )
        plan.status = "pending_approval"
        plan.approved_by = None
        plan.approved_at = None
        plan.rejection_reason = None
        plan.rejected_at = None
        plan.published_at = None
        recommendation.status = "pending_approval"
        db.add(plan)
        if commit:
            db.commit()
            db.refresh(plan)
            self._audit(db, "refresh_rewrite_drafted", plan)
        else:
            db.flush()
        return plan

    def approve(
        self, db: Session, plan: RefreshApprovalPlan, *, approved_by: str
    ) -> RefreshApprovalPlan:
        if plan.status == "approved":
            return plan
        if plan.status != "pending_approval":
            raise ValueError(f"Only a pending rewrite can be approved; current state is '{plan.status}'.")
        plan.status = "approved"
        plan.approved_by = approved_by
        plan.approved_at = self._now()
        plan.rejection_reason = None
        plan.recommendation.status = "approved"
        db.commit()
        db.refresh(plan)
        self._audit(db, "refresh_rewrite_approved", plan, {"approved_by": approved_by})
        return plan

    def reject(
        self, db: Session, plan: RefreshApprovalPlan, *, reason: str
    ) -> RefreshApprovalPlan:
        if plan.status == "published":
            raise ValueError("A published rewrite cannot be rejected.")
        if plan.status == "rejected":
            return plan
        plan.status = "rejected"
        plan.rejection_reason = reason
        plan.rejected_at = self._now()
        plan.recommendation.status = "rejected"
        db.commit()
        db.refresh(plan)
        self._audit(db, "refresh_rewrite_rejected", plan, {"reason": reason})
        return plan

    def publish(self, db: Session, plan: RefreshApprovalPlan) -> RefreshApprovalPlan:
        if plan.status == "published":
            return plan
        if plan.status != "approved":
            raise ValueError("The rewrite must be explicitly approved before it can be published.")
        page = db.get(LandingPage, plan.page_id)
        if not page:
            raise ValueError("The landing page for this rewrite no longer exists.")
        if self._snapshot(page) != plan.original_content:
            raise ValueError(
                "The page changed after this rewrite was drafted. Generate a new recommendation "
                "before publishing so reviewed content is never applied to a stale page."
            )

        proposed = plan.proposed_content
        version_number = (
            db.query(func.max(PageRefreshVersion.version_number))
            .filter(PageRefreshVersion.page_id == page.id)
            .scalar()
            or 0
        ) + 1
        db.add(
            PageRefreshVersion(
                page_id=page.id,
                version_number=version_number,
                change_summary=plan.change_summary,
                old_title=page.title,
                new_title=str(proposed["title"]),
                old_hero=page.hero,
                new_hero=str(proposed["hero"]),
                old_cta=page.cta,
                new_cta=str(proposed["cta"]),
                created_by=self.name,
            )
        )
        page.title = str(proposed["title"])
        page.hero = str(proposed["hero"])
        page.sections = proposed["sections"]
        page.cta = str(proposed["cta"])
        page.seo = proposed["seo"]
        page.status = "published"
        plan.status = "published"
        plan.published_at = self._now()
        plan.recommendation.status = "published"
        db.commit()
        db.refresh(plan)
        self._audit(db, "refresh_rewrite_published", plan, {"version": version_number})
        return plan

    def _normalize_rewrite(
        self, payload: dict[str, object], fallback: dict[str, object], page: LandingPage
    ) -> dict[str, object]:
        seo = normalize_seo(payload.get("seo"), dict(fallback["seo"]))
        if page.seo.get("brand_theme"):
            seo["brand_theme"] = page.seo["brand_theme"]
        return {
            "title": coerce_text(payload.get("title"), str(fallback["title"]))[:220],
            "hero": coerce_text(payload.get("hero"), str(fallback["hero"])),
            "sections": normalize_sections(payload.get("sections"), list(fallback["sections"])),
            "cta": coerce_text(payload.get("cta"), str(fallback["cta"]))[:160],
            "seo": seo,
        }

    @staticmethod
    def _exact_changes(
        original: dict[str, object],
        proposed: dict[str, object],
        performance: dict[str, object] | None,
    ) -> list[dict[str, str]]:
        reason = str((performance or {}).get("diagnosis") or "Apply the approved refresh recommendation.")
        original_seo = original.get("seo") if isinstance(original.get("seo"), dict) else {}
        proposed_seo = proposed.get("seo") if isinstance(proposed.get("seo"), dict) else {}
        changes = [
            ("SEO title", original.get("title"), proposed.get("title")),
            ("Hero", original.get("hero"), proposed.get("hero")),
            ("CTA", original.get("cta"), proposed.get("cta")),
            ("Meta description", original_seo.get("description"), proposed_seo.get("description")),
            ("Page sections", original.get("sections"), proposed.get("sections")),
        ]
        return [
            {
                "field": field,
                "current": coerce_text(current, "Not set"),
                "recommended": coerce_text(recommended, "Not set"),
                "reason": reason,
            }
            for field, current, recommended in changes
            if current != recommended
        ]

    def _fallback_rewrite(
        self, page: LandingPage, recommendation: RefreshRecommendation
    ) -> dict[str, object]:
        keywords = list(page.seo.get("keywords") or [])
        primary_keyword = keywords[0] if keywords else page.title
        sections = [dict(section) for section in page.sections]
        sections.append(
            {
                "heading": "A clearer path to results",
                "body": (
                    "See how the approach fits your goals, review the practical next steps, "
                    "and decide whether a focused conversation is worthwhile."
                ),
            }
        )
        return {
            "title": f"{page.title} | A Practical Guide"[:220],
            "hero": f"{page.hero} Explore a clearer, evidence-led path from interest to action.",
            "sections": sections,
            "cta": "See how it works",
            "seo": {
                **page.seo,
                "description": (
                    f"Explore {primary_keyword} with a practical approach, clear next steps, "
                    "and a focused path to action."
                )[:320],
                "keywords": keywords,
            },
            "change_summary": (
                f"Reworked the search snippet, hero, supporting depth, and CTA in response to: "
                f"{recommendation.recommendation}"
            ),
        }

    @staticmethod
    def _snapshot(page: LandingPage) -> dict[str, object]:
        return {
            "title": page.title,
            "hero": page.hero,
            "sections": page.sections,
            "cta": page.cta,
            "seo": page.seo,
            "status": page.status,
        }

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def _audit(
        self,
        db: Session,
        action: str,
        plan: RefreshApprovalPlan,
        metadata: dict[str, object] | None = None,
    ) -> None:
        record_audit(
            db,
            actor=self.name,
            action=action,
            entity_type="refresh_approval_plan",
            entity_id=plan.id,
            metadata={
                "recommendation_id": plan.recommendation_id,
                "page_id": plan.page_id,
                **(metadata or {}),
            },
        )
