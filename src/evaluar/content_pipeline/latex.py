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


def render_latex(source: str, asset_sources: dict[str, str] | None = None) -> str:
    """Escape authored source, preserving math and rendering only compiler-approved images."""
    replacements: dict[str, str] = {}
    approved = asset_sources or {}

    def replace_asset(match: re.Match[str]) -> str:
        asset = match.group(1)
        src = approved.get(asset)
        if src is None:
            return match.group(0)
        token = f"EVALUARASSETTOKEN{len(replacements)}END"
        replacements[token] = (
            f'<img class="exercise-figure" src="{html.escape(src, quote=True)}" '
            f'alt="{html.escape(asset, quote=True)}">'
        )
        return token

    source_with_tokens = ASSET_REFERENCE.sub(replace_asset, source)
    escaped = html.escape(source_with_tokens)
    for token, markup in replacements.items():
        escaped = escaped.replace(token, markup)
    paragraphs = [part.replace("\n", "<br>\n") for part in re.split(r"\n\s*\n", escaped)]
    return "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs if paragraph)
