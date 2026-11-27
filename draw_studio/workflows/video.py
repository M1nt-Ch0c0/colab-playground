"""Local FFmpeg helpers for the final video stitching step."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


TRANSITIONS = {"cut": "cut", "none": "cut", "fade": "fade"}


def normalize_transition(value: str) -> str:
    if not isinstance(value, str) or value not in TRANSITIONS:
        raise ValueError("转场必须是 cut（硬切）或 fade（淡入淡出）")
    return TRANSITIONS[value]


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _probe_video_info(path: Path) -> tuple[float, bool]:
    """Return (duration_seconds, has_audio) using ffprobe (or safe defaults)."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 5.0, True
    try:
        proc = subprocess.run(
            [
                ffprobe, "-v", "error",
                "-show_entries", "format=duration:stream=codec_type",
                "-of", "json", str(path),
            ],
            capture_output=True, text=True, timeout=20,
        )
        if proc.returncode != 0:
            return 5.0, True
        info = json.loads(proc.stdout or "{}")
        dur = float((info.get("format") or {}).get("duration") or 5.0)
        streams = info.get("streams") or []
        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        return max(0.2, dur), has_audio
    except Exception:
        return 5.0, True


def stitch_videos(
    clip_paths: list[Path],
    out_mp4: Path,
    out_thumb: Path | None = None,
    *,
    target_width: int = 1280,
    target_height: int = 768,
    fps: int = 24,
    transition: str = "fade",
    fade_s: float = 0.35,
) -> dict[str, Any]:
    """Normalize and stitch MP4 clips via FFmpeg (supports hard cut or smooth xfade + acrossfade)."""
    if not clip_paths:
        raise ValueError("没有可拼接的视频片段")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("当前环境未安装 ffmpeg，无法合成长视频（Docker 镜像已内置 ffmpeg）")

    w = max(256, int(target_width // 2 * 2))
    h = max(256, int(target_height // 2 * 2))
    fps = max(12, min(60, int(fps or 24)))
    trans = normalize_transition(transition)
    fade = max(0.1, min(1.5, float(fade_s or 0.35)))

    with tempfile.TemporaryDirectory(prefix="qp-stitch-") as tmp:
        tmp_dir = Path(tmp)
        norm_clips: list[tuple[Path, float]] = []
        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"fps={fps},format=yuv420p,setsar=1"
        )
        for idx, src in enumerate(clip_paths):
            if not src.exists():
                raise ValueError(f"视频片段不存在：{src.name}")
            dur, has_audio = _probe_video_info(src)
            norm = tmp_dir / f"norm_{idx:03d}.mp4"
            if has_audio:
                cmd = [
                    ffmpeg, "-y", "-i", str(src),
                    "-vf", vf,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                    "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
                    "-movflags", "+faststart", str(norm),
                ]
            else:
                cmd = [
                    ffmpeg, "-y", "-i", str(src),
                    "-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo",
                    "-shortest",
                    "-vf", vf,
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                    "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
                    "-movflags", "+faststart", str(norm),
                ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if proc.returncode != 0:
                raise RuntimeError(f"FFmpeg 标准化片段 #{idx + 1} 失败：{proc.stderr[-300:]}")
            ndur, _ = _probe_video_info(norm)
            norm_clips.append((norm, ndur))

        if len(norm_clips) == 1:
            shutil.copyfile(norm_clips[0][0], out_mp4)
            total_dur = norm_clips[0][1]
        elif trans == "cut" or any(d <= fade * 2.2 for _, d in norm_clips):
            lst = tmp_dir / "concat.txt"
            lst.write_text(
                "\n".join(f"file '{p.as_posix()}'" for p, _ in norm_clips) + "\n",
                encoding="utf-8",
            )
            cmd = [
                ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                "-c", "copy", "-movflags", "+faststart", str(out_mp4),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if proc.returncode != 0:
                raise RuntimeError(f"FFmpeg 拼接失败：{proc.stderr[-300:]}")
            total_dur = sum(d for _, d in norm_clips)
            trans = "cut"
        else:
            cmd = [ffmpeg, "-y"]
            for p, _ in norm_clips:
                cmd.extend(["-i", str(p)])
            v_filters: list[str] = []
            a_filters: list[str] = []
            prev_v = "0:v"
            prev_a = "0:a"
            acc_dur = norm_clips[0][1]
            for idx in range(1, len(norm_clips)):
                offset = max(0.05, acc_dur - fade)
                out_v = f"v{idx}"
                out_a = f"a{idx}"
                v_filters.append(
                    f"[{prev_v}][{idx}:v]xfade=transition=fade:duration={fade:.3f}:offset={offset:.3f}[{out_v}]"
                )
                a_filters.append(f"[{prev_a}][{idx}:a]acrossfade=d={fade:.3f}:c1=tri:c2=tri[{out_a}]")
                prev_v = out_v
                prev_a = out_a
                acc_dur = acc_dur + norm_clips[idx][1] - fade
            fc = ";".join(v_filters + a_filters)
            cmd.extend([
                "-filter_complex", fc,
                "-map", f"[{prev_v}]", "-map", f"[{prev_a}]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
                "-movflags", "+faststart", str(out_mp4),
            ])
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if proc.returncode != 0:
                raise RuntimeError(f"FFmpeg 淡入淡出合成失败：{proc.stderr[-300:]}")
            total_dur = acc_dur

        if out_thumb is not None:
            subprocess.run(
                [
                    ffmpeg, "-y", "-i", str(out_mp4),
                    "-vf", "thumbnail,scale=512:-1", "-frames:v", "1", "-q:v", "4",
                    str(out_thumb),
                ],
                capture_output=True, timeout=30,
            )

    final_dur, _ = _probe_video_info(out_mp4)
    return {
        "duration_s": round(final_dur or total_dur, 2),
        "clip_count": len(clip_paths),
        "width": w,
        "height": h,
        "fps": fps,
        "transition": trans,
    }
