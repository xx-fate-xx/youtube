"""Budget guard and cost ledger.

Rules (enforced, not advisory):
- A paid call needs STUDIO_ENABLE_PAID_PROVIDERS=1 AND explicit per-call operator consent.
- A paid call whose estimate would push the calendar-month total over the cap is refused.
- Every call (free or paid) is written to the ledger so usage is auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlmodel import Session, col, func, select

from studio.config import Settings
from studio.models import CostEntry


class BudgetError(RuntimeError):
    pass


class PaidProvidersDisabled(BudgetError):
    pass


class ConsentRequired(BudgetError):
    pass


class BudgetExceeded(BudgetError):
    pass


@dataclass(frozen=True)
class Preflight:
    provider: str
    operation: str
    estimate_usd: float
    month_spent_usd: float
    monthly_cap_usd: float
    paid: bool

    @property
    def remaining_after_usd(self) -> float:
        return self.monthly_cap_usd - self.month_spent_usd - self.estimate_usd


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


class BudgetGuard:
    def __init__(self, session: Session, settings: Settings, now: datetime | None = None):
        self.session = session
        self.settings = settings
        self._now = now

    def now(self) -> datetime:
        return self._now or datetime.now(UTC)

    def _spent_since(self, start: datetime) -> float:
        stmt = select(func.coalesce(func.sum(CostEntry.usd), 0.0)).where(
            col(CostEntry.at) >= start, CostEntry.kind == "actual"
        )
        return float(self.session.exec(stmt).one())

    def month_spent(self) -> float:
        return self._spent_since(_month_start(self.now()))

    def day_spent(self) -> float:
        return self._spent_since(_day_start(self.now()))

    def preflight(
        self,
        *,
        provider: str,
        operation: str,
        estimate_usd: float,
        paid: bool,
        consent: bool = False,
        episode_id: str | None = None,
    ) -> Preflight:
        if estimate_usd < 0:
            raise ValueError("estimate_usd must be >= 0")
        is_paid = paid or estimate_usd > 0
        spent = self.month_spent()
        pf = Preflight(provider, operation, estimate_usd, spent, self.settings.monthly_budget_usd,
                       is_paid)
        if not is_paid:
            return pf
        if not self.settings.enable_paid:
            raise PaidProvidersDisabled(
                f"{provider}.{operation}: paid providers are disabled "
                "(set STUDIO_ENABLE_PAID_PROVIDERS=1 to allow, still requires consent)."
            )
        if not consent:
            raise ConsentRequired(
                f"{provider}.{operation}: estimated ${estimate_usd:.2f}. Re-run with explicit "
                "consent (e.g. --i-consent-to-spend) after reviewing the estimate."
            )
        if spent + estimate_usd > self.settings.monthly_budget_usd:
            raise BudgetExceeded(
                f"{provider}.{operation}: ${estimate_usd:.2f} would exceed monthly cap "
                f"${self.settings.monthly_budget_usd:.2f} (spent ${spent:.2f})."
            )
        self.session.add(
            CostEntry(episode_id=episode_id, provider=provider, operation=operation,
                      usd=estimate_usd, kind="estimate", paid=True,
                      consent_ref=f"consent@{self.now().isoformat()}")
        )
        return pf

    def record(
        self,
        *,
        provider: str,
        operation: str,
        usd: float = 0.0,
        units: float = 0.0,
        unit: str = "",
        paid: bool = False,
        episode_id: str | None = None,
    ) -> CostEntry:
        if paid and usd > 0 and self.month_spent() + usd > self.settings.monthly_budget_usd:
            # Should not happen after preflight, but never record silently over cap.
            raise BudgetExceeded(f"Actual cost ${usd:.2f} for {provider} exceeds monthly cap")
        entry = CostEntry(episode_id=episode_id, provider=provider, operation=operation, usd=usd,
                          units=units, unit=unit, kind="actual", paid=paid)
        self.session.add(entry)
        self.session.flush()
        return entry


def cost_report(session: Session, settings: Settings, now: datetime | None = None) -> dict:
    guard = BudgetGuard(session, settings, now)
    rows = session.exec(select(CostEntry).where(CostEntry.kind == "actual")).all()
    by_day: dict[str, float] = {}
    by_month: dict[str, float] = {}
    by_episode: dict[str, float] = {}
    by_provider: dict[str, dict[str, float]] = {}
    for r in rows:
        day = r.at.strftime("%Y-%m-%d")
        month = r.at.strftime("%Y-%m")
        by_day[day] = by_day.get(day, 0.0) + r.usd
        by_month[month] = by_month.get(month, 0.0) + r.usd
        if r.episode_id:
            by_episode[r.episode_id] = by_episode.get(r.episode_id, 0.0) + r.usd
        p = by_provider.setdefault(r.provider, {"calls": 0, "usd": 0.0})
        p["calls"] += 1
        p["usd"] += r.usd
    return {
        "monthly_cap_usd": settings.monthly_budget_usd,
        "paid_providers_enabled": settings.enable_paid,
        "month_spent_usd": round(guard.month_spent(), 4),
        "day_spent_usd": round(guard.day_spent(), 4),
        "remaining_month_usd": round(settings.monthly_budget_usd - guard.month_spent(), 4),
        "by_day": dict(sorted(by_day.items())),
        "by_month": dict(sorted(by_month.items())),
        "by_episode": by_episode,
        "by_provider": by_provider,
        "entries": len(rows),
    }
