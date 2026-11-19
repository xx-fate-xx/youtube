"""Footage / image providers. MVP: locally supplied files with explicit licence metadata."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from studio.fsutil import sha256_file
from studio.models import AssetRecord, LicenseClearance

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".png", ".jpg", ".jpeg", ".wav", ".mp3", ".m4a"}


def import_local_asset(
    episode_dir: Path,
    file: Path,
    *,
    asset_id: str,
    kind: str,
    author: str,
    license: str,
    license_proof: str,
    clearance: LicenseClearance,
    source_url: str = "",
    attribution_text: str = "",
    ai_generated: bool = False,
    realistic: bool = False,
    origin: str = "user_supplied",
) -> AssetRecord:
    """Copy a user-supplied file into the episode and return its licence record.

    The operator states the licence; nothing here assumes a file is reusable.
    """
    if not file.is_file():
        raise FileNotFoundError(file)
    if file.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type {file.suffix}")
    if not license.strip() or not license_proof.strip():
        raise ValueError("license and license_proof are required for every imported asset")
    dest = episode_dir / "assets" / "user" / f"{asset_id}{file.suffix.lower()}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file, dest)
    return AssetRecord(
        id=asset_id,
        path=str(dest.relative_to(episode_dir)),
        kind=kind,
        origin=origin,
        author=author,
        license=license,
        license_proof=license_proof,
        clearance=clearance,
        source_url=source_url,
        downloaded_at=datetime.now(UTC) if source_url else None,
        attribution_required=bool(attribution_text),
        attribution_text=attribution_text,
        ai_generated=ai_generated,
        realistic=realistic,
        sha256=sha256_file(dest),
    )
