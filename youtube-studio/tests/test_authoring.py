"""Hand-written episodes: skeletons, validation and pick-up by research/script/shorts."""

from __future__ import annotations

import shutil

from studio.authoring import author_dir, check, init_files, source_for
from studio.channels import get_channel
from studio.db import session_scope
from studio.episodes import create_episode, workspace


def _episode(settings, channel_key="business_uncovered", topic="How subscription boxes work"):
    ch = get_channel(settings.channels_dir, channel_key)
    with session_scope(settings.db_path) as session:
        ep = create_episode(session, settings, ch, topic, target_minutes=9)
    return ep, workspace(settings, ep).ensure(), ch


def test_skeletons_are_created_once_and_fail_checks(settings):
    ep, ws, ch = _episode(settings)
    written = init_files(ws, ch, ep.title, ep.topic)
    assert {p.name for p in written} == {"research.yaml", "script.yaml", "shorts.yaml",
                                         "README.md"}
    assert init_files(ws, ch, ep.title, ep.topic) == []  # never overwrites
    problems = check(ws, ch, ep.target_minutes)
    assert any("placeholders left" in p for p in problems)
    assert any("PLACEHOLDER" in p or "placeholder" in p for p in problems)


def test_authored_files_are_used_instead_of_samples(settings):
    ep, ws, ch = _episode(settings, "engineering_explained", "Undersea cables, hand written")
    d = author_dir(ws)
    d.mkdir(parents=True)
    for name in ("research.yaml", "script.yaml", "shorts.yaml"):
        shutil.copy(settings.samples_dir / "undersea_cables" / name, d / name)
    problems = check(ws, ch, ep.target_minutes)
    assert problems == [], problems
    provider, sample, src_hash = source_for(ws, settings.samples_dir, None, "script.yaml")
    assert sample == "authoring" and src_hash.startswith("authoring:")
    pack = provider.research(ep.id, ep.topic, sample)
    assert len(pack.claims) == 21
    # editing the file changes the job input hash (so `studio script` re-runs)
    (d / "script.yaml").write_text((d / "script.yaml").read_text() + "\n# edited\n")
    assert source_for(ws, settings.samples_dir, None, "script.yaml")[2] != src_hash


def test_without_authoring_the_sample_is_used(settings):
    ep, ws, ch = _episode(settings)
    provider, sample, src_hash = source_for(ws, settings.samples_dir, "undersea_cables",
                                            "research.yaml")
    assert sample == "undersea_cables" and src_hash == "sample:undersea_cables"


def _speechlike(path, sentences, *, sr=22050, distractor_in=None):
    """Tone bursts per word, short gaps between words, longer pauses between sentences."""
    import math
    import struct
    import wave

    frames = bytearray()
    truth = []
    t = 0.0

    def tone(sec):
        nonlocal t
        n = int(sec * sr)
        for i in range(n):
            frames.extend(struct.pack("<h", int(9000 * math.sin(2 * math.pi * 220 * i / sr))))
        t += n / sr

    def silence(sec):
        nonlocal t
        n = int(sec * sr)
        frames.extend(b"\x00\x00" * n)
        t += n / sr

    silence(0.4)
    for k, sent in enumerate(sentences):
        start = t
        words = sent.split()
        for w_i, w in enumerate(words):
            tone(0.06 * len(w) + 0.05)
            if w_i < len(words) - 1:
                gap = 0.22 if (distractor_in == k and w_i == len(words) // 2) else 0.06
                silence(gap)
        truth.append((start, t))
        silence(0.45)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))
    return truth


def test_user_recording_sentences_align_to_pauses(settings, tmp_path):
    from studio.audio import align_sentences, detect_silences
    from studio.providers.voice import wav_duration

    sentences = ["Cables carry light.", "Repeaters keep the signal strong along the route.",
                 "Ships repair them.", "Many routes keep regions connected when one fails.",
                 "That is the whole story in short."]
    wav = tmp_path / "rec.wav"
    truth = _speechlike(wav, sentences, distractor_in=3)
    spans = align_sentences(sentences, wav_duration(wav),
                            detect_silences(settings.ffmpeg_binary(), wav))
    assert spans is not None and len(spans) == len(sentences)
    for (a, b), (ta, tb) in zip(spans, truth, strict=True):
        assert abs(a - ta) < 0.08 and abs(b - tb) < 0.08, (spans, truth)


def test_too_few_pauses_falls_back(tmp_path):
    from studio.audio import align_sentences

    assert align_sentences(["One.", "Two.", "Three."], 5.0, [(0.0, 0.3)]) is None
