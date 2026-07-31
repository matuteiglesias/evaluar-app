"""Final allow-list sanitization for compiler output."""

from html import escape
from html.parser import HTMLParser

ALLOWED_TAGS = {"p", "br", "strong", "em", "code", "pre", "ul", "ol", "li", "span"}
ALLOWED_ATTRIBUTES = {"span": {"class"}}


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            return
        allowed = ALLOWED_ATTRIBUTES.get(tag, set())
        rendered = "".join(
            f' {name}="{escape(value or "", quote=True)}"'
            for name, value in attrs
            if name in allowed
        )
        self.parts.append(f"<{tag}{rendered}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in ALLOWED_TAGS and tag != "br":
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(escape(data))


def sanitize_html(value: str) -> str:
    parser = _Sanitizer()
    parser.feed(value)
    parser.close()
    return "".join(parser.parts)
