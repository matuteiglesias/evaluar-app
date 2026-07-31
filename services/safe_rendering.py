import re

import bleach
import markdown
from markupsafe import Markup

from services.exercise_loader import preprocess_latex_for_mathjax


EXERCISE_TAGS = {"br", "code", "div", "em", "i", "img", "li", "ol", "p", "pre", "strong", "ul"}
FEEDBACK_TAGS = {"blockquote", "br", "code", "em", "li", "ol", "p", "pre", "strong", "ul"}
LOCAL_IMAGE = re.compile(r"^/tikzpics/[A-Za-z0-9_-]+\.png$")
UNSAFE_TEX_COMMAND = re.compile(
    r"\\(?:href|url|class|style|cssId|htmlClass|htmlId|htmlStyle|unicode)\b",
    re.IGNORECASE,
)


def _exercise_attribute(tag, name, value):
    if tag == "div" and name == "class":
        return value == "exercise-center"
    if tag == "img":
        if name == "src":
            return LOCAL_IMAGE.fullmatch(value) is not None
        if name == "class":
            return value == "exercise-figure"
        return name == "alt"
    return False


def render_exercise(raw_latex, exercise_id):
    """Apply legacy transformations, then sanitize repository-controlled content."""
    # MathJax sees text after HTML sanitization. Neutralize TeX commands capable
    # of creating URLs, attributes, or HTML so they remain visibly inert text.
    neutral_latex = UNSAFE_TEX_COMMAND.sub(lambda match: f"＼{match.group()[1:]}", raw_latex)
    compatible_html = preprocess_latex_for_mathjax(neutral_latex, exercise_id)
    cleaned = bleach.clean(
        compatible_html,
        tags=EXERCISE_TAGS,
        attributes=_exercise_attribute,
        protocols={"http", "https"},
        strip=True,
        strip_comments=True,
    )
    return Markup(cleaned)


def render_feedback(raw_model_output):
    """Render untrusted model Markdown through a feedback-specific allowlist."""
    try:
        generated_html = markdown.markdown(
            raw_model_output,
            extensions=["fenced_code", "sane_lists"],
            output_format="html",
        )
    except (TypeError, ValueError):
        generated_html = str(raw_model_output)
    cleaned = bleach.clean(
        generated_html,
        tags=FEEDBACK_TAGS,
        attributes={},
        protocols=set(),
        strip=True,
        strip_comments=True,
    )
    return Markup(cleaned)
