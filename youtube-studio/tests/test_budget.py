from __future__ import annotations

import pytest

from studio.budget import (
    BudgetExceeded,
    BudgetGuard,
    ConsentRequired,
    PaidProvidersDisabled,
    cost_report,
)
from studio.db import session_scope


def test_default_cap_is_250(settings):
    assert settings.monthly_budget_usd == 250.0
    assert settings.enable_paid is False


def test_free_calls_pass_and_are_logged(settings):
    with session_scope(settings.db_path) as session:
        guard = BudgetGuard(session, settings)
        guard.preflight(provider="mock_voice", operation="tts", estimate_usd=0.0, paid=False)
        guard.record(provider="mock_voice", operation="tts", episode_id="x")
        assert cost_report(session, settings)["entries"] == 1


def test_paid_call_refused_when_flag_off(settings):
    with session_scope(settings.db_path) as session, pytest.raises(PaidProvidersDisabled):
        BudgetGuard(session, settings).preflight(provider="elevenlabs", operation="tts",
                                                 estimate_usd=1.0, paid=True, consent=True)


def test_paid_call_needs_explicit_consent(paid_settings):
    with session_scope(paid_settings.db_path) as session, pytest.raises(ConsentRequired):
        BudgetGuard(session, paid_settings).preflight(provider="elevenlabs",
                                                      operation="tts", estimate_usd=1.0,
                                                      paid=True, consent=False)


def test_any_nonzero_estimate_counts_as_paid(settings):
    with session_scope(settings.db_path) as session, pytest.raises(PaidProvidersDisabled):
        BudgetGuard(session, settings).preflight(provider="sneaky", operation="x",
                                                 estimate_usd=0.01, paid=False)


def test_hard_stop_before_exceeding_monthly_cap(paid_settings):
    with session_scope(paid_settings.db_path) as session:
        guard = BudgetGuard(session, paid_settings)
        guard.preflight(provider="p", operation="a", estimate_usd=6.0, paid=True, consent=True)
        guard.record(provider="p", operation="a", usd=6.0, paid=True)
        with pytest.raises(BudgetExceeded):
            guard.preflight(provider="p", operation="b", estimate_usd=4.01, paid=True,
                            consent=True)
        pf = guard.preflight(provider="p", operation="c", estimate_usd=4.0, paid=True,
                             consent=True)
        assert pf.remaining_after_usd == pytest.approx(0.0)


def test_record_refuses_actual_cost_over_cap(paid_settings):
    with session_scope(paid_settings.db_path) as session:
        guard = BudgetGuard(session, paid_settings)
        guard.record(provider="p", operation="a", usd=9.0, paid=True)
        with pytest.raises(BudgetExceeded):
            guard.record(provider="p", operation="b", usd=2.0, paid=True)


def test_report_has_daily_and_monthly_usage(paid_settings):
    with session_scope(paid_settings.db_path) as session:
        guard = BudgetGuard(session, paid_settings)
        guard.record(provider="p", operation="a", usd=1.5, paid=True, episode_id="ep1")
        rep = cost_report(session, paid_settings)
        assert rep["month_spent_usd"] == pytest.approx(1.5)
        assert rep["day_spent_usd"] == pytest.approx(1.5)
        assert sum(rep["by_day"].values()) == pytest.approx(1.5)
        assert rep["by_episode"]["ep1"] == pytest.approx(1.5)
