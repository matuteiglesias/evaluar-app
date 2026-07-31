"""Conservative LaTeX validation and precompilation."""

import html
import re

UNSUPPORTED = re.compile(
    r"\\(?:input|include|write|openout|read|catcode|csname|usepackage|href|url|class|style|htmlClass|htmlId|htmlStyle)\b",
    re.I,
)
REFERENCE = re.compile(r"\\(?:ref|eqref)\{([^}]+)\}")
LABEL = re.compile(r"\\label\{([^}]+)\}")
ASSET_REFERENCE = re.compile(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}")


def validate_latex(source: str) -> tuple[list[str], set[str], set[str]]:
    unsupported = sorted(set(match.group(0) for match in UNSUPPORTED.finditer(source)))
    labels = set(LABEL.findall(source))
    missing_refs = set(REFERENCE.findall(source)) - labels
    assets = set(ASSET_REFERENCE.findall(source))
    return unsupported, missing_refs, assets


def render_latex(source: str) -> str:
    """Escape source and preserve math for client-side MathJax; never emit source HTML."""
    escaped = html.escape(source)
    paragraphs = [part.replace("\n", "<br>\n") for part in re.split(r"\n\s*\n", escaped)]
    return "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs if paragraph)
