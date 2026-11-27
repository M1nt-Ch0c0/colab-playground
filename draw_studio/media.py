"""Local media operations shared by the gallery and generation inputs."""
from __future__ import annotations

import io
import json
import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError


def video_info(path: Path) -> dict:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-protocol_whitelist", "file", "-f", "mov", "-select_streams", "V:0",
             "-show_entries", "stream=duration,width,height:stream_side_data=rotation:format=duration",
             "-of", "json", str(path)], capture_output=True, timeout=15, check=True,
        )
        info = json.loads(result.stdout)
        stream = info["streams"][0]
        seconds = float(stream.get("duration") or info["format"]["duration"])
        width, height = int(stream["width"]), int(stream["height"])
        if not math.isfinite(seconds) or seconds <= 0 or min(width, height) <= 0:
            raise ValueError
        if any(round(float(s.get("rotation", 0)) / 90) % 2 for s in stream.get("side_data_list", [])):
            width, height = height, width
        return {"media_duration_s": seconds, "width": width, "height": height}
    except FileNotFoundError as exc:
        raise ValueError("读取视频需要在服务端安装 FFmpeg") from exc
    except (subprocess.SubprocessError, ValueError, TypeError, KeyError, IndexError) as exc:
        raise ValueError("无法读取视频轨，请选择有效的 MP4") from exc


def _ffmpeg(source: Path, output: Path, inputs: list[str], options: list[str]) -> None:
    try:
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-protocol_whitelist", "file",
                        "-f", "mov", *inputs, "-i", str(source), "-map", "0:V:0", *options, str(output)],
                       capture_output=True, timeout=180, check=True)
        if not output.is_file() or not output.stat().st_size:
            raise ValueError("该时间点没有可读取的画面")
    except FileNotFoundError as exc:
        raise ValueError("处理视频需要在服务端安装 FFmpeg") from exc
    except subprocess.SubprocessError as exc:
        raise ValueError("FFmpeg 未能处理这段视频，请检查素材或缩短片段") from exc


def image_thumbnail(image: Image.Image, destination: Path) -> None:
    thumb = image.copy()
    thumb.thumbnail((480, 480), Image.Resampling.LANCZOS)
    thumb.convert("RGB").save(destination, quality=85)


def _video_thumbnail(source: Path, dest: Path) -> None:
    _ffmpeg(source, dest, [], ["-an", "-frames:v", "1", "-vf", "scale=480:480:force_original_aspect_ratio=decrease"])


def import_media(store, raw: bytes, kind: str, name: str) -> str:
    title = Path(name.replace("\\", "/")).name.strip()[:160] or ("导入视频" if kind == "video" else "导入图片")
    meta = {"prompt": title, "model": "导入素材", "media_operation": "import"}
    with tempfile.TemporaryDirectory() as folder:
        dest = Path(folder) / ("source.mp4" if kind == "video" else "source.png")
        thumb = Path(folder) / "thumb.jpg"
        if kind == "video":
            dest.write_bytes(raw)
            meta.update(video_info(dest))
            _video_thumbnail(dest, thumb)
        else:
            try:
                with Image.open(io.BytesIO(raw), formats=("PNG", "JPEG", "WEBP")) as img:
                    original = ImageOps.exif_transpose(img)
                    alpha = "A" in original.getbands() or "transparency" in original.info
                    image = original.convert("RGBA" if alpha else "RGB")
                    image.save(dest)
                    image_thumbnail(image, thumb)
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
                raise ValueError("请选择有效的 PNG、JPEG 或 WebP 图片") from exc
        return store.save(dest, kind, meta, thumb)


def image_crop(store, rid: str, source: Path, x: int, y: int, width: int, height: int) -> str:
    try:
        with Image.open(source) as original:
            image = ImageOps.exif_transpose(original)
            if min(x, y) < 0 or min(width, height) < 1 or x + width > image.width or y + height > image.height:
                raise ValueError("裁剪范围超出原图，请重新选择")
            crop = image.crop((x, y, x + width, y + height))
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("无法读取原图，请从作品库重新选择") from exc
    with tempfile.TemporaryDirectory() as folder:
        dest, thumb = Path(folder) / "crop.png", Path(folder) / "thumb.jpg"
        crop.save(dest)
        image_thumbnail(crop, thumb)
        meta = {"prompt": f"图片 #{rid} · 裁图 {width}×{height}", "model": "图片裁剪", "media_operation": "crop",
                "source_rounds": [rid], "source_crop": {"x": x, "y": y, "width": width, "height": height}}
        return store.save(dest, "image", meta, thumb)


def video_frame(store, rid: str, source: Path, position: str, time_s: float) -> str:
    duration = video_info(source)["media_duration_s"]
    if not math.isfinite(time_s) or not 0 <= time_s <= duration + 0.001:
        raise ValueError("取帧时间超出片长")
    with tempfile.TemporaryDirectory() as folder:
        frame = Path(folder) / "frame.png"
        if position == "first":
            time_s = 0.0
            _ffmpeg(source, frame, [], ["-an", "-frames:v", "1"])
        elif position == "last" or time_s >= duration:
            time_s = duration
            _ffmpeg(source, frame, ["-ss", str(max(0, duration - 1)), "-noaccurate_seek"],
                    ["-an", "-fps_mode", "passthrough", "-update", "1"])
        else:
            # Decode from the preceding keyframe. Its timestamps are relative to the seek point.
            # The last frame at or before that point is the frame currently displayed, also for VFR.
            _ffmpeg(source, frame, ["-ss", str(time_s), "-noaccurate_seek"],
                    ["-an", "-vf", "trim=end_pts=1", "-fps_mode", "passthrough", "-update", "1"])
        thumb = Path(folder) / "thumb.jpg"
        with Image.open(frame) as image:
            image_thumbnail(image, thumb)
        label = {"first": "首帧", "last": "尾帧"}.get(position, f"{time_s:g} 秒")
        return store.save(frame, "image", {"prompt": f"视频 #{rid} · {label}", "model": "视频取帧",
                          "source_rounds": [rid], "media_operation": "frame", "source_time_s": time_s}, thumb)


def video_clip(store, rid: str, source: Path, start: float, end: float, mute: bool) -> str:
    duration = video_info(source)["media_duration_s"]
    if not all(math.isfinite(t) for t in (start, end)) or not 0 <= start < end <= duration + 0.001:
        raise ValueError("截取范围必须在原片内，结束时间要晚于开始时间")
    with tempfile.TemporaryDirectory() as folder:
        clip, thumb = Path(folder) / "clip.mp4", Path(folder) / "thumb.jpg"
        audio = ["-an"] if mute else ["-map", "0:a:0?", "-c:a", "aac"]
        _ffmpeg(source, clip, ["-ss", str(start)], ["-t", str(min(end, duration) - start), *audio, "-c:v", "libx264",
                "-preset", "veryfast", "-crf", "18", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart"])
        meta = {**video_info(clip), "prompt": f"视频 #{rid} · {start:g}–{end:g} 秒", "model": "视频裁段",
                "source_rounds": [rid], "media_operation": "clip", "source_range_s": [start, end], "muted": mute}
        _video_thumbnail(clip, thumb)
        return store.save(clip, "video", meta, thumb)
