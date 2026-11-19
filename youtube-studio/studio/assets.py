"""Asset generation (diagrams/cards) and the licence manifest."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from studio.channels import ChannelProfile
from studio.diagrams import get_diagram
from studio.episodes import Workspace
from studio.fsutil import atomic_write_json, read_model, sha256_file
from studio.models import (
    AssetManifest,
    AssetRecord,
    LicenseClearance,
    Scene,
    Storyboard,
    utcnow,
)
from studio.visuals import (
    INTER_DIR,
    Canvas,
    Theme,
    font_is_bundled_inter,
    font_paths,
    text_card,
    title_card,
)

GENERATED_LICENSE = "Original work generated locally by youtube-studio for this channel"


def parse_steps(spec: str, max_step: int) -> list[int]:
    spec = spec.strip()
    if not spec:
        return list(range(0, max_step + 1))
    if "," in spec:
        out: list[int] = []
        for part in spec.split(","):
            out += [x for x in parse_steps(part, max_step) if x not in out]
        return out
    if "-" in spec:
        a, b = (int(x) for x in spec.split("-", 1))
    else:
        a = b = int(spec)
    a, b = max(0, a), min(max_step, b)
    return list(range(a, b + 1)) if a <= b else [min(a, max_step)]


def scene_asset_id(scene: Scene) -> str:
    v = scene.visual
    if v.kind == "diagram":
        return f"diagram-{v.ref}"
    if v.kind == "footage":
        return v.ref
    return f"{v.kind}-{scene.id}"


def scene_canvas(scene: Scene, theme: Theme, channel: ChannelProfile) -> Canvas | None:
    v = scene.visual
    if v.kind == "diagram":
        return get_diagram(v.ref).build(theme)
    if v.kind == "title":
        return title_card(theme, v.ref or scene.section_heading, channel.name)
    if v.kind == "card":
        return text_card(theme, v.ref or scene.section_heading)
    return None  # footage: user-supplied file


def step_png(ws: Workspace, asset_id: str, step: int) -> Path:
    return ws.assets / "rendered" / asset_id / f"step_{step:02d}.png"


def load_manifest(ws: Workspace, episode_id: str) -> AssetManifest:
    if ws.manifest_file.exists():
        return read_model(ws.manifest_file, AssetManifest)
    return AssetManifest(episode_id=episode_id)


def save_manifest(ws: Workspace, manifest: AssetManifest) -> None:
    atomic_write_json(ws.manifest_file, manifest)


def _parse_day(day: str) -> datetime:
    return datetime.fromisoformat(day).replace(tzinfo=UTC)


def bundled_font_issues() -> list[str]:
    """The bundled Inter files must match the hashes recorded at download time."""
    source = json.loads((INTER_DIR / "SOURCE.json").read_text(encoding="utf-8"))
    issues = []
    for name, digest in source["files"].items():
        f = INTER_DIR / name
        if not f.exists():
            issues.append(f"font-main: bundled file missing: {name}")
        elif sha256_file(f) != digest:
            issues.append(f"font-main: {name} changed since download (sha256 mismatch)")
    return issues


def font_record(ws: Workspace) -> AssetRecord:
    paths = font_paths()
    if font_is_bundled_inter():
        source = json.loads((INTER_DIR / "SOURCE.json").read_text(encoding="utf-8"))
        return AssetRecord(
            id="font-main",
            path=str(INTER_DIR),
            kind="font",
            origin="third_party_open_license",
            source_url=source["release_page"],
            author=source["copyright"],
            license=source["license"],
            license_proof=(f"{INTER_DIR / source['license_file']} (bundled licence text); "
                           f"archive {source['source_url']} sha256 {source['archive_sha256']}; "
                           f"key clause: \"{source['license_key_sentence']}\""),
            downloaded_at=_parse_day(source["downloaded_at"]),
            clearance=LicenseClearance.CLEARED,
            sha256=sha256_file(Path(paths[1])) if paths else "",
            attribution_required=False,
            notes=source["use_in_video"],
        )
    path = paths[0] if paths else "Pillow default font"
    return AssetRecord(
        id="font-main",
        path=str(path),
        kind="font",
        origin="system",
        author="font vendor (see file)",
        license="unverified for video use",
        license_proof="",
        clearance=LicenseClearance.UNKNOWN,
        notes=("Confirm the font licence permits text rendered into published video, or set "
               "STUDIO_FONT to an OFL font (e.g. Inter, Source Sans 3) and then run "
               "`studio assets license <ep> font-main --clearance cleared --license OFL-1.1 "
               "--proof <url>`."),
    )


def build_assets(ws: Workspace, board: Storyboard, channel: ChannelProfile) -> AssetManifest:
    """Render every scene's visual (all needed build steps) and record licence metadata."""
    theme = Theme.from_identity(channel.visual)
    manifest = load_manifest(ws, board.episode_id)
    done: set[tuple[str, int]] = set()
    for scene in board.scenes:
        canvas = scene_canvas(scene, theme, channel)
        if canvas is None:
            continue
        asset_id = scene_asset_id(scene)
        steps = parse_steps(scene.visual.steps, canvas.max_step)
        for step in steps:
            if (asset_id, step) in done:
                continue
            canvas.save(None, step_png(ws, asset_id, step), upto=step)
            done.add((asset_id, step))
        svg = ws.assets / "svg" / f"{asset_id}.svg"
        svg.parent.mkdir(parents=True, exist_ok=True)
        svg.write_text(canvas.to_svg(), encoding="utf-8")
        existing = manifest.get(asset_id)
        manifest.upsert(AssetRecord(
            id=asset_id,
            path=str(svg.relative_to(ws.root)),
            kind="diagram" if scene.visual.kind == "diagram" else "card",
            origin="generated_local",
            author=f"{channel.name} (studio diagram code)",
            license=GENERATED_LICENSE,
            license_proof="Generated from source code in studio/diagrams and studio/visuals",
            clearance=LicenseClearance.CLEARED,
            created_at=existing.created_at if existing else utcnow(),
            sha256=sha256_file(svg),
            notes="Schematic diagram, not to scale; contains no third-party imagery.",
        ))
    used = {scene_asset_id(sc) for sc in board.scenes}
    manifest.assets = [a for a in manifest.assets
                       if not (a.origin == "generated_local" and a.kind in {"diagram", "card"}
                               and a.id not in used)]
    current = manifest.get("font-main")
    fresh = font_record(ws)
    # Re-record when the font in use changed; keep a manually cleared record otherwise.
    if current is None or current.path != fresh.path or font_is_bundled_inter():
        manifest.upsert(fresh)
    save_manifest(ws, manifest)
    return manifest


MUSIC_LICENSE = ("Original ambient bed synthesised locally from sine waves (FFmpeg aevalsrc); "
                 "no samples or third-party music")


def music_record(ws: Workspace, path: Path) -> AssetRecord:
    return AssetRecord(
        id="music-bed", path=str(path.relative_to(ws.root)), kind="music",
        origin="generated_local", author="youtube-studio (studio/ffmpeg.py make_music_bed)",
        license=MUSIC_LICENSE,
        license_proof="Generated from the expression in studio/ffmpeg.py:make_music_bed",
        clearance=LicenseClearance.CLEARED, sha256=sha256_file(path),
        notes="Content ID: original synthesis, nothing to match; safe for monetisation.")


def manifest_issues(ws: Workspace, manifest: AssetManifest,
                    board: Storyboard | None = None) -> list[str]:
    """Licence/provenance problems that block approval."""
    issues: list[str] = []
    for a in manifest.assets:
        if not a.license.strip():
            issues.append(f"{a.id}: missing licence")
        if not a.license_proof.strip():
            issues.append(f"{a.id}: missing licence proof")
        if a.clearance != LicenseClearance.CLEARED:
            issues.append(f"{a.id}: clearance is {a.clearance.value} - {a.notes or a.license}")
        if a.attribution_required and not a.attribution_text.strip():
            issues.append(f"{a.id}: attribution required but no attribution text")
        if a.origin in {"stock", "user_supplied"} and a.source_url and not a.downloaded_at:
            issues.append(f"{a.id}: downloaded asset without download timestamp")
        if a.kind == "font" and a.origin == "third_party_open_license":
            issues.extend(bundled_font_issues())
        if a.kind != "font":
            path = ws.root / a.path
            if not path.exists():
                issues.append(f"{a.id}: file missing at {a.path}")
            elif a.sha256 and sha256_file(path) != a.sha256:
                issues.append(f"{a.id}: file changed since it was recorded (sha256 mismatch)")
    if board:
        ids = {a.id for a in manifest.assets}
        for scene in board.scenes:
            sid = scene_asset_id(scene)
            if sid not in ids:
                issues.append(f"{scene.id}: visual '{sid}' has no manifest entry")
    return issues


def attributions(manifest: AssetManifest) -> list[str]:
    return [a.attribution_text for a in manifest.assets if a.attribution_required
            and a.attribution_text]
