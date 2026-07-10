#!/usr/bin/env python3
"""Render Xiaohongshu launch cards from verified benchmark and demo assets."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "docs" / "assets"
BENCHMARK = ROOT / "docs" / "benchmarks" / "read-path-v0.12.json"

WIDTH = 1080
HEIGHT = 1440
MARGIN = 72
BACKGROUND = "#141414"
PANEL = "#202020"
INK = "#F4F1E8"
MUTED = "#AAA79F"
GREEN = "#53D769"
RED = "#FF6B5E"
YELLOW = "#F3C74F"
CYAN = "#58C7D8"

ZH_FONT = Path("/System/Library/Fonts/STHeiti Medium.ttc")
MONO_FONT = Path("/System/Library/Fonts/SFNSMono.ttf")


def font(size: int, *, mono: bool = False) -> ImageFont.FreeTypeFont:
    path = MONO_FONT if mono else ZH_FONT
    return ImageFont.truetype(str(path), size=size)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    return image, ImageDraw.Draw(image)


def label(draw: ImageDraw.ImageDraw, text: str, y: int) -> None:
    draw.text((MARGIN, y), text, font=font(28, mono=True), fill=GREEN)
    draw.line((MARGIN, y + 46, WIDTH - MARGIN, y + 46), fill="#343434", width=2)


def footer(draw: ImageDraw.ImageDraw, text: str) -> None:
    draw.line(
        (MARGIN, HEIGHT - 120, WIDTH - MARGIN, HEIGHT - 120),
        fill="#343434",
        width=2,
    )
    draw.text((MARGIN, HEIGHT - 88), text, font=font(26), fill=MUTED)


def rounded_panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    fill: str = PANEL,
    outline: str | None = None,
) -> None:
    draw.rounded_rectangle(box, radius=8, fill=fill, outline=outline, width=3)


def fit_image(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    target_width = box[2] - box[0]
    target_height = box[3] - box[1]
    ratio = min(target_width / image.width, target_height / image.height)
    return image.resize(
        (round(image.width * ratio), round(image.height * ratio)),
        Image.Resampling.LANCZOS,
    )


def benchmark_values() -> dict[str, float]:
    payload = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    results = payload["results"]
    return {
        "mcp_cold": results["omnireach_mcp_cold"]["median_ms"] / 1000,
        "browser_cold": results["playwright_chrome_cold"]["median_ms"] / 1000,
        "cold_ratio": (
            results["playwright_chrome_cold"]["median_ms"]
            / results["omnireach_mcp_cold"]["median_ms"]
        ),
    }


def render_cover(values: dict[str, float]) -> None:
    image, draw = canvas()
    label(draw, "OMNIREACH / V0.12", 64)
    draw.text((MARGIN, 170), "Agent 读网页", font=font(88), fill=INK)
    draw.text((MARGIN, 286), "不必先开浏览器", font=font(88), fill=INK)
    draw.text(
        (MARGIN, 425),
        "先 search / fetch，再决定要不要 Playwright",
        font=font(34),
        fill=MUTED,
    )

    rounded_panel(draw, (MARGIN, 540, WIDTH - MARGIN, 1010))
    draw.text((112, 590), "同一份 RFC 9110", font=font(34), fill=YELLOW)
    draw.text((112, 658), "5 次冷启动中位数", font=font(26), fill=MUTED)

    draw.text((112, 760), "omnireach MCP", font=font(34), fill=INK)
    draw.text(
        (WIDTH - 332, 742),
        f"{values['mcp_cold']:.2f}s",
        font=font(56, mono=True),
        fill=GREEN,
    )
    draw.line((112, 838, WIDTH - 112, 838), fill="#3A3A3A", width=2)
    draw.text((112, 880), "Playwright + Chrome", font=font(34), fill=INK)
    draw.text(
        (WIDTH - 332, 862),
        f"{values['browser_cold']:.2f}s",
        font=font(56, mono=True),
        fill=RED,
    )

    draw.text(
        (MARGIN, 1075),
        f"Playwright 用时 {values['cold_ratio']:.1f}x",
        font=font(52),
        fill=YELLOW,
    )
    draw.text((MARGIN, 1155), "脚本、环境、每个样本全部公开", font=font(30), fill=MUTED)
    footer(draw, "MIT 开源 · github.com/Daily-AC/omnireach")
    image.save(ASSETS / "launch-xhs-cover.png", optimize=True)


def demo_frame() -> Image.Image:
    gif = Image.open(ASSETS / "demo-fast-path.gif")
    gif.seek(min(400, gif.n_frames - 1))
    return gif.convert("RGB")


def render_demo() -> None:
    frame = demo_frame()
    frame.save(ASSETS / "demo-fast-path.png", optimize=True)

    image, draw = canvas()
    label(draw, "REAL LOGGED-IN RUN", 64)
    draw.text((MARGIN, 166), "登录态照用", font=font(82), fill=INK)
    draw.text((MARGIN, 274), "可见窗口不弹", font=font(82), fill=GREEN)
    draw.text(
        (MARGIN, 398),
        "真实 MCP fetch + 小红书搜索",
        font=font(34),
        fill=MUTED,
    )

    box = (MARGIN, 500, WIDTH - MARGIN, 1080)
    rounded_panel(draw, box, fill="#1C1C24", outline="#3D3D4B")
    fitted = fit_image(frame, (96, 532, WIDTH - 96, 1048))
    x = (WIDTH - fitted.width) // 2
    y = 532 + (516 - fitted.height) // 2
    image.paste(fitted, (x, y))

    draw.text((MARGIN, 1135), "Chrome windows", font=font(30, mono=True), fill=MUTED)
    draw.text((MARGIN, 1192), "1  ->  1", font=font(64, mono=True), fill=GREEN)
    footer(draw, "后台临时 tab · 用完释放 · 不复制账号密码")
    image.save(ASSETS / "launch-xhs-demo.png", optimize=True)


def render_routing() -> None:
    image, draw = canvas()
    label(draw, "TWO READ PATHS", 64)
    draw.text((MARGIN, 166), "只读任务", font=font(82), fill=INK)
    draw.text((MARGIN, 274), "分两条路", font=font(82), fill=CYAN)

    rounded_panel(draw, (MARGIN, 430, WIDTH - MARGIN, 760), outline=GREEN)
    draw.text((112, 475), "普通网页", font=font(44), fill=GREEN)
    draw.text((112, 552), "HTTP  ->  clean Markdown", font=font(37, mono=True), fill=INK)
    draw.text((112, 632), "不启动 Chrome", font=font(34), fill=MUTED)

    rounded_panel(draw, (MARGIN, 810, WIDTH - MARGIN, 1140), outline=CYAN)
    draw.text((112, 855), "登录墙来源", font=font(44), fill=CYAN)
    draw.text((112, 932), "existing Chrome  ->  hidden tab", font=font(30, mono=True), fill=INK)
    draw.text((112, 1012), "继承登录态，用完释放", font=font(34), fill=MUTED)

    draw.text((MARGIN, 1200), "点击 / 表单 / 截图", font=font(32), fill=MUTED)
    draw.text((MARGIN, 1254), "继续用 Playwright", font=font(46), fill=YELLOW)
    footer(draw, "omnireach 不是浏览器自动化的全量替代")
    image.save(ASSETS / "launch-xhs-routing.png", optimize=True)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    values = benchmark_values()
    render_cover(values)
    render_demo()
    render_routing()
    print("rendered launch-xhs-cover.png, launch-xhs-demo.png, launch-xhs-routing.png")


if __name__ == "__main__":
    main()
