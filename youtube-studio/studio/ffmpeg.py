"""Thin FFmpeg wrapper. Only portable features are used (no libass/drawtext dependency)."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


@dataclass(frozen=True)
class EncodeProfile:
    name: str
    preset: str
    crf: int
    fps: int = 30
    audio_bitrate: str = "192k"


PREVIEW = EncodeProfile("preview", "veryfast", 26)
MASTER = EncodeProfile("master", "medium", 18)


def run(binary: str, args: list[str], timeout: float = 3600) -> str:
    cmd = [binary, "-hide_banner", "-nostdin", "-y", "-loglevel", "error", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise FFmpegError(f"ffmpeg failed ({proc.returncode}):\n{tail}")
    return proc.stderr


def probe_duration(binary: str, path: Path) -> float:
    proc = subprocess.run([binary, "-hide_banner", "-nostdin", "-i", str(path)],
                          capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not m:
        raise FFmpegError(f"Could not read duration of {path}")
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def probe_video_size(binary: str, path: Path) -> tuple[int, int]:
    proc = subprocess.run([binary, "-hide_banner", "-nostdin", "-i", str(path)],
                          capture_output=True, text=True)
    m = re.search(r"Video:.*?(\d{3,5})x(\d{3,5})", proc.stderr)
    if not m:
        raise FFmpegError(f"No video stream in {path}")
    return int(m.group(1)), int(m.group(2))


def encode_stills(binary: str, frames: list[tuple[Path, float]], out: Path,
                  profile: EncodeProfile, *, fade_in: bool, fade_out: bool,
                  fade_s: float = 0.3) -> float:
    """Encode a list of (png, seconds) into an H.264 segment. Returns exact duration."""
    total = sum(d for _, d in frames)
    lst = out.with_suffix(".ffconcat")
    lines = ["ffconcat version 1.0"]
    for png, dur in frames:
        lines += [f"file '{png.resolve()}'", f"duration {dur:.6f}"]
    lines.append(f"file '{frames[-1][0].resolve()}'")
    lst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    vf = [f"fps={profile.fps}", "format=yuv420p"]
    if fade_in and total > 2 * fade_s:
        vf.append(f"fade=t=in:st=0:d={fade_s}")
    if fade_out and total > 2 * fade_s:
        vf.append(f"fade=t=out:st={total - fade_s:.3f}:d={fade_s}")
    tmp = out.with_suffix(".part.mp4")
    run(binary, ["-f", "concat", "-safe", "0", "-i", str(lst), "-vf", ",".join(vf),
                 "-c:v", "libx264", "-preset", profile.preset, "-crf", str(profile.crf),
                 "-r", str(profile.fps), "-t", f"{total:.6f}", "-an", str(tmp)])
    tmp.replace(out)
    lst.unlink(missing_ok=True)
    return total


def encode_footage(binary: str, src: Path, out: Path, duration: float, size: tuple[int, int],
                   profile: EncodeProfile) -> None:
    w, h = size
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
          f"fps={profile.fps},format=yuv420p")
    tmp = out.with_suffix(".part.mp4")
    run(binary, ["-stream_loop", "-1", "-i", str(src), "-t", f"{duration:.6f}", "-vf", vf,
                 "-c:v", "libx264", "-preset", profile.preset, "-crf", str(profile.crf),
                 "-r", str(profile.fps), "-an", str(tmp)])
    tmp.replace(out)


def concat_segments(binary: str, segments: list[Path], out: Path) -> None:
    lst = out.with_suffix(".segments.ffconcat")
    lst.write_text("ffconcat version 1.0\n" + "".join(f"file '{s.resolve()}'\n"
                                                       for s in segments), encoding="utf-8")
    run(binary, ["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])
    lst.unlink(missing_ok=True)


# Original pad: Am - F - C - G, one chord every 8 s with triangular crossfades, slow tremolo.
CHORDS = [(110.0, 130.81, 164.81), (87.31, 110.0, 130.81), (130.81, 164.81, 196.0),
          (98.0, 123.47, 146.83)]
CHORD_S = 8.0


def music_bed_expression() -> str:
    p = f"mod(t/{CHORD_S},{len(CHORDS)})"
    terms = []
    for k, chord in enumerate(CHORDS):
        w = f"max(0,1-abs({p}-{k}))" + (f"+max(0,1-abs({p}-{len(CHORDS)}))" if k == 0 else "")
        voices = "+".join(f"{amp}*sin(2*PI*{f}*t)"
                          for f, amp in zip(chord, (0.05, 0.035, 0.025), strict=True))
        shimmer = f"0.008*sin(2*PI*{chord[2] * 2}*t)"
        terms.append(f"({w})*({voices}+{shimmer})")
    return "(" + "+".join(terms) + ")*(0.75+0.25*sin(2*PI*0.07*t))"


def make_music_bed(binary: str, out: Path, duration: float) -> None:
    """Original ambient bed synthesised from sine waves (no third-party music)."""
    fade_out_start = max(0.0, duration - 3)
    run(binary, ["-f", "lavfi", "-i",
                 # commas inside the expression must be escaped in a filter description
                 f"aevalsrc={music_bed_expression().replace(',', chr(92) + ',')}"
                 f":s=48000:d={duration:.3f}",
                 "-af", f"lowpass=f=1400,aecho=0.6:0.5:90|180:0.25|0.15,volume=1.8,"
                        f"afade=t=in:d=3,afade=t=out:st={fade_out_start:.3f}:d=3",
                 "-ac", "2", str(out)])


def prepare_music(binary: str, src: Path, out: Path, duration: float) -> None:
    """Licensed user track -> looped/trimmed 48 kHz stereo bed with fades."""
    fade_out_start = max(0.0, duration - 3)
    run(binary, ["-stream_loop", "-1", "-i", str(src), "-t", f"{duration:.3f}",
                 "-af", f"aresample=48000,afade=t=in:d=2,"
                        f"afade=t=out:st={fade_out_start:.3f}:d=3",
                 "-ac", "2", str(out)])


def music_for(binary: str, ws_audio: Path, manifest, ws_root: Path, duration: float,
              name: str = "music_bed.wav") -> tuple[Path, str]:
    """Pick the music bed: a cleared licensed track ('music-track') or the generated pad.

    Returns (wav path, source) where source is 'licensed:<id>' or 'generated'."""
    from studio.fsutil import sha256_text
    from studio.models import LicenseClearance

    rec = manifest.get("music-track") if manifest else None
    if rec and rec.clearance == LicenseClearance.CLEARED:
        src = ws_root / rec.path
        key = sha256_text(rec.sha256 or str(src), f"{duration:.2f}")[:12]
        out = ws_audio / f"music_track_{key}.wav"
        if not out.exists():
            prepare_music(binary, src, out, duration)
        return out, f"licensed:{rec.id}"
    out = ws_audio / name
    stamp = out.with_suffix(".expr")
    expr = music_bed_expression()
    if (not out.exists() or probe_duration(binary, out) + 0.05 < duration
            or not stamp.exists() or stamp.read_text() != expr):
        make_music_bed(binary, out, duration)
        stamp.write_text(expr)
    return out, "generated"


def mux_with_ducking(binary: str, video: Path, narration: Path, music: Path | None, out: Path,
                     duration: float, profile: EncodeProfile, music_volume: float = 0.35) -> None:
    """Narration has priority: the music bed is side-chain compressed under the voice."""
    args = ["-i", str(video), "-i", str(narration)]
    if music:
        args += ["-i", str(music)]
        fc = ("[1:a]aresample=48000,aformat=channel_layouts=stereo,apad,asplit=2[n1][n2];"
              f"[2:a]aresample=48000,volume={music_volume}[m];"
              "[m][n2]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[duck];"
              "[n1][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]")
    else:
        fc = "[1:a]aresample=48000,aformat=channel_layouts=stereo,apad[a]"
    tmp = out.with_suffix(".part.mp4")
    run(binary, [*args, "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                 "-c:a", "aac", "-b:a", profile.audio_bitrate, "-t", f"{duration:.6f}",
                 "-movflags", "+faststart", str(tmp)])
    tmp.replace(out)


def to_wav_22k_mono(binary: str, src: Path, out: Path) -> None:
    run(binary, ["-i", str(src), "-ac", "1", "-ar", "22050", "-sample_fmt", "s16", str(out)])
