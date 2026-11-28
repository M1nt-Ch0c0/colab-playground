"""MiniMax-H3 source clip validation and reference roles."""
from __future__ import annotations

import re
from pathlib import Path

from ..media import video_info


VIDEO_TASKS = {
    "edit": (
        "video editing", "The target video is an edited version of <Video 1>. "
        "Retain its subjects, timing and camera work except for the requested changes.",
    ),
    "continue": (
        "video continuation", "Generate the next segment starting where <Video 1> ends, "
        "carrying its action and camera motion forward.",
    ),
    "motion": (
        "reference generation", "Follow the blocking, timing and camera movement of <Video 1>. "
        "Use <Picture 1> for the character's face, costume and materials.",
    ),
}


def reference_prompt(prompt: str, task: str, image_count: int = 0) -> str:
    label, role = VIDEO_TASKS[task]
    # Keep the official six-section structure for rewritten or hand-authored prompts.
    summary = re.search(r"(?im)^summary:\s*", prompt)
    if summary:
        rest = prompt[summary.end():]
        prefix = re.match(r"\[([^\]\n]*)\]", rest)
        labels = [s.strip() for s in prefix[1].split("+")] if prefix else []
        if label in labels and "<Video 1>" in prompt and (task != "motion" or "<Picture 1>" in prompt):
            return prompt
        extra = [s for s in labels if s and s not in (label, "video editing", "video continuation")]
        tag = " + ".join([label, *extra])
        return f"{prompt[:summary.end()]}[{tag}] {role} {rest[prefix.end() if prefix else 0:].lstrip()}"
    if image_count and task != "motion":
        pictures = ", ".join(f"<Picture {i}>" for i in range(1, image_count + 1))
        return f"[{label} + reference generation] {role} Use {pictures} as visual references for the request.\n{prompt}"
    return f"[{label}] {role}\n{prompt}"


def probe_reference_video(path: Path) -> float:
    duration = video_info(path)["media_duration_s"]
    if not 2 <= duration <= 15:
        raise ValueError(f"参考视频时长为 {duration:.2f} 秒，请截取 2–15 秒的片段")
    return duration
