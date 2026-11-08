"""Syz visual conventions (BUILD_SPEC §0.6). Nunito Sans is bundled (SIL Open Font License)."""
from pathlib import Path

from matplotlib import font_manager

FONT = "Nunito Sans"
MINT, BLUEBERRY, MULBERRY = "#3BAF90", "#4B5F80", "#AC5D85"
ORANGE, AMBER, NAVY = "#FF6C0E", "#FFA400", "#202945"
GREY = "#B8BFCC"
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
