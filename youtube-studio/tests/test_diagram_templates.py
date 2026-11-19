"""YAML diagram templates: validation, layout QA, motion and Shorts compatibility."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter

from studio.diagrams import get_diagram, has_diagram, layout_issues, spec_ids
from studio.diagrams.templates import TEMPLATE_TYPES, DiagramSpec
from studio.models import Script, ScriptParagraph, ScriptSection, ShortSpec, VisualSpec
from studio.motion import SceneRenderer, plan_scene
from studio.visuals import Theme

THEME = Theme("#0B1D2A", "#EAF2F7", "#2EC4B6", "#FFB703", "#6B8496", "#06121BCC", "Inter")


def parse(data: dict):
    return TypeAdapter(DiagramSpec).validate_python(data)


def test_every_example_spec_builds_clean_and_covers_all_types():
    ids = spec_ids()
    types = set()
    for ref in ids:
        d = get_diagram(ref)
        types.add(d.spec.type)
        canvas = d.build(THEME)
        assert canvas.max_step >= 0
        assert layout_issues(canvas) == [], ref
    assert types == set(TEMPLATE_TYPES)


def test_templates_animate_through_the_motion_engine():
    for ref in spec_ids():
        d = get_diagram(ref)
        canvas = d.build(THEME)
        plan = plan_scene(canvas, list(range(canvas.max_step + 1)), 8.0,
                          camera=d.default_camera)
        r = SceneRenderer(canvas, plan, (320, 180), layer_scale=0.5)
        a, b = r.frame(0.2).tobytes(), r.frame(7.5).tobytes()
        assert a != b, f"{ref}: nothing moves"


def test_numbers_on_screen_need_claims():
    base = {"type": "stat", "title": "Faults", "value": "70-80%", "label": "accidental",
            "source": "ICPC"}
    with pytest.raises(ValueError, match="claims"):
        parse(base)
    assert parse({**base, "claims": ["C9"]}).value == "70-80%"
    with pytest.raises(ValueError, match="claims"):
        parse({"type": "timeline", "title": "T", "events": [
            {"when": "1858", "label": "a"}, {"when": "2006", "label": "b"}]})


def test_process_numbering_is_not_a_fact():
    spec = parse({"type": "process", "title": "Steps", "steps": [
        {"title": "Survey"}, {"title": "Lay"}]})
    assert spec.claims == []


def test_map_references_are_checked():
    nodes = [{"id": "A", "x": 500, "y": 400}, {"id": "B", "x": 1400, "y": 400}]
    with pytest.raises(ValueError, match="unknown node"):
        parse({"type": "map", "title": "M", "nodes": nodes,
               "routes": [{"from": "A", "to": "Z"}]})
    with pytest.raises(ValueError, match="unknown route"):
        parse({"type": "map", "title": "M", "nodes": nodes,
               "routes": [{"from": "A", "to": "B"}], "cuts": [{"route": "B-A"}]})
    with pytest.raises(ValueError, match="extra"):
        parse({"type": "map", "title": "M", "nodes": nodes, "colour": "red"})


def test_measured_comparison_needs_claims():
    items = [{"label": "a", "value": 1.0}, {"label": "b", "value": 0.3}]
    with pytest.raises(ValueError, match="claims"):
        parse({"type": "comparison", "title": "C", "items": items, "data": True})
    spec = parse({"type": "comparison", "title": "C", "items": items})
    assert spec.footnote.startswith("Bar lengths illustrate")


def test_unknown_diagram_and_spec_dir_override(tmp_path, monkeypatch):
    assert not has_diagram("nope")
    with pytest.raises(KeyError):
        get_diagram("nope")
    monkeypatch.setenv("STUDIO_DIAGRAM_SPECS", str(tmp_path))
    (tmp_path / "x_steps.yaml").write_text(
        "type: process\ntitle: Two steps\nsteps:\n  - {title: One}\n  - {title: Two}\n")
    assert has_diagram("x_steps") and get_diagram("x_steps").default_camera == "wide"


def test_storyboard_warns_when_diagram_facts_are_not_cited(settings):
    from studio.channels import get_channel
    from studio.storyboard import build_storyboard

    ch = get_channel(settings.channels_dir, "engineering_explained")

    def script(claims):
        para = ScriptParagraph(text="Most faults are accidental.", claim_ids=claims,
                               visual=VisualSpec(kind="diagram", ref="ee_fault_causes"))
        return Script(episode_id="e", title="t", generated_by="test", sections=[ScriptSection(
            id="s", heading="h", paragraphs=[para])])

    _, warnings = build_storyboard(script([]), ch)
    assert any("C9" in w for w in warnings)
    _, warnings = build_storyboard(script(["C9"]), ch)
    assert warnings == []


def test_templates_work_in_shorts_with_legible_labels():
    from studio.shorts import legibility_issues, prepare_short

    spec = ShortSpec(id="s", title="t", hook="h", narration="n", diagram="ee_cable_lifecycle",
                     focus="90,250,800,623|1010,250,800,623", steps="0-4")
    canvas, plan, dropped = prepare_short(spec, THEME, 25.0)
    assert legibility_issues(spec, canvas, plan) == []
