from __future__ import annotations

from studio.analytics import add_mock_stats, channel_report, import_csv
from studio.captions import cues_from_words, parse_srt, srt_time, to_srt
from studio.db import session_scope
from studio.models import ResearchPack, Script, ScriptParagraph, ScriptSection, WordTiming
from studio.providers.llm import MockLLMProvider
from studio.shorts import overlap, shorts_issues


def test_srt_time_format():
    assert srt_time(0) == "00:00:00,000"
    assert srt_time(3661.5) == "01:01:01,500"


WORDS = "one two three four five six seven eight nine ten. Eleven twelve.".split()


def test_cues_respect_length_and_roundtrip():
    words = [WordTiming(word=w, start=i * 0.4, end=i * 0.4 + 0.35)
             for i, w in enumerate(WORDS)]
    cues = cues_from_words(words, max_chars=20)
    assert all(len(c.text) <= 20 for c in cues)
    assert any(c.text.endswith("ten.") for c in cues)
    assert all(a.end <= b.start for a, b in zip(cues, cues[1:], strict=False))
    back = parse_srt(to_srt(cues))
    assert [c.text for c in back] == [c.text for c in cues]


def test_sample_shorts_are_independent_of_long_script(settings, episode):
    ep, _, ch = episode
    llm = MockLLMProvider(settings.samples_dir)
    pack = llm.research(ep.id, ep.topic, "undersea_cables")
    script = llm.script(ep.id, ep.title, ch, pack, 9, "undersea_cables")
    shorts = llm.shorts(ep.id, ep.title, pack, 3, "undersea_cables")
    assert len(shorts) == 3
    assert shorts_issues(shorts, script, pack, ch) == []


def test_copied_short_is_flagged(settings, episode):
    ep, _, ch = episode
    llm = MockLLMProvider(settings.samples_dir)
    pack = llm.research(ep.id, ep.topic, "undersea_cables")
    script = llm.script(ep.id, ep.title, ch, pack, 9, "undersea_cables")
    shorts = llm.shorts(ep.id, ep.title, pack, 3, "undersea_cables")
    shorts[0].narration = script.sections[2].paragraphs[0].text
    assert any("copied from the long script" in i
               for i in shorts_issues(shorts, script, pack, ch))
    assert overlap("a b c d e f", "a b c d e f") == 1.0


def test_csv_import_and_comparison(settings, tmp_path):
    csv_file = tmp_path / "export.csv"
    csv_file.write_text(
        "Content,Video title,Views,Impressions,Impressions click-through rate (%),"
        "Average view duration,Subscribers\n"
        "Total,,300,5000,6.0,0:03:00,7\n"
        "abc123,Video A,200,3000,6.5,0:03:10,5\n"
        "def456,Video B,100,2000,5.0,0:02:40,2\n", encoding="utf-8")
    with session_scope(settings.db_path) as session:
        assert import_csv(session, "engineering_explained", csv_file) == 2
        add_mock_stats(session, "business_uncovered", [], 30)
        session.flush()
        rep = channel_report(session)
    ee = rep["engineering_explained"]
    assert ee["views"] == 300 and ee["impressions"] == 5000
    assert ee["avg_view_duration_s"] == 175.0
    assert ee["sources"] == ["csv"]


def test_placeholder_script_is_marked(settings):
    from studio.channels import get_channel

    ch = get_channel(settings.channels_dir, "ai_workflow_lab")
    s = MockLLMProvider(settings.samples_dir).script(
        "e", "t", ch, ResearchPack(episode_id="e", topic="t", generated_by="x"), 10, None)
    assert s.is_placeholder and "[PLACEHOLDER" in s.narration_text
    assert isinstance(s, Script) and isinstance(s.sections[0], ScriptSection)
    assert isinstance(s.sections[0].paragraphs[0], ScriptParagraph)
