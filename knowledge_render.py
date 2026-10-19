#!/usr/bin/env python3
"""Shared markdown renderer for parent-guide knowledge files. Stdlib only.

Why a root module: server.py ships in the public repo but scripts/ does not
(scripts/publish.sh excludes it), so server.py must not import from scripts/.
Both consumers import from here:
  - scripts/build-site.py  renders knowledge/*.md into the public site/ pages
  - server.py              renders knowledge/user/*.md into the in-app
                           knowledge panel (self-built layer, local only)

The md subset is the one used by knowledge/ files: headings, paragraphs,
ul/ol, pipe tables, > quotes (rendered as .note), ``` code blocks, --- rules,
**bold** / `code` / [links](url) inline. Sections titled with "(给 AI)" are
internal skill protocol and skipped, as is the provenance blockquote header.
"""
import html
import re

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_CODE = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_UL_ITEM = re.compile(r"^\s*[-*] ")
_OL_ITEM = re.compile(r"^\s*\d+\. ")

# provenance header fields: official files use 入库:, self-built use 自建:
_PROV_DATE = re.compile(r"(?:自建|入库)[:：]\s*(\d{4}-\d{2}-\d{2})")
_PROV_TYPE = re.compile(r"类型[=＝]\s*([^;；\n]*)")
_PROV_SOURCE = re.compile(r"来源[=＝]\s*([^;；\n]*)")
_PROV_CHECK = re.compile(r"核对[=＝]\s*([^;；\n]*)")


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = _LINK.sub(r'<a href="\2">\1</a>', s)
    s = _BOLD.sub(r"<b>\1</b>", s)
    s = _CODE.sub(r"<code>\1</code>", s)
    return s


def render_table(rows):
    head = [c.strip() for c in rows[0].strip().strip("|").split("|")]
    body = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows[2:]]
    out = ["<table><thead><tr>"]
    out += [f"<th>{inline(c)}</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for r in body:
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def parse_provenance(text: str):
    """Split a knowledge file into (title, meta, body).

    title = the H1 line; meta = fields of the provenance blockquote right
    after it (date/type/source/check; missing fields come back as None);
    body = the remainder, ready for md_to_html (which skips the same header
    again, so passing the full text also works).
    """
    lines = text.splitlines()
    title = None
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        lines = lines[1:]
    header = []
    while lines and (lines[0].startswith(">") or not lines[0].strip()):
        header.append(lines.pop(0))
    blob = "\n".join(header)

    def field(rx):
        m = rx.search(blob)
        return m.group(1).strip() or None if m else None

    meta = {
        "date": field(_PROV_DATE),
        "type": field(_PROV_TYPE),
        "source": field(_PROV_SOURCE),
        "check": field(_PROV_CHECK),
    }
    return title, meta, "\n".join(lines)


def md_to_html(text: str) -> str:
    """Render the subset of markdown used by knowledge/ files.

    Skips the provenance header: the blockquote block immediately following
    the H1 line (internal bookkeeping, not for the public site).
    """
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
        while lines and (lines[0].startswith(">") or not lines[0].strip()):
            lines = lines[1:]
    out, para, table, quote, code = [], [], [], [], False
    skip_section = False  # inside a "…(给 AI)" section: internal protocol, skip until next heading
    code_buf = []

    def flush_para():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    def flush_quote():
        if quote:
            out.append(f'<div class="note">{inline(" ".join(quote))}</div>')
            quote.clear()

    i = 0
    while i < len(lines):
        ln = lines[i]
        if skip_section and not (ln.startswith("## ") or ln.startswith("# ")):
            i += 1
            continue
        if ln.strip().startswith("```"):
            if code:
                out.append("<pre>" + html.escape("\n".join(code_buf)) + "</pre>")
                code_buf = []
                code = False
            else:
                flush_para(); flush_quote()
                code = True
            i += 1
            continue
        if code:
            code_buf.append(ln)
            i += 1
            continue
        if ln.strip().startswith("|"):
            flush_para(); flush_quote()
            table.append(ln)
            i += 1
            if i >= len(lines) or not lines[i].strip().startswith("|"):
                out.append(render_table(table))
                table = []
            continue
        if ln.startswith("> "):
            flush_para()
            quote.append(ln[2:])
            i += 1
            continue
        flush_quote()
        if not ln.strip():
            flush_para()
        elif ln.startswith("## "):
            flush_para()
            skip_section = "(给 AI)" in ln
            if not skip_section:
                out.append(f"<h2>{inline(ln[3:])}</h2>")
        elif ln.startswith("### "):
            flush_para()
            out.append(f"<h3>{inline(ln[4:])}</h3>")
        elif ln.startswith("# "):
            flush_para()
            skip_section = "(给 AI)" in ln
            if not skip_section:
                out.append(f"<h1>{inline(ln[2:])}</h1>")
        elif _UL_ITEM.match(ln):
            flush_para()
            items = []
            while i < len(lines) and _UL_ITEM.match(lines[i]):
                text = _UL_ITEM.sub("", lines[i])
                items.append(f"<li>{inline(text)}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif _OL_ITEM.match(ln):
            flush_para()
            items = []
            while i < len(lines) and _OL_ITEM.match(lines[i]):
                text = _OL_ITEM.sub("", lines[i])
                items.append(f"<li>{inline(text)}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue
        elif ln.strip() in ("---", "***"):
            flush_para()
            out.append("<hr>")
        else:
            para.append(ln.strip())
        i += 1
    flush_para(); flush_quote()
    if table:
        out.append(render_table(table))
    return "\n".join(out)
