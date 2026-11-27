"""Crop context for a regional edit and put only the painted pixels back."""
from __future__ import annotations

import io
from typing import Annotated

from PIL import Image, ImageDraw
from pydantic import BaseModel, Field, ValidationError

Unit = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class BrushStroke(BaseModel):
    size: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)]
    points: list[tuple[Unit, Unit]] = Field(min_length=1, max_length=12000)


class EditMask(BaseModel):
    source_id: str = Field(pattern=r"^\d{3,7}$")
    strokes: list[BrushStroke] = Field(min_length=1, max_length=256)


def normalize_mask(raw: dict) -> dict:
    try:
        mask = EditMask.model_validate(raw)
    except ValidationError as exc:
        raise ValueError("请在一张图片上涂出要修改的位置，再提交局部改图") from exc
    if sum(len(s.points) for s in mask.strokes) > 12000:
        raise ValueError("蒙版笔迹太多，请简化选区")
    return mask.model_dump()


def source_image(store, rid: str) -> bytes:
    found = store.media_path(rid) if isinstance(rid, str) else None
    if not found or found[0] != "image":
        raise ValueError(f"图片作品 #{rid} 不存在或已移除，请重新选择")
    try:
        return found[1].read_bytes()
    except FileNotFoundError as exc:
        raise ValueError(f"图片作品 #{rid} 已移除，请重新选择") from exc


class MaskedEdit:
    def __init__(self, source: bytes, mask: dict):
        with Image.open(io.BytesIO(source)) as original:
            self.original = original.convert("RGBA" if "A" in original.getbands() or "transparency" in original.info else "RGB")
        w, h = self.original.size
        self.mask = Image.new("L", (w, h))
        draw = ImageDraw.Draw(self.mask)
        for stroke in mask["strokes"]:
            diameter = max(1, round(stroke["size"] * min(w, h)))
            radius = (diameter - 1) / 2
            points = [(round(x * (w - 1)), round(y * (h - 1))) for x, y in stroke["points"]]
            if len(points) > 1:
                draw.line(points, fill=255, width=diameter, joint="curve")
            if diameter == 1:
                draw.point(points, fill=255)
                continue
            for x, y in points:
                draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
        x0, y0, x1, y1 = self.mask.getbbox()
        pad = max(24, round(max(x1 - x0, y1 - y0) * 0.3))
        self.box = (max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad))
        self.crop = self.original.crop(self.box)

    def reference(self) -> bytes:
        buffer = io.BytesIO()
        self.crop.save(buffer, format="PNG")
        return buffer.getvalue()

    def composite(self, generated) -> Image.Image:
        patch = generated.convert(self.original.mode).resize(self.crop.size, Image.Resampling.LANCZOS)
        result = self.original.copy()
        result.paste(patch, self.box, self.mask.crop(self.box))
        return result
