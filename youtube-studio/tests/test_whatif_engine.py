"""What If engine (studio/whatif): timing, freezes, backgrounds, chalk, planted feet, placeholder planning."""

from __future__ import annotations

import math
import textwrap
from pathlib import Path

import numpy as np
import pytest

from studio.pipeline import episode
from studio.whatif import backdrop, mocap, overlay, scene
from studio.whatif.motion import Track


def test_seq_times_resolve_from_shot_durations():
    s = scene.Seq(shots=(1, 3), bg="x")
    total = s.layout({1: 2.0, 2: 3.0, 3: 1.0})
    assert total == 6.0
    assert s.T(s.at(2, 0.5)) == 2.5
    assert s.T(s.end(-1.0)) == 5.0
    assert s.T(1.25) == 1.25


def test_freeze_stops_motion_but_not_clip_time():
    s = scene.Seq(shots=(1, 2), bg="x")
    s.freeze(1.0, 2.0, [])
    s.layout({1: 2.0, 2: 2.0})
    bk = scene.Baked(s, 4.0, 30)
    assert bk.n == 120
    assert bk.mt[15] == pytest.approx(0.5)
    assert bk.mt[45] == pytest.approx(1.0)        # frozen
    assert bk.mt[90] == pytest.approx(2.0)        # resumed, 1 s behind the clip clock
    k, since = bk.frozen(1.5)
    assert k == 1.0 and since == pytest.approx(0.5)


def test_backdrop_placeholder_and_ground_band(tmp_path: Path):
    bd = backdrop.Backdrop(tmp_path, "missing_bg", (640, 360), parallax=0.8)
    a = bd.frame(0.0)
    b = bd.frame(900.0, blur_px=12)
    assert a.shape == b.shape == (360, 640, 3)
    assert np.allclose(a[:200], b[:200], atol=1)            # far layer stays put
    still = backdrop.Backdrop(tmp_path, "missing_bg", (640, 360))
    assert still.frame(0.0, desat=1.0).std() <= still.frame(0.0).std() + 1e-6


def test_chalk_writes_progressively():
    assert overlay.chalk_text(0, 0, "AIR", 40, 0.0) == ""
    assert ">A<" in overlay.chalk_text(0, 0, "AIR", 40, 0.2)
    assert ">AI<" in overlay.chalk_text(0, 0, "AIR", 40, 0.5)
    assert ">AIR<" in overlay.chalk_text(0, 0, "AIR", 40, 1.0)
    assert 'stroke-dashoffset="0"' in overlay.chalk_line([(0, 0), (100, 0)], 1.0, rough=False)
    assert overlay.text(0, 0, "a < b & c", 20).count("&lt;") == 1


needs_mocap = pytest.mark.skipif(not (mocap.CACHE / "02.asf").is_file(), reason="CMU mocap cache not downloaded")


@needs_mocap
def test_walk_loop_reproduces_the_captured_foot_path():
    """Feet stay planted exactly as in the capture: the baked world path of the toes equals the mocap path for the
    first cycle, and the loop wrap adds no jump."""
    from studio.whatif.motion import SRC_FPS, loop_cycle
    clip = mocap.clip("walk", SRC_FPS)
    cyc, _adv = loop_cycle(clip, min_len=int(0.66 * SRC_FPS))
    step = SRC_FPS // 30
    per = len(cyc) // step                                         # output frames per cycle
    n = 2 * per + 5
    baked = Track(30).add(0.0, "walk", blend=0.0).bake(n)        # frame i shows capture frame (i + 1) * step
    x, toe = 0.0, []
    for pose, dx in baked:
        x += dx
        toe.append(x + pose["toeL"][0])
    p0 = cyc[0]["pelvis"][0]
    for i in range(per - 1):
        assert toe[i] == pytest.approx(cyc[(i + 1) * step]["toeL"][0] - p0, abs=1e-6)
    # no teleport anywhere, including the loop seams: the biggest pose change between frames stays in line
    # with ordinary limb speed (all values in body heights)
    jumps = [max(math.dist(baked[i][0][j][:2], baked[i - 1][0][j][:2]) for j in baked[i][0]) for i in range(1, n)]
    seam = jumps[per - 3:per + 3]
    rest = jumps[: per - 4]
    assert max(seam) < 1.5 * max(rest)
    assert max(abs(toe[i] - toe[i - 1]) for i in range(1, n)) < 0.12           # peak swing ~4-5 m/s


@pytest.fixture()
def whatif_ep(tmp_path: Path):
    src = tmp_path / "episodes" / "wi_ep"
    src.mkdir(parents=True)
    (src / "episode.yaml").write_text(textwrap.dedent(f"""\
        slug: wi_ep
        style: whatif_stickman
        storyboard_end: "0:09"
        work_dir: {(tmp_path / 'work').as_posix()}
        """), encoding="utf-8")
    (src / "frames.txt").write_text(textwrap.dedent("""\
        #1 | 0:00 | B | wide | - | w | -
        RU: a
        VO: One.
        SCENE: -
        #2 | 0:03 | B | wide | - | w | -
        RU: b
        VO: Two.
        SCENE: -
        #3 | 0:06 | B | wide | - | w | -
        RU: c
        VO: Three.
        SCENE: -
        """), encoding="utf-8")
    (src / "scenes.py").write_text(textwrap.dedent("""\
        from studio.whatif.scene import Seq
        def build(size):
            return [Seq(shots=(1, 2), bg="city")]
        """), encoding="utf-8")
    (src / "characters.yaml").write_text("{}\n", encoding="utf-8")
    e = episode.use(src)
    yield e
    episode._CURRENT = None


def test_uncovered_shots_become_placeholders(whatif_ep):
    from studio.whatif import render as wr
    assert whatif_ep.style().get("engine") == "whatif"
    seqs = wr.plan(whatif_ep.size)
    assert [s.shots for s in seqs] == [(1, 2), (3, 3)]
    assert getattr(seqs[1], "placeholder", False)
    durs, timing = wr.durations(silent=True)
    assert timing is None and durs == {1: 3.0, 2: 3.0, 3: 3.0}


def test_backdrop_wraps_seamlessly_and_scrolls_subpixel(tmp_path: Path):
    from PIL import Image
    rng = np.random.default_rng(1)
    Image.fromarray(rng.integers(0, 255, (180, 400, 3), dtype=np.uint8)).save(tmp_path / "noise.png")
    bd = backdrop.Backdrop(tmp_path, "noise", (320, 180))
    assert bd.span % (2 * bd.tile_w) == 0                     # wraps by whole picture+mirror periods
    for cam in (0.0, 137.0, bd.span - 3.0):
        assert np.allclose(bd.frame(cam), bd.frame(cam + bd.span), atol=1e-3)
    half = bd.frame(100.5)
    assert np.allclose(half, (bd.frame(100.0) + bd.frame(101.0)) / 2, atol=1e-3)
    # a centred blur does not move the picture: the blurred frame's column centroid stays put
    flat = np.zeros((180, 400, 3), dtype=np.uint8)
    flat[:, 250] = 255
    Image.fromarray(flat).save(tmp_path / "line.png")
    ln = backdrop.Backdrop(tmp_path, "line", (320, 180))
    cols = np.arange(320)
    sharp, blurred = ln.frame(0.0)[90, :, 0], ln.frame(0.0, blur_px=21)[90, :, 0]
    assert (sharp * cols).sum() / sharp.sum() == pytest.approx((blurred * cols).sum() / blurred.sum(), abs=0.6)


def test_end_freeze_holds_to_the_cut():
    s = scene.Seq(shots=(1, 1), bg="x")
    s.freeze(2.0, s.end(-0.3), [])
    s.layout({1: 4.0})
    bk = scene.Baked(s, 4.0, 30)
    assert bk.frozen(3.9)[0] == 1.0                            # no split-second of motion before the next shot


@needs_mocap
def test_one_shot_clip_then_hold_does_not_drift():
    tr = Track(30).add(0.0, "walk").add(1.0, "stand", blend=0.3)
    baked = tr.bake(240)
    assert all(abs(dx) < 1e-9 for _p, dx in baked[45:])      # the stand clip is short: then it holds, no slide


@needs_mocap
def test_planted_feet_are_flat_on_the_floor():
    from studio.whatif import rig
    stand = mocap.clip("stand", 120)[-1]
    p = rig.styled(stand)
    for side in "LR":
        assert p["heel" + side][1] == pytest.approx(rig.SOLE, abs=2e-3)
        assert p["tip" + side][1] == pytest.approx(rig.SOLE, abs=2e-3)
        assert p["tip" + side][0] > p["ankle" + side][0] > p["heel" + side][0]


@needs_mocap
def test_follow_camera_glides_while_running():
    s = scene.Seq(shots=(1, 1), bg="x")
    hero = s.actor(x=600, h=250, hero=True)
    hero.run(0.0, cadence=1.4)
    s.follow(hero, 0.0)
    s.layout({1: 6.0})
    bk = scene.Baked(s, 6.0, 30)
    d = np.diff(bk.cam_x[60:170])
    assert d.min() > 0 and (d.max() - d.min()) < 0.08 * d.mean()   # steady pan, no surge per step


@needs_mocap
def test_stand_pose_is_upright():
    """The captured stance is a ~32 deg crouch; the library straightens it (feet kept, knees opened)."""
    f = mocap.clip("stand", 30)[-1]
    raw = mocap.load_cmu("16_33", 30)[-1]
    for side in "LR":
        h, k, a = (np.array(f[j + side][:2]) for j in ("hip", "knee", "ankle"))
        v1, v2 = h - k, a - k
        flex = 180 - math.degrees(math.acos(v1 @ v2 / np.linalg.norm(v1) / np.linalg.norm(v2)))
        assert flex < 12
        assert f["ankle" + side] == raw["ankle" + side]               # feet untouched
        assert np.linalg.norm(h - k) == pytest.approx(np.linalg.norm(np.array(raw["hip" + side][:2])
                                                                     - np.array(raw["knee" + side][:2])), abs=1e-6)


def test_comic_cut_and_tweens():
    from studio.whatif import comic
    c = comic.Comic(shots=(1, 2), plate="x")
    c.cast("a", height=500)
    c.key("a", 0.0, "a0", 100, 1000)
    c.key("a", 1.0, "a0", 300, 1000, tween="lin")
    c.hide("a", 2.0)
    c.cam(0.0, 100, 100, 1000)
    c.cam(c.at(2), 900, 500, 2000, "hold")             # hard cut exactly at shot 2
    c.layout({1: 1.5, 2: 1.0})
    assert comic.cast_state(c, c.casts["a"], 0.5)[1] == pytest.approx(200)
    assert comic.cast_state(c, c.casts["a"], 2.1) is None
    assert comic._cam(c, 1.49, 2688, 1520) == (100, 100, 1000)
    assert comic._cam(c, 1.5, 2688, 1520) == (900, 500, 2000)     # the cut lands on its own frame
