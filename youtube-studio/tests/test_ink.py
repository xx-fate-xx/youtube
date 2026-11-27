"""Sumi-e ink overlays (studio/whatif/ink.py) render to valid SVG at every phase."""

from studio.whatif import ink
from studio.whatif.scene import _svg

W, H = 270, 480


def _alpha_sum(svg: str) -> int:
    img = _svg(svg, W, H)
    return sum(img.getchannel("A").getdata())


def test_label_is_written_on_left_to_right():
    f = ink.label(W / 2, 60, "GROWTH", 40, dur=0.5)
    assert f(0.0, 0.0) == ""
    half, full = _alpha_sum(f(0.25, 0.0)), _alpha_sum(f(0.6, 0.0))
    assert 0 < half < full


def test_bleed_covers_then_reveals():
    cover = ink.bleed(W, H, 0.5, cover=True)
    reveal = ink.bleed(W, H, 0.5, cover=False)
    assert cover(0.0, 0.0) == ""
    assert 'width="270" height="480"' in cover(0.6, 0.0)          # solid ink at the end
    assert 'width="270" height="480"' in reveal(0.0, 0.0)         # solid ink at the start
    assert reveal(0.6, 0.0) == ""
    assert 0 < _alpha_sum(cover(0.3, 0.0)) < W * H * 255


def test_seam_stroke_seal_and_grain_render():
    for svg in (ink.seam(W, H / 2)(0, 0), ink.stroke(20, 100, 200)(1.0, 0),
                ink.seal(135, 300, 60)(1.0, 0),
                ink.grain(W, H)(0, 0)):
        assert _alpha_sum(svg) > 0
