"""
generate_screenshots.py
Generates the demo_before.png and demo_after.png used by Docu-Sync demos and eval.py.

The two images show a realistic task-management dashboard with deliberate UI changes
between the before and after states — ideal for demonstrating change detection:

  BEFORE → AFTER changes:
  • Primary button: blue (#2563EB) → green (#16A34A)
  • Button label:   "Submit Report" → "Generate Report"
  • Sidebar:        4 nav items → 5 items ("Analytics" added with "New" badge)
  • New green alert banner added at top of content area
  • Welcome text updated with emoji
  • Sidebar background darkened slightly

Usage:
    cd demo/
    pip install Pillow
    python generate_screenshots.py
"""

import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 800

BEFORE = dict(
    sidebar_bg="#1E1E2E", sidebar_text="#A0A0B0",
    sidebar_active_bg="#3B3B5C",
    btn_primary="#2563EB",
    stat1="#2563EB", stat2="#7C3AED", stat3="#059669",
    nav_count=4,
    btn_label="Submit Report",
    welcome="Welcome back, Anshita",
    alert=None,
    tag_new=None,
)
AFTER = dict(
    sidebar_bg="#0F172A", sidebar_text="#94A3B8",
    sidebar_active_bg="#1D4ED8",
    btn_primary="#16A34A",
    stat1="#1D4ED8", stat2="#7C3AED", stat3="#16A34A",
    nav_count=5,
    btn_label="Generate Report",
    welcome="Welcome back, Anshita 👋",
    alert="#16A34A",
    tag_new="#16A34A",
)


def _font(size):
    for name in ["DejaVuSans.ttf", "LiberationSans-Regular.ttf", "Arial.ttf"]:
        for base in [
            "/usr/share/fonts/truetype/dejavu",
            "/usr/share/fonts/truetype/liberation",
            "/usr/share/fonts",
        ]:
            path = os.path.join(base, name)
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _bold(size):
    for name in ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Arial Bold.ttf"]:
        for base in [
            "/usr/share/fonts/truetype/dejavu",
            "/usr/share/fonts/truetype/liberation",
            "/usr/share/fonts",
        ]:
            path = os.path.join(base, name)
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def make_screenshot(p):
    img = Image.new("RGB", (W, H), _rgb("#F8F9FA"))
    d   = ImageDraw.Draw(img)

    SIDEBAR_W = 220
    HEADER_H  = 60

    nav_items = (
        ["🏠  Overview", "✅  Tasks", "📁  Projects", "📊  Analytics", "⚙️  Settings"]
        if p["nav_count"] == 5 else
        ["🏠  Overview", "✅  Tasks", "📁  Projects", "⚙️  Settings"]
    )

    # ── Sidebar ────────────────────────────────────────────────────────────────
    d.rectangle([0, 0, SIDEBAR_W, H], fill=_rgb(p["sidebar_bg"]))

    d.rounded_rectangle([18, 14, 46, 42], radius=8, fill=_rgb(p["btn_primary"]))
    d.text((26, 18), "T", font=_bold(18), fill=(255, 255, 255))
    d.text((54, 20), "TaskFlow", font=_bold(16), fill=(255, 255, 255))

    for i, item in enumerate(nav_items):
        y = 80 + i * 48
        active = (i == 0)
        if active:
            d.rounded_rectangle([10, y - 2, SIDEBAR_W - 10, y + 34], radius=8,
                                  fill=_rgb(p["sidebar_active_bg"]))
        color = (255, 255, 255) if active else _rgb(p["sidebar_text"])
        d.text((22, y + 6), item, font=_font(14), fill=color)

        if p["tag_new"] and "Analytics" in item:
            bx = SIDEBAR_W - 52
            d.rounded_rectangle([bx, y + 8, bx + 38, y + 26], radius=6,
                                  fill=_rgb(p["tag_new"]))
            d.text((bx + 8, y + 10), "New", font=_font(11), fill=(255, 255, 255))

    av_y = H - 68
    d.ellipse([18, av_y, 46, av_y + 28], fill=_rgb(p["btn_primary"]))
    d.text((25, av_y + 5), "AB", font=_bold(11), fill=(255, 255, 255))
    d.text((54, av_y + 4), "Anshita B.", font=_bold(13), fill=(255, 255, 255))
    d.text((54, av_y + 20), "Admin", font=_font(11), fill=_rgb(p["sidebar_text"]))

    # ── Header ─────────────────────────────────────────────────────────────────
    d.rectangle([SIDEBAR_W, 0, W, HEADER_H], fill=(255, 255, 255))
    d.line([SIDEBAR_W, HEADER_H, W, HEADER_H], fill=_rgb("#E5E7EB"), width=1)
    d.text((SIDEBAR_W + 24, 18), "TaskFlow  —  Dashboard", font=_bold(17), fill=(15, 23, 42))

    sx = W - 280
    d.rounded_rectangle([sx, 14, W - 110, 46], radius=8, fill=(243, 244, 246),
                          outline=_rgb("#E5E7EB"))
    d.text((sx + 12, 21), "🔍  Search…", font=_font(13), fill=(156, 163, 175))
    d.ellipse([W - 92, 12, W - 60, 48], fill=_rgb(p["btn_primary"]))
    d.text((W - 84, 22), "AB", font=_bold(12), fill=(255, 255, 255))

    # ── Alert banner ───────────────────────────────────────────────────────────
    cy = HEADER_H + 8
    if p["alert"]:
        ac  = _rgb(p["alert"])
        alc = tuple(min(255, c + 170) for c in ac)
        d.rounded_rectangle([SIDEBAR_W + 20, cy + 4, W - 20, cy + 38], radius=8, fill=alc)
        d.text((SIDEBAR_W + 36, cy + 12),
               "✨  New Analytics dashboard is live — explore your insights!",
               font=_font(13), fill=ac)
        cy += 50

    # ── Welcome ────────────────────────────────────────────────────────────────
    d.text((SIDEBAR_W + 24, cy + 10), p["welcome"], font=_bold(22), fill=(15, 23, 42))
    d.text((SIDEBAR_W + 24, cy + 40), "Here's what's happening today.",
           font=_font(14), fill=(100, 116, 139))
    cy += 80

    # ── Stat cards ─────────────────────────────────────────────────────────────
    CARD_W = (W - SIDEBAR_W - 60) // 3
    for i, (col, label, val, sub) in enumerate([
        (p["stat1"], "Active Tasks", "24", "+3 this week"),
        (p["stat2"], "In Progress",  "8",  "2 due today"),
        (p["stat3"], "Completed",    "61", "+12 this month"),
    ]):
        cx = SIDEBAR_W + 20 + i * (CARD_W + 10)
        d.rounded_rectangle([cx, cy, cx + CARD_W, cy + 100], radius=12,
                              fill=(255, 255, 255), outline=_rgb("#E5E7EB"))
        ic = _rgb(col)
        il = tuple(min(255, c + 190) for c in ic)
        d.ellipse([cx + 16, cy + 16, cx + 48, cy + 48], fill=il)
        d.text((cx + 22, cy + 22), "●", font=_bold(18), fill=ic)
        d.text((cx + 60, cy + 18), val,   font=_bold(26), fill=(15, 23, 42))
        d.text((cx + 60, cy + 50), label, font=_font(13), fill=(100, 116, 139))
        d.text((cx + 16, cy + 72), sub,   font=_font(12), fill=ic)
    cy += 120

    # ── Task table ─────────────────────────────────────────────────────────────
    TW = W - SIDEBAR_W - 40
    d.rounded_rectangle([SIDEBAR_W + 20, cy, SIDEBAR_W + 20 + TW, cy + 260],
                          radius=12, fill=(255, 255, 255), outline=_rgb("#E5E7EB"))
    d.text((SIDEBAR_W + 36, cy + 16), "Recent Tasks", font=_bold(15), fill=(15, 23, 42))

    hy = cy + 48
    d.rectangle([SIDEBAR_W + 20, hy, SIDEBAR_W + 20 + TW, hy + 32], fill=(249, 250, 251))
    for lbl, xo in [("Task Name", 16), ("Status", 320), ("Priority", 460), ("Due", 580)]:
        d.text((SIDEBAR_W + 20 + xo, hy + 9), lbl, font=_bold(12), fill=(100, 116, 139))

    for i, (name, status, s_bg, s_fg, prio, p_bg, p_fg, due) in enumerate([
        ("Update user onboarding flow",  "In Progress", "#EFF6FF", "#2563EB", "High",   "#FEE2E2", "#DC2626", "Apr 20"),
        ("Fix navigation bar bug",       "Completed",   "#ECFDF5", "#059669", "Medium", "#FEF3C7", "#D97706", "Apr 18"),
        ("Design new dashboard widgets", "In Progress", "#EFF6FF", "#2563EB", "High",   "#FEE2E2", "#DC2626", "Apr 22"),
        ("Write API documentation",      "Pending",     "#F3F4F6", "#6B7280", "Low",    "#F3F4F6", "#6B7280", "Apr 25"),
    ]):
        ry = hy + 32 + i * 44
        if i % 2:
            d.rectangle([SIDEBAR_W + 21, ry, SIDEBAR_W + 20 + TW - 1, ry + 44],
                         fill=(250, 250, 252))
        d.text((SIDEBAR_W + 36, ry + 14), name, font=_font(13), fill=(15, 23, 42))
        px2 = SIDEBAR_W + 20 + 320
        d.rounded_rectangle([px2, ry + 12, px2 + 90, ry + 32], radius=6, fill=_rgb(s_bg))
        d.text((px2 + 8, ry + 15), status, font=_font(11), fill=_rgb(s_fg))
        px3 = SIDEBAR_W + 20 + 460
        d.rounded_rectangle([px3, ry + 12, px3 + 68, ry + 32], radius=6, fill=_rgb(p_bg))
        d.text((px3 + 8, ry + 15), prio, font=_font(11), fill=_rgb(p_fg))
        d.text((SIDEBAR_W + 20 + 580, ry + 14), due, font=_font(13), fill=(100, 116, 139))
    cy += 270

    # ── Primary button ─────────────────────────────────────────────────────────
    bx, by, BW, BH = SIDEBAR_W + 20, cy + 14, 180, 44
    d.rounded_rectangle([bx, by, bx + BW, by + BH], radius=10, fill=_rgb(p["btn_primary"]))
    lw = _bold(14).getlength(p["btn_label"])
    d.text((bx + (BW - lw) // 2, by + 13), p["btn_label"], font=_bold(14), fill=(255, 255, 255))

    sx2 = bx + BW + 12
    d.rounded_rectangle([sx2, by, sx2 + 130, by + BH], radius=10,
                          fill=(255, 255, 255), outline=_rgb("#E5E7EB"), width=1)
    d.text((sx2 + 30, by + 13), "Export CSV", font=_font(14), fill=(71, 85, 105))

    return img


if __name__ == "__main__":
    out = os.path.dirname(os.path.abspath(__file__))
    make_screenshot(BEFORE).save(os.path.join(out, "demo_before.png"))
    make_screenshot(AFTER).save(os.path.join(out, "demo_after.png"))
    print("✅  Saved demo_before.png  (blue 'Submit Report' button, 4 nav items)")
    print("✅  Saved demo_after.png   (green 'Generate Report' button, Analytics tab added)")
