"""Shorts (format: short) in the video pipeline: geometry, safe areas, captions, sound library."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from PIL import Image

from studio.pipeline import episode, frames, mix, qa, render, titles

LONG_SOUNDS = textwrap.dedent("""\
    duck_db: {music: 6, ambience: 4, sfx: 6}
    chapter_whoosh: {sfx: whoosh, at: -0.9, gain_db: -12}
    spots:
      key: {prompt: "telegraph key"}
      whoosh: {prompt: "whoosh"}
    ambience:
      room: {prompt: "quiet room", duration: 20}
    music:
      theme: {prompt: "theme", duration: 60}
    """)

SHORT_FRAMES = textwrap.dedent("""\
    #1 | 0:00 | B | close | - | h | Aug 1858
    RU: кадр 1
    VO: A message takes sixteen hours.
    SCENE: A telegraph room at night.
    CHAPTER: The slow cable
    AMB: room
    SFX: key @0.2 -6dB; bell @1 -8dB
    MUSIC: theme

    #2 | 0:03 | A | cutaway | - | h | -
    RU: кадр 2
    VO: The cable soaks up charge.
    SCENE: Cross-section of a cable.
    """)


@pytest.fixture()
def short(tmp_path: Path):
    long_src = tmp_path / "episodes" / "long_ep"
    long_src.mkdir(parents=True)
    (long_src / "episode.yaml").write_text(textwrap.dedent(f"""\
        slug: long_ep
        storyboard_end: "1:00"
        work_dir: {(tmp_path / 'work_long').as_posix()}
        """), encoding="utf-8")
    (long_src / "sounds.yaml").write_text(LONG_SOUNDS, encoding="utf-8")
    sfx = tmp_path / "work_long" / "audio" / "sfx"
    sfx.mkdir(parents=True)
    (sfx / "key.mp3").write_bytes(b"x")
    src = tmp_path / "episodes" / "short_ep"
    src.mkdir(parents=True)
    (src / "episode.yaml").write_text(textwrap.dedent(f"""\
        slug: short_ep
        format: short
        parent: long_ep
        sound_library: {long_src.as_posix()}
        storyboard_end: "0:06"
        work_dir: {(tmp_path / 'work_short').as_posix()}
        eras: {{h: "Historical setting."}}
        image: {{params: {{aspect_ratio: "9:16"}}}}
        """), encoding="utf-8")
    (src / "frames.txt").write_text(SHORT_FRAMES, encoding="utf-8")
    (src / "sounds.yaml").write_text("spots:\n  bell: {prompt: \"small bell\"}\n", encoding="utf-8")
    (src / "characters.yaml").write_text("{}\n", encoding="utf-8")
    e = episode.use(src)
    yield e
    episode._CURRENT = None


def test_short_geometry(short):
    assert short.vertical and short.size == (1080, 1920)
    img, dx, dy = qa.to_frame(Image.new("RGB", (1600, 2400)))
    assert img.size == (1350, 2400) and dx == 250 and dy == 0


def test_vertical_prompt_uses_short_composition(short):
    prompt, _ = frames.image_prompt(frames.parse()[0])
    assert "9:16 vertical frame" in prompt and "16:9 horizontal" not in prompt


def test_sound_library_is_shared(short):
    lib = short.sounds()
    assert set(lib["spots"]) == {"key", "whoosh", "bell"}       # library + the Short's own effect
    assert short.sound_file("spot", "key").parent.parent.parent.name == "work_long"
    assert short.sound_file("spot", "bell").parent.parent.parent.name == "work_short"
    cue = mix.sound_design(write=False)
    assert cue["chapter_whoosh"]["frames"] == []                 # a single chapter: no whoosh
    assert [m["file"] for m in cue["music"]] == ["theme"]
    st = mix.status()
    assert "bell" in {x["id"] for x in st["missing"]}
    assert "key" in {x["id"] for x in st["present"]}


def test_titles_stay_in_shorts_safe_area(short):
    for pos in titles.positions():
        spec = {"main": "4,000+ clocks · 1881", "sub": "CENTRAL PARIS", "pos": pos, "dy": 2000}
        cx, cy = titles.centre(spec)
        bw, bh = titles.block_size("4,000+ clocks · 1881", "CENTRAL PARIS")
        assert cx + bw / 2 <= 0.84 * 1080 + 1     # left of the Shorts button column
        assert cy + bh / 2 <= 0.56 * 1920 + 1     # above the captions and the interface
    layer = titles.draw({"main": "Aug 1858", "sub": None, "pos": "top_center"})
    assert layer.size == (1080, 1920)


def test_short_render_plan_has_no_dips(short):
    rows = render.timeline(frames.parse())
    pl = render.plan(rows, {f["n"]: f for f in frames.parse()}, {}, set())
    assert not any(p["dip_in"] or p["dip_out"] for p in pl.values())


def test_caption_groups_are_short_and_ordered():
    words = [(w, i * 0.4, i * 0.4 + 0.3) for i, w in enumerate(
        "In 1880s Paris, thousands of clocks could not keep time on their own.".split())]
    groups = render.caption_groups(words)
    assert all(len(g[0]) <= 16 or " " not in g[0] for g in groups)
    assert all(len(g[0].split()) <= 3 for g in groups)
    assert groups[0][0] == "In 1880s Paris"
    assert render.caption_text("6,000 pounds, the weight") == "6,000 pounds the weight"
    assert render.caption_text("about 1.5 ft.") == "about 1.5 ft"
    assert render.caption_text("invulnerable? Then") == "invulnerable? Then"
    assert render.caption_text("don't — ever: “really”…") == "don't ever really"
    assert all(a[2] <= b[1] + 1e-9 for a, b in zip(groups, groups[1:], strict=False))
    render.W, render.H = 1080, 1920
    ass = render.captions_ass(groups)
    assert "PlayResX: 1080" in ass and "Inter Display ExtraBold" in ass
    assert ass.count("Dialogue:") == len(groups)
