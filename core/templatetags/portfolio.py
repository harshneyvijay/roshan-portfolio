import re
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def href(url):
    """Only allow http(s)/mailto/tel links; anything else (incl. [PLACEHOLDERS]) becomes '#'."""
    u = (url or "").strip()
    return u if re.match(r"^(https?://|mailto:|tel:|/)", u, re.I) else "#"


@register.filter
def is_real(url):
    return href(url) != "#"


@register.filter
def richtext(text):
    """Tiny safe formatter: paragraphs, '## ' headings, '- ' lists, **bold**, `code`."""
    out, items = [], []

    def flush():
        if items:
            out.append("<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")
            items.clear()

    def inline(s):
        s = escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        return re.sub(r"`(.+?)`", r"<code>\1</code>", s)

    for block in re.split(r"\n\s*\n", (text or "").strip()):
        for line in block.splitlines():
            line = line.rstrip()
            if line.startswith("- "):
                items.append(inline(line[2:]))
            elif line.startswith("## "):
                flush()
                out.append(f"<h2>{inline(line[3:])}</h2>")
            elif line.strip():
                flush()
                out.append(f"<p>{inline(line)}</p>")
        flush()
    return mark_safe("\n".join(out))


@register.filter
def filesize(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


@register.filter
def pdf_url(name):
    return f"/files/pdf/{name}"
