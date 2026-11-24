"""Syz visual conventions (BUILD_SPEC §0.6). Nunito Sans is bundled (SIL Open Font License)."""
from pathlib import Path

from matplotlib import font_manager

FONT = "Nunito Sans"
MINT, BLUEBERRY, MULBERRY = "#3BAF90", "#4B5F80", "#AC5D85"
ORANGE, AMBER, NAVY = "#FF6C0E", "#FFA400", "#202945"
GREY = "#B8BFCC"
RS_RISING, RS_FALLING = "#2F6FDE", "#D8343F"     # relative-strength line: blue when its 200-day average rises, red when it falls (24 Nov 2026)
VERDICT_COLOUR = {"Bullish": MINT, "Neutral+": BLUEBERRY, "Neutral": BLUEBERRY, "Neutral-": BLUEBERRY,
                  "Bearish_LM": MULBERRY, "Bearish": MULBERRY}
VERDICT_GLYPH = {"Bullish": "▲", "Neutral+": "◆", "Neutral": "◆", "Neutral-": "◆", "Bearish_LM": "▼", "Bearish": "▼"}
VERDICT_LABEL = {"Bullish": "BULLISH", "Neutral+": "NEUTRAL – POSITIVE TILT", "Neutral": "NEUTRAL",
                 "Neutral-": "NEUTRAL – NEGATIVE TILT", "Bearish_LM": "BEARISH – LOSING MOMENTUM", "Bearish": "BEARISH"}
SOURCE_LINE = "Sources : Syz Research, Bloomberg"

_FONT_DIR = Path(__file__).parent / "fonts"


def register_fonts() -> str:
    """Register the bundled Nunito Sans files; returns the family name to use."""
    files = sorted(_FONT_DIR.glob("NunitoSans-*.ttf"))
    for f in files:
        font_manager.fontManager.addfont(str(f))
    return FONT if files else "DejaVu Sans"


# ── Verdict badge: the only badge allowed on charts (reference: charts/assets/verdict_badges_reference.pptx,
#    received 19 Nov 2026). Three badges only – the tilt and losing-momentum shades map onto them.
BADGE_FAMILY = {"Bullish": "Bullish", "Neutral+": "Neutral", "Neutral": "Neutral", "Neutral-": "Neutral",
                "Bearish_LM": "Bearish", "Bearish": "Bearish"}
BADGE_SPEC = {  # fill, glyph, label – exactly as in the reference file
    "Bullish": (MINT, "▲", "BULLISH"), "Neutral": (BLUEBERRY, "◆", "NEUTRAL"), "Bearish": (MULBERRY, "▼", "BEARISH")}
BADGE_W, BADGE_H = 1.18, 0.34          # inches (1,078,992 × 310,896 EMU)
BADGE_RADIUS = 0.2353 * BADGE_H        # roundRect adj 23,529
BADGE_PT, BADGE_TRACK_PT = 11, 1.5     # white bold capitals, letter spacing 150 (1.5 pt)


def draw_verdict_badge(fig, verdict: str, x: float, y: float) -> bool:
    """Draw the reference badge with its bottom-left corner at (x, y) inches. False when the verdict has no badge."""
    from matplotlib.patches import FancyBboxPatch
    fam = BADGE_FAMILY.get(verdict)
    if fam is None:
        return False
    fill, glyph, label = BADGE_SPEC[fam]
    tr = fig.dpi_scale_trans
    fig.add_artist(FancyBboxPatch((x, y), BADGE_W, BADGE_H, boxstyle=f"round,pad=0,rounding_size={BADGE_RADIUS:.4f}",
                                  fc=fill, ec=fill, lw=1.0, transform=tr, zorder=10))
    cy = y + BADGE_H / 2
    fig.text(x + 0.09 + 0.13, cy, glyph, transform=tr, ha="center", va="center", color="white", fontsize=BADGE_PT,
             fontweight="bold", family=["DejaVu Sans"], zorder=11)
    rend = fig.canvas.get_renderer()
    box_w = 0.82                       # reference label box (749,808 EMU), from 0.32 in
    size, track = BADGE_PT, BADGE_TRACK_PT

    def widths(sz):
        out = []
        for ch in label:
            t = fig.text(0, 0, ch, fontsize=sz, fontweight="bold")
            out.append(t.get_window_extent(rend).width / fig.dpi)
            t.remove()
        return out

    w = widths(size)
    while sum(w) + track / 72 * (len(label) - 1) > box_w - 0.02:      # tighten tracking first, then the size
        if track > 0.6:
            track -= 0.1
        else:
            size -= 0.25
            w = widths(size)
    cx = x + 0.32
    for ch, wc in zip(label, w):       # letter by letter: matplotlib has no tracking
        fig.text(cx, cy, ch, transform=tr, ha="left", va="center", color="white", fontsize=size,
                 fontweight="bold", zorder=11)
        cx += wc + track / 72
    return True
