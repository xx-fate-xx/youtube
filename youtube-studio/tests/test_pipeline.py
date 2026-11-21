"""Generic video pipeline (studio.pipeline): annotations, sound design, gates, render plan."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from studio.pipeline import episode, frames, mix, originality, preflight, production, render, titles

FRAMES = textwrap.dedent("""\
    # test storyboard
    #1 | 0:00 | B | medium | - | h | 16 Aug 1858
    RU: кадр 1
    VO: On August 16, 1858, a message crosses the ocean.
    SCENE: A telegraph room at night lit by an oil lamp.
    CHAPTER: The message
    AMB: room
    SFX: key @0.3 -4dB; boom @1 -6dB max=2
    MUSIC: theme
    AI_CLIP: yes

    #2 | 0:04 | A | wide | - | h | -
    RU: кадр 2
    VO: The cable is two thousand miles long.
    SCENE: Wide view of a stormy sea with two ships.
    FX: rain, lightning@2.5
    CAMERA: sway

    #3 | 0:08 | A | close | - | h | -
    RU: кадр 3
    VO: Then the signal fades.
    SCENE: Close view of a brass instrument.
    AMB: -
    TITLE: William Thomson | Glasgow

    #4 | 0:11 | A | infographic | - | - | ~10 days
    RU: кадр 4
    VO: News took ten days.
    SCENE: A calendar with pages flying away.
    CHAPTER: Ten days behind
    AMB: room
    MUSIC: theme2 -2dB

    #5 | 0:14 | B | wide | - | m | -
    RU: кадр 5
    VO: Today light carries the data.
    SCENE: Modern cable on the seabed.
    ANIM: pulses run along the cable || slow pan from left to right || cable stays still
    FX: bubbles
    """)

SOUNDS = textwrap.dedent("""\
    duck_db: {music: 6, ambience: 4, sfx: 6}
    chapter_whoosh: {sfx: whoosh, at: -0.9, gain_db: -12}
    spots:
      key: {prompt: "telegraph key"}
      boom: {prompt: "boom"}
      whoosh: {prompt: "whoosh"}
    ambience:
      room: {prompt: "quiet room", duration: 20, gain_db: -2}
    music:
      theme: {prompt: "theme", duration: 10}
      theme2: {prompt: "theme 2", duration: 10}
    """)


@pytest.fixture()
def ep(tmp_path: Path):
    src = tmp_path / "episodes" / "test_ep"
    src.mkdir(parents=True)
    (src / "episode.yaml").write_text(textwrap.dedent(f"""\
        slug: test_ep
        title: Test
        storyboard_end: "0:20"
        work_dir: {(tmp_path / 'work').as_posix()}
        eras: {{h: "Historical setting."}}
        budget: {{higgsfield_credits: 20, elevenlabs_credits: 5000, retry_reserve: 0.10}}
        """), encoding="utf-8")
    (src / "frames.txt").write_text(FRAMES, encoding="utf-8")
    (src / "sounds.yaml").write_text(SOUNDS, encoding="utf-8")
    (src / "characters.yaml").write_text("{}\n", encoding="utf-8")
    e = episode.use(src)
    yield e
    episode._CURRENT = None


def test_annotations_are_parsed(ep):
    fr = frames.parse()
    assert frames.chapters(fr) == [(1, "The message"), (4, "Ten days behind")]
    assert fr[0]["ai_clip"] and fr[0]["music"] == {"file": "theme", "gain_db": 0.0}
    assert fr[0]["sfx"][1] == {"sfx": "boom", "frame": 1, "at": 1.0, "gain_db": -6.0, "max_s": 2.0}
    assert fr[1]["fx"] == ["rain", "lightning@2.5"] and fr[1]["camera"] == "sway"
    assert fr[1]["amb"] == "room"            # AMB persists into the next frame
    assert fr[2]["amb"] is None              # "AMB: -" stops it
    assert fr[2]["title"] == ("William Thomson", "Glasgow")
    assert fr[3]["title"] == ("~10 days", None)       # header column becomes a one-line title
    assert [f["duration"] for f in fr] == [4, 4, 3, 3, 6]


def test_sound_design_is_derived(ep):
    cue = mix.sound_design(write=False)
    assert cue["ambience"] == {"room": [[1, 2], [4, 5]]}
    assert cue["ambience_gain_db"] == {"room": -2}
    assert [s["sfx"] for s in cue["spots"]] == ["key", "boom"]
    assert cue["music"] == [{"file": "theme", "from_frame": 1, "to_frame": 4, "gain_db": 0.0},
                            {"file": "theme2", "from_frame": 4, "to_frame": None, "gain_db": -2.0}]
    assert cue["chapter_whoosh"]["frames"] == [4]


def test_unknown_sound_is_rejected(ep):
    bad = FRAMES.replace("SFX: key @0.3", "SFX: nope @0.3")
    (ep.src / "frames.txt").write_text(bad, encoding="utf-8")
    with pytest.raises(SystemExit, match="nope"):
        mix.sound_design(write=False)


def test_render_plan_uses_annotations(ep):
    fr = {f["n"]: f for f in frames.parse()}
    pl = render.plan(render.timeline(list(fr.values())), fr, {}, {1})
    assert pl[1]["move"] == "ai_clip" and pl[1]["dip_in"]
    assert pl[2]["move"] == "sway" and pl[2]["fx"] == ["rain", "lightning"]
    assert pl[2]["lightning_t"] == 2.5
    assert pl[3]["dip_out"] and pl[4]["dip_in"]          # chapter boundary dips to black
    assert pl[5]["move"] == "pan_lr" and "bubbles" in pl[5]["fx"]
    assert "lamp" in pl[1]["fx"]                          # auto lamp flicker from the scene text
    moves = [pl[n]["move"] for n in sorted(pl)]
    assert all(a != b for a, b in zip(moves, moves[1:], strict=False))  # never repeat a move


def test_title_split_and_specs(ep):
    sp = titles.specs()
    assert sp[3]["main"] == "William Thomson" and sp[3]["sub"] == "GLASGOW"
    assert sp[1]["pos"] == "bottom_center" and sp[1]["source"] == "default"


def test_originality_gate():
    ours = ("The first cable across the Atlantic failed within a month because the insulation "
            "broke down.")
    copied = ("Some intro words here. The first cable across the Atlantic failed within a month "
              "because the insulation broke down. More words.")
    other = ("A telegraph line was laid in 1858 and stopped working in September after weeks "
             "of weak signals.")
    assert not originality.compare(ours, copied)["ok"]
    res = originality.compare(ours, other)
    assert res["ok"] and res["longest_shared_run"] < originality.MAX_RUN


def test_paid_steps_need_operator_approval(ep):
    frames.build()
    with pytest.raises(SystemExit, match="approval"):
        production.cmd_next(type("A", (), {"batch": 2})())
    est = preflight.estimate()
    assert est["higgsfield"]["images_to_generate"] == 5
    assert est["higgsfield"]["ai_clips"] == 1
    assert est["elevenlabs"]["narration_chars"] > 0 and est["elevenlabs"]["sounds"] > 0
    rec = preflight.approve("test")
    assert rec["approved"] and preflight.approved()


def test_preflight_refuses_over_budget(ep):
    frames.build()
    cfg = ep.src / "episode.yaml"
    text = cfg.read_text(encoding="utf-8")
    text = text.replace("higgsfield_credits: 20", "higgsfield_credits: 2")
    cfg.write_text(text, encoding="utf-8")
    episode.use(ep.src)
    with pytest.raises(SystemExit, match="budget"):
        preflight.approve()
    assert not (episode.ep().work / "preflight.json").exists() or not json.loads(
        (episode.ep().work / "preflight.json").read_text(encoding="utf-8")).get("approved")
