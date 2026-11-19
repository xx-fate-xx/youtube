from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from studio.channels import get_channel
from studio.config import Settings, load_settings
from studio.db import session_scope
from studio.episodes import create_episode, workspace

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    for var in ("STUDIO_ENABLE_PAID_PROVIDERS", "STUDIO_ENABLE_YOUTUBE", "STUDIO_PROJECTS_DIR",
                "STUDIO_MONTHLY_BUDGET_USD", "YOUTUBE_CLIENT_SECRETS_FILE"):
        monkeypatch.delenv(var, raising=False)
    shutil.copytree(REPO / "channels", tmp_path / "channels")
    shutil.copytree(REPO / "samples", tmp_path / "samples")
    return load_settings(tmp_path)


@pytest.fixture
def paid_settings(settings: Settings) -> Settings:
    return replace(settings, enable_paid=True, monthly_budget_usd=10.0)


@pytest.fixture
def episode(settings: Settings):
    channel = get_channel(settings.channels_dir, "engineering_explained")
    with session_scope(settings.db_path) as session:
        ep = create_episode(session, settings, channel, "How undersea internet cables work",
                            target_minutes=9, sample="undersea_cables")
    return ep, workspace(settings, ep), channel
