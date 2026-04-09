"""OG image generation using Pillow — score cards, profile cards, task previews."""

import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Brand colors
BG_COLOR = (15, 23, 42)          # slate-900
ACCENT_COLOR = (99, 102, 241)    # indigo-500
TEXT_PRIMARY = (248, 250, 252)   # slate-50
TEXT_SECONDARY = (148, 163, 184) # slate-400
GOLD_COLOR = (251, 191, 36)      # amber-400
CARD_BG = (30, 41, 59)           # slate-800

OG_WIDTH = 1200
OG_HEIGHT = 630


def _get_draw_context():
    """Lazy import Pillow to avoid import errors if not installed."""
    from PIL import Image, ImageDraw, ImageFont
    return Image, ImageDraw, ImageFont


def _create_base_image():
    Image, ImageDraw, ImageFont = _get_draw_context()
    img = Image.new("RGB", (OG_WIDTH, OG_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    # Accent bar on left
    draw.rectangle([(0, 0), (8, OG_HEIGHT)], fill=ACCENT_COLOR)
    return img, draw, ImageFont


def _try_font(ImageFont, size: int):
    """Try to load a system font, fall back to default."""
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except Exception:
            return ImageFont.load_default()


def generate_score_card(
    candidate_name: str,
    task_title: str,
    domain: str,
    score: float,
    rank: int,
    total_submissions: int,
) -> bytes:
    """Generate a 1200x630 PNG score card image."""
    img, draw, ImageFont = _create_base_image()

    font_large = _try_font(ImageFont, 80)
    font_medium = _try_font(ImageFont, 36)
    font_small = _try_font(ImageFont, 28)
    font_tiny = _try_font(ImageFont, 22)

    # Score — large center display
    score_text = f"{int(score)} / 100"
    draw.text((80, 80), score_text, font=font_large, fill=GOLD_COLOR)

    # Candidate name
    draw.text((80, 200), candidate_name, font=font_medium, fill=TEXT_PRIMARY)

    # Task title (truncated)
    task_display = task_title[:55] + "..." if len(task_title) > 55 else task_title
    draw.text((80, 260), task_display, font=font_small, fill=TEXT_SECONDARY)

    # Domain badge
    draw.rectangle([(80, 310), (80 + len(domain) * 14 + 20, 350)], fill=ACCENT_COLOR)
    draw.text((90, 316), domain.upper(), font=font_tiny, fill=TEXT_PRIMARY)

    # Rank
    rank_text = f"#{rank} of {total_submissions} submissions"
    draw.text((80, 380), rank_text, font=font_small, fill=TEXT_PRIMARY)

    # Tagline
    draw.text((80, 450), "Verified by HireX", font=font_small, fill=ACCENT_COLOR)

    # HireX branding (bottom right)
    draw.text((OG_WIDTH - 200, OG_HEIGHT - 60), "HireX", font=font_medium, fill=TEXT_SECONDARY)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def generate_profile_card(
    full_name: str,
    headline: Optional[str],
    skill_score: int,
    tasks_completed: int,
    domain: Optional[str],
) -> bytes:
    """Generate a 1200x630 profile card image."""
    img, draw, ImageFont = _create_base_image()

    font_large = _try_font(ImageFont, 64)
    font_medium = _try_font(ImageFont, 36)
    font_small = _try_font(ImageFont, 28)

    draw.text((80, 80), full_name, font=font_large, fill=TEXT_PRIMARY)

    if headline:
        draw.text((80, 180), headline[:70], font=font_medium, fill=TEXT_SECONDARY)

    draw.text((80, 280), f"Skill Score: {skill_score} / 1000", font=font_medium, fill=GOLD_COLOR)
    draw.text((80, 340), f"{tasks_completed} tasks completed", font=font_small, fill=TEXT_PRIMARY)

    if domain:
        draw.text((80, 400), f"Top domain: {domain}", font=font_small, fill=ACCENT_COLOR)

    draw.text((80, 500), "Proof-of-Work Profile · HireX", font=font_small, fill=TEXT_SECONDARY)
    draw.text((OG_WIDTH - 200, OG_HEIGHT - 60), "HireX", font=font_medium, fill=TEXT_SECONDARY)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def generate_task_card(
    task_title: str,
    domain: str,
    difficulty: str,
    company_name: Optional[str],
    submission_count: int,
) -> bytes:
    """Generate a 1200x630 task preview card image."""
    img, draw, ImageFont = _create_base_image()

    font_large = _try_font(ImageFont, 56)
    font_medium = _try_font(ImageFont, 36)
    font_small = _try_font(ImageFont, 28)

    title_display = task_title[:60] + "..." if len(task_title) > 60 else task_title
    draw.text((80, 80), title_display, font=font_large, fill=TEXT_PRIMARY)

    if company_name:
        draw.text((80, 200), company_name, font=font_medium, fill=TEXT_SECONDARY)

    draw.text((80, 280), f"{domain} · {difficulty.capitalize()}", font=font_medium, fill=ACCENT_COLOR)
    draw.text((80, 360), f"{submission_count} submissions", font=font_small, fill=TEXT_PRIMARY)
    draw.text((80, 460), "Real Tasks. Real Proof. Real Jobs.", font=font_small, fill=GOLD_COLOR)
    draw.text((OG_WIDTH - 200, OG_HEIGHT - 60), "HireX", font=font_medium, fill=TEXT_SECONDARY)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
