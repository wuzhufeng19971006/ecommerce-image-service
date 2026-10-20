"""生成两张本地测试图，便于没有真实素材时体验上传流程。"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "samples"
OUT.mkdir(parents=True, exist_ok=True)


def font(size: int):
    for candidate in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                pass
    return ImageFont.load_default()


def garment() -> None:
    image = Image.new("RGB", (900, 1200), "#f4efe5")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((80, 70, 820, 1130), radius=30, fill="#fffdf8")
    # simple trench silhouette
    draw.polygon(
        [
            (370, 280), (530, 280), (610, 360), (700, 980), (200, 980),
            (290, 360),
        ],
        fill="#d8c1a4",
        outline="#a78b6c",
    )
    draw.line([(450, 300), (450, 970)], fill="#a78b6c", width=4)
    draw.line([(330, 430), (370, 760)], fill="#b49a7c", width=3)
    draw.line([(570, 430), (530, 760)], fill="#b49a7c", width=3)
    for y in (600, 660, 720):
        draw.ellipse((440, y, 462, y + 22), outline="#8e7358", width=3)
    draw.line([(270, 760), (630, 760)], fill="#8e7358", width=6)
    draw.text((120, 1050), "DEMO GARMENT / 衣图测试图", font=font(26), fill="#8b785f")
    image.save(OUT / "garment.png")


def garment_detail() -> None:
    source = OUT / "garment.png"
    if not source.exists():
        garment()
    with Image.open(source) as image:
        cropped = image.crop((250, 320, 710, 860)).resize((800, 800), Image.Resampling.LANCZOS)
    cropped.save(OUT / "garment-detail.png")


def model() -> None:
    image = Image.new("RGB", (900, 1200), "#e7ded1")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((60, 50, 840, 1150), radius=30, fill="#ede7dd")
    # abstract model silhouette
    draw.ellipse((400, 120, 500, 230), fill="#c7a98d")
    draw.rounded_rectangle((405, 215, 495, 250), radius=10, fill="#b7987b")
    draw.polygon(
        [(360, 260), (540, 260), (610, 680), (570, 1080), (330, 1080), (290, 680)],
        fill="#b6a08b",
    )
    draw.line([(450, 270), (450, 1070)], fill="#a28b76", width=3)
    draw.text((110, 1090), "DEMO MODEL / 衣图测试图", font=font(24), fill="#8b785f")
    image.save(OUT / "model.png")


if __name__ == "__main__":
    garment()
    garment_detail()
    model()
    print(
        f"已生成测试图：{OUT / 'garment.png'}、{OUT / 'garment-detail.png'}、"
        f"{OUT / 'model.png'}"
    )
