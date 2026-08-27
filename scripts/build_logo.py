#!/usr/bin/env python3
"""omnireach logomark — 生成全套 logo 资产。

构图：一个环（omni，全域覆盖）+ 中心实心圆（单一 CLI 入口）+ 环上四个等分节点（触达的源）。
刻意不画中心到节点的射线：实测那会让图形读作车轮，且 16px 下糊成一团。

所有几何用极坐标精确计算，输出 SVG（矢量，任意尺寸锐利）。
"""
import math
from pathlib import Path

C = 50.0          # 画布中心
R_RING = 32.0     # 环半径
R_NODE = 8.0      # 节点半径（最外沿 = R_RING + R_NODE = 40，即画布 80%，四周留 10% 呼吸）
R_HUB = 11.0      # 中心圆半径
STROKE = 4.5      # 环线宽
N = 4             # 节点数

CORAL = "#FF6B5A"
BLACK = "#16161c"
WHITE = "#fafafa"


def polar(r: float, deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    return C + r * math.cos(a), C + r * math.sin(a)


def logomark(color: str) -> str:
    angles = [-90 + i * (360 / N) for i in range(N)]
    nodes = "\n".join(
        f'    <circle cx="{polar(R_RING, a)[0]:.1f}" cy="{polar(R_RING, a)[1]:.1f}" r="{R_NODE}"/>'
        for a in angles
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
        'width="100" height="100" role="img" aria-label="omnireach">\n'
        f'  <circle cx="{C}" cy="{C}" r="{R_RING}" fill="none" '
        f'stroke="{color}" stroke-width="{STROKE}"/>\n'
        f'  <g fill="{color}">\n'
        f'    <circle cx="{C}" cy="{C}" r="{R_HUB}"/>\n'
        f"{nodes}\n"
        "  </g>\n"
        "</svg>\n"
    )


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "docs" / "assets"
    out.mkdir(exist_ok=True)
    for name, color in [("logo.svg", CORAL), ("logo-black.svg", BLACK), ("logo-white.svg", WHITE)]:
        p = out / name
        p.write_text(logomark(color))
        print(f"  {name:<18} {p.stat().st_size} bytes")
