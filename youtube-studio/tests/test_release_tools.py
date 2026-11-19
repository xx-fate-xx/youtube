"""Chapters, description, music selection and thumbnail variants (all offline)."""

from __future__ import annotations

import wave

from studio.assets import load_manifest, save_manifest
from studio.models import (
    AssetRecord,
    LicenseClearance,
    NarrationTrack,
    Scene,
    SceneTiming,
    Storyboard,
    VisualSpec,
)
from studio.publish import chapters, fmt_ts


def _board(ws, sections):
    """sections: list of (heading, start_s); one scene per section."""
    scenes, timings = [], []
    for i, (heading, start) in enumerate(sections):
        scenes.append(Scene(id=f"sc{i}", index=i, section_id=f"s{i}", section_heading=heading,
                            narration="x", claim_ids=[],
                            visual=VisualSpec(kind="card", ref=heading),
                            est_duration_s=1, starts_section=True, ends_section=True))
        end = sections[i + 1][1] if i + 1 < len(sections) else start + 40
        timings.append(SceneTiming(scene_id=f"sc{i}", start=start, end=end, words=[]))
    ws.storyboard_file.parent.mkdir(parents=True, exist_ok=True)
    ws.storyboard_file.write_text(Storyboard(episode_id="e", scenes=scenes).model_dump_json())
    ws.narration_file.parent.mkdir(parents=True, exist_ok=True)
    ws.narration_file.write_text(NarrationTrack(
        episode_id="e", provider="mock_voice", voice="v", audio_path="a.wav",
        duration_s=timings[-1].end, is_placeholder=True, timing_method="estimated",
        license_asset_id="narration", scenes=timings).model_dump_json())


def test_fmt_ts():
    assert fmt_ts(0) == "0:00" and fmt_ts(65.9) == "1:05" and fmt_ts(3725) == "1:02:05"


def test_chapters_follow_youtube_rules(settings, episode):
    _, ws, _ = episode
    _board(ws, [("Hook", 0), ("Map", 30), ("Too close", 34), ("Glass", 90), ("Recap", 200)])
    ch = chapters(ws)
    assert ch[0] == (0.0, "Hook")
    assert [t for t, _ in ch] == sorted(t for t, _ in ch)
    assert "Too close" not in [h for _, h in ch]  # < 10 s after the previous chapter
    assert all(b - a >= 10 for (a, _), (b, _) in zip(ch, ch[1:], strict=False))


def test_fewer_than_three_chapters_are_dropped(settings, episode):
    _, ws, _ = episode
    _board(ws, [("Hook", 0), ("Only", 60)])
    assert chapters(ws) == []


def _tone(path, seconds=3.0, sr=22050):
    import math
    import struct

    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(4000 * math.sin(i / 20)))
                               for i in range(int(sr * seconds))))


def test_licensed_music_track_replaces_generated_bed(settings, episode, tmp_path):
    from studio import ffmpeg

    ep, ws, _ = episode
    binary = settings.ffmpeg_binary()
    out, source = ffmpeg.music_for(binary, ws.audio, load_manifest(ws, ep.id), ws.root, 6.0)
    assert source == "generated" and ffmpeg.probe_duration(binary, out) >= 6.0
    track = ws.root / "assets" / "user" / "music-track.wav"
    track.parent.mkdir(parents=True, exist_ok=True)
    _tone(track)
    manifest = load_manifest(ws, ep.id)
    rec = AssetRecord(id="music-track", path=str(track.relative_to(ws.root)), kind="music",
                      origin="user_supplied", author="Library", license="YouTube Audio Library",
                      license_proof="screenshot.png", clearance=LicenseClearance.RESTRICTED)
    manifest.upsert(rec)
    save_manifest(ws, manifest)
    # restricted -> not used
    assert ffmpeg.music_for(binary, ws.audio, load_manifest(ws, ep.id), ws.root, 6.0)[1] == \
        "generated"
    rec.clearance = LicenseClearance.CLEARED
    manifest.upsert(rec)
    save_manifest(ws, manifest)
    out, source = ffmpeg.music_for(binary, ws.audio, load_manifest(ws, ep.id), ws.root, 7.0)
    assert source == "licensed:music-track"
    assert abs(ffmpeg.probe_duration(binary, out) - 7.0) < 0.2  # looped to length


def test_thumbnail_variants_are_readable_and_small(settings, tmp_path):
    from studio.channels import get_channel
    from studio.thumbnails import readability_issues, render_variants

    ch = get_channel(settings.channels_dir, "engineering_explained")
    variants = render_variants(tmp_path, title="How Undersea Internet Cables Actually Work",
                               hook="Internet under the sea", channel=ch,
                               diagram="cable_cross_section")
    assert [v.key for v in variants] == ["a_classic", "b_hook", "c_split"]
    assert readability_issues(variants) == []
    from PIL import Image

    assert all(Image.open(v.path).size == (1280, 720) for v in variants)
