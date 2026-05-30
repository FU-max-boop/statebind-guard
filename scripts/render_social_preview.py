#!/usr/bin/env python3
"""Render the StateBind Guard social preview image.

This is a maintainer utility, not a runtime dependency. The committed PNG keeps
link previews stable while the SVG remains easy to inspect.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "statebind_social_preview.png"


def load_font(size: int, *, mono: bool = False):
    try:
        from PIL import ImageFont
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SystemExit("Pillow is required to render the social preview.") from exc

    candidates = (
        ["/System/Library/Fonts/SFNSMono.ttf", "/System/Library/Fonts/Menlo.ttc"]
        if mono
        else ["/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/SFCompact.ttf"]
    )
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default(size=size)


def rounded(draw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def main() -> int:
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SystemExit("Pillow is required to render the social preview.") from exc

    image = Image.new("RGB", (1200, 630), "#10131a")
    draw = ImageDraw.Draw(image)
    rounded(draw, (44, 44, 1156, 586), 26, "#f8fafc")
    rounded(draw, (44, 44, 1156, 176), 26, "#102033")
    draw.rectangle((44, 140, 1156, 186), fill="#102033")

    sans_18 = load_font(18)
    sans_22 = load_font(22)
    sans_25 = load_font(25)
    sans_32 = load_font(32)
    sans_34 = load_font(34)
    sans_50 = load_font(50)
    mono_20 = load_font(20, mono=True)
    mono_26 = load_font(26, mono=True)

    draw.text((92, 91), "StateBind Guard", fill="#e9fbf8", font=sans_34)
    draw.text((92, 138), "CI guard for executable coding-agent handoffs", fill="#a7f3d0", font=sans_18)
    draw.text((92, 220), "Make handoffs executable.", fill="#16181d", font=sans_50)
    draw.text(
        (92, 292),
        "Catch visible-but-unbound files, tests, PRs, SHAs, and artifacts",
        fill="#4b5563",
        font=sans_25,
    )
    draw.text(
        (92, 326),
        "before the next coding agent acts on the wrong object.",
        fill="#4b5563",
        font=sans_25,
    )

    cards = [
        ("!", "#fee2e2", "#b42318", "Visible is not bound", "same SHA, wrong role"),
        ("#", "#dcfce7", "#0e766e", "Role-bound handles", "test, file, PR, artifact"),
        (">", "#ffedd5", "#b35c00", "CLI + Action + SARIF", "30-second CI adoption"),
    ]
    x = 92
    for icon, icon_bg, icon_fg, title, body in cards:
        rounded(draw, (x, 388, x + 304, 500), 12, "#ffffff", "#d9dee7")
        rounded(draw, (x + 18, 406, x + 62, 450), 9, icon_bg)
        draw.text((x + 30, 413), icon, fill=icon_fg, font=mono_26)
        draw.text((x + 78, 413), title, fill="#16181d", font=sans_22)
        draw.text((x + 78, 451), body, fill="#5d6472", font=sans_18)
        x += 338

    draw.line((92, 532, 1108, 532), fill="#d9dee7", width=1)
    draw.text(
        (92, 556),
        'statebind init --goal "keep handoffs executable" --next-command "make test"',
        fill="#334155",
        font=mono_20,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUT)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
