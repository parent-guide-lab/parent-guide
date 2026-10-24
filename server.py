#!/usr/bin/env python3
"""parent-guide local server: static hosting + data API. Stdlib only.

Serves the built single-file renderer (web/dist/render.html) and reads/writes
the user's local data directory (data/child.json + data/page.json). Data never
leaves the machine; GET falls back to data-templates when files are missing.

Usage:
    python3 server.py [--open] [--port N] [--data DIR] [--web DIR]
    Env overrides: PG_PORT / PG_DATA / PG_WEB (CLI flags win over env).
"""
import argparse
import json
import os
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from knowledge_render import md_to_html, parse_provenance

ROOT = Path(__file__).resolve().parent
TEMPLATE_PAGE = ROOT / "skills/parent-guide/data-templates/page.json"
TEMPLATE_DATA = ROOT / "skills/parent-guide/data-templates/child.json"

_KB_META_FILES = {"README.md", "LICENSE.md", "BACKLOG.md"}


def _official_topics():
    """Official knowledge metadata. site/knowledge.json is the build product
    of build-site.py TOPICS (single source); the H1 scan below only covers
    the unlikely case of a repo copy without a built site."""
    try:
        data = json.loads((ROOT / "site/knowledge.json").read_text("utf-8"))
        if isinstance(data, list) and data:
            return data
    except (OSError, ValueError):
        pass
    fallback = []
    for md in sorted((ROOT / "knowledge").glob("*.md")):
        if md.name in _KB_META_FILES:
            continue
        slug = "tantrum" if md.stem == "tantrum-cdc" else md.stem
        title, _, _ = parse_provenance(md.read_text("utf-8"))
        fallback.append({"file": md.name, "slug": slug, "title": title or md.stem,
                         "hook": None, "src": None})
    return fallback


def _user_knowledge():
    """Self-built docs under knowledge/user/ (README.md is the convention
    doc, not content). Local-only layer: never published, listed here only."""
    udir = ROOT / "knowledge/user"
    items = []
    if not udir.is_dir():
        return items
    for md in sorted(udir.glob("*.md")):
        if md.name == "README.md":
            continue
        title, meta, _ = parse_provenance(md.read_text("utf-8"))
        items.append({"file": md.name, "title": title or md.stem, "meta": meta})
    return items


def _read_knowledge(name):
    """Render one knowledge doc to HTML for the in-app knowledge page.

    Three reachable layers, each a strict allowlist:
      quickref.md    -> site-src/quickref.md (the site quick-ref page's twin)
      user/<name>.md -> knowledge/user/ (family-private layer, bare name only)
      <file>.md      -> knowledge/ official closed set (files knowledge.json lists)
    Meta files (README/LICENSE/BACKLOG), traversal and subdirs are rejected.
    """
    if not name or not name.endswith(".md") or "\\" in name or name.startswith("/"):
        raise ValueError("非法文件名")
    if name == "quickref.md":
        path = ROOT / "site-src" / "quickref.md"
    elif name.startswith("user/"):
        rest = name[len("user/"):]
        if "/" in rest or not rest.endswith(".md"):
            raise ValueError("自建层只允许 user/ 下的单个 .md 文件名")
        if rest == "README.md":
            raise ValueError("README.md 是自建层约定文档,不是自建知识")
        path = ROOT / "knowledge/user" / rest
    else:
        if "/" in name:
            raise ValueError("官方层只允许单个 .md 文件名")
        official = {t["file"] for t in _official_topics()}
        official.discard("quickref.md")  # handled above (lives in site-src/)
        if name in _KB_META_FILES or name not in official:
            raise ValueError(f"未知官方专题文件:{name}")
        path = ROOT / "knowledge" / name
    if not path.is_file():
        raise FileNotFoundError(name)
    title, meta, body = parse_provenance(path.read_text("utf-8"))
    return {"file": name, "title": title or name, "meta": meta, "html": md_to_html(body)}


def _load_json(path, bootstrap_flag=False):
    """Read JSON file; on missing file, fall back to the shipped template.

    Returns (obj, bootstrapped): bootstrapped=True means "no real file yet,
    content came from data-templates" so the client can hint first-time setup.
    """
    try:
        return json.loads(path.read_text("utf-8")), False
    except FileNotFoundError:
        obj = json.loads(TEMPLATE_PAGE.read_text("utf-8")) if path.name == "page.json" \
            else json.loads(TEMPLATE_DATA.read_text("utf-8"))
        return obj, True


def make_server(port, data_dir, web_dir):
    """Build an HTTPServer bound to localhost. Paths are resolved by the caller
    (CLI/env), so this factory stays test-friendly: no globals, no side effects."""
    data_dir = Path(data_dir)
    page_file = data_dir / "page.json"
    data_file = data_dir / "child.json"

    class Handler(SimpleHTTPRequestHandler):
        # SimpleHTTPRequestHandler(directory=...) confines static serving to
        # web_dir and normalizes away any ../ traversal internally.

        def end_headers(self):
            # 本地服务同样禁缓存:改版后用户刷新看到的一定是新版
            # (判例:用户本地看旧版多为缓存,曾误判为 bug)
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(web_dir), **kwargs)

        def log_message(self, *args):  # keep console quiet
            pass

        def guess_type(self, path):
            # .md must display in the browser, not trigger a download
            # (mimetypes has no mapping for it on most systems).
            if str(path).endswith(".md"):
                return "text/plain; charset=utf-8"
            return super().guess_type(path)

        def translate_path(self, path):
            # /site/* serves the repo's knowledge pages (site/) instead of
            # web/dist -- the local entry into the public knowledge base.
            if path.startswith("/site/") or path == "/site":
                rel = path[len("/site"):].lstrip("/")
                full = os.path.normpath(os.path.join(str(ROOT / "site"), rel))
                if full == str(ROOT / "site") or full.startswith(str(ROOT / "site") + os.sep):
                    return full
            # /knowledge/* serves the raw official knowledge files (read-only),
            # so page cards can deep-link their source (e.g. growth card ->
            # knowledge/growth.md).
            if path.startswith("/knowledge/") or path == "/knowledge":
                rel = path[len("/knowledge"):].lstrip("/")
                full = os.path.normpath(os.path.join(str(ROOT / "knowledge"), rel))
                if full.startswith(str(ROOT / "knowledge") + os.sep):
                    return full
            return super().translate_path(path)

        def _send_json(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_body(self):
            length = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self):
            try:
                if self.path == "/api/page":
                    obj, bootstrapped = _load_json(page_file)
                    if bootstrapped:
                        obj["bootstrapped"] = True
                    return self._send_json(200, obj)
                if self.path == "/api/data":
                    obj, bootstrapped = _load_json(data_file)
                    if bootstrapped:
                        obj["bootstrapped"] = True
                    return self._send_json(200, obj)
                if self.path == "/api/knowledge":
                    return self._send_json(200, {"official": _official_topics(),
                                                 "user": _user_knowledge()})
                if self.path.startswith("/api/knowledge/read"):
                    q = parse_qs(urlsplit(self.path).query)
                    names = q.get("file") or []
                    if not names:
                        return self._send_json(400, {"error": "缺少 file 参数"})
                    try:
                        return self._send_json(200, _read_knowledge(names[0]))
                    except ValueError as e:
                        return self._send_json(400, {"error": str(e)})
                    except OSError as e:
                        return self._send_json(404, {"error": str(e)})
            except (OSError, ValueError) as e:
                return self._send_json(500, {"error": str(e)})
            if self.path == "/":
                self.path = "/render.html"  # root serves the renderer directly
            super().do_GET()

        def do_POST(self):
            kind = self.path.removeprefix("/api/")
            target = {"page": page_file, "data": data_file}.get(kind)
            if target is None:
                return self._send_json(404, {"error": "unknown endpoint"})
            try:
                payload = self._read_body()
                if kind == "page" and not isinstance(payload.get("blocks"), list):
                    raise ValueError("page.json 必须包含 blocks 数组")
                if kind == "page":
                    # duplicate/missing block ids corrupt geometry write-backs
                    # (GridStack keys by id) -- fail fast, 400
                    ids = [b.get("id") for b in payload["blocks"] if isinstance(b, dict)]
                    bad = [i for i in ids if i is None or not str(i).strip()]
                    dup = sorted({i for i in ids if ids.count(i) > 1 and i is not None})
                    if bad or dup:
                        raise ValueError(f"blocks 存在重复/缺失 id: {dup or '(有 block 无 id)'}")
                    if len(ids) != len(payload["blocks"]):
                        raise ValueError("blocks 里混入了非对象条目")
                    # autoH/minH: type-check when present (fail fast; defaults live in the renderer)
                    for b in payload["blocks"]:
                        if "autoH" in b and not isinstance(b["autoH"], bool):
                            raise ValueError(f"block {b['id']}: autoH 必须是布尔值")
                        if "minH" in b and (not isinstance(b["minH"], int) or not 1 <= b["minH"] <= 20):
                            raise ValueError(f"block {b['id']}: minH 必须是 1..20 的整数")
                    # tracker 自定义卡 props 白名单(2026-10-22 M1,验收集背书):
                    # 计数口径是机械的(head 只声明 count,渲染器从 items 现算),结构坏=拒写
                    TONES = {"ok", "watch", "todo", "sub"}
                    for b in payload["blocks"]:
                        if b.get("type") != "tracker":
                            continue
                        bid, p = b.get("id"), b.get("props") or {}
                        if not str(p.get("title") or "").strip():
                            raise ValueError(f"block {bid}: tracker 缺 title")
                        items = p.get("items")
                        if not isinstance(items, list) or not 1 <= len(items) <= 100:
                            raise ValueError(f"block {bid}: tracker items 必须是 1..100 条的数组")
                        for i, it in enumerate(items):
                            if not isinstance(it, dict) or not str(it.get("text") or "").strip():
                                raise ValueError(f"block {bid}: tracker items[{i}] 缺 text")
                            for k in ("group", "badge", "meta"):
                                if k in it and not isinstance(it[k], str):
                                    raise ValueError(f"block {bid}: tracker items[{i}].{k} 必须是字符串")
                            if "tone" in it and it["tone"] not in TONES:
                                raise ValueError(f"block {bid}: tracker items[{i}].tone 必须是 ok/watch/todo/sub")
                        head = p.get("head", [])
                        if not isinstance(head, list) or len(head) > 4:
                            raise ValueError(f"block {bid}: tracker head 必须是 ≤4 项的数组")
                        for h in head:
                            if not isinstance(h, dict) or not str(h.get("label") or "").strip():
                                raise ValueError(f"block {bid}: tracker head 项缺 label")
                            if h.get("count") == "group":
                                if not str(h.get("eq") or "").strip():
                                    raise ValueError(f"block {bid}: tracker head count=group 必须带 eq")
                            elif h.get("count") != "items":
                                raise ValueError(f"block {bid}: tracker head.count 必须是 items 或 group")
                            if "tone" in h and h["tone"] not in TONES:
                                raise ValueError(f"block {bid}: tracker head.tone 必须是 ok/watch/todo/sub")
                    # page 页面卡 props 白名单(2026-10-24 拍板:卡=小页面,AI 从锁定
                    # 词汇表自由组装;text/list 退役存量兼容。fail-soft 原则同 tracker)
                    PAGE_KINDS = {"section", "p", "rows", "kv", "check", "callout"}
                    CALLOUT_TONES = {"hint", "warn"}
                    for b in payload["blocks"]:
                        if b.get("type") != "page":
                            continue
                        bid, p = b.get("id"), b.get("props") or {}
                        if not str(p.get("title") or "").strip():
                            raise ValueError(f"block {bid}: page 缺 title")
                        pblocks = p.get("blocks")
                        if not isinstance(pblocks, list) or not 1 <= len(pblocks) <= 30:
                            raise ValueError(f"block {bid}: page blocks 必须是 1..30 块的数组")
                        for i, bl in enumerate(pblocks):
                            if not isinstance(bl, dict):
                                raise ValueError(f"block {bid}: page blocks[{i}] 必须是对象")
                            kind = bl.get("kind")
                            if kind not in PAGE_KINDS:
                                raise ValueError(
                                    f"block {bid}: page blocks[{i}].kind 必须是 {'/'.join(sorted(PAGE_KINDS))}")
                            if kind in ("section", "p", "callout") and not str(bl.get("text") or "").strip():
                                raise ValueError(f"block {bid}: page blocks[{i}] 缺 text")
                            if kind == "callout" and bl.get("tone") not in CALLOUT_TONES:
                                raise ValueError(f"block {bid}: page callout.tone 必须是 hint/warn")
                            if kind == "kv" and (not str(bl.get("label") or "").strip()
                                                 or not str(bl.get("text") or "").strip()):
                                raise ValueError(f"block {bid}: page kv 缺 label/text")
                            if kind in ("rows", "check"):
                                items = bl.get("items")
                                if not isinstance(items, list) or not 1 <= len(items) <= 30:
                                    raise ValueError(f"block {bid}: page {kind} items 必须是 1..30 条的数组")
                                for j, it in enumerate(items):
                                    if isinstance(it, dict):
                                        if not str(it.get("text") or "").strip():
                                            raise ValueError(f"block {bid}: page {kind} items[{j}] 缺 text")
                                        if kind == "check" and "done" in it and not isinstance(it["done"], bool):
                                            raise ValueError(
                                                f"block {bid}: page check items[{j}].done 必须是布尔")
                                    elif not (isinstance(it, str) and it.strip()):
                                        raise ValueError(f"block {bid}: page {kind} items[{j}] 必须是字符串或对象")
                if kind == "data" and not [k for k in payload if not k.startswith("_")]:
                    raise ValueError("child.json 必须包含至少一个孩子数据键")
                payload.pop("bootstrapped", None)  # internal flag never persists
                data_dir.mkdir(parents=True, exist_ok=True)
                tmp = target.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
                tmp.replace(target)  # atomic: tmp + rename, no half-written files
                self._send_json(200, {"saved": target.name})
            except (OSError, ValueError) as e:
                self._send_json(400, {"error": str(e)})

    return HTTPServer(("127.0.0.1", port), Handler)


def main():
    ap = argparse.ArgumentParser(description="parent-guide local server")
    ap.add_argument("--open", action="store_true", help="open the page in a browser")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PG_PORT", 8765)))
    ap.add_argument("--data", default=os.environ.get("PG_DATA", str(ROOT / "data")))
    ap.add_argument("--web", default=os.environ.get("PG_WEB", str(ROOT / "web/dist")))
    args = ap.parse_args()

    httpd = make_server(args.port, args.data, args.web)
    url = f"http://127.0.0.1:{args.port}/render.html"
    print(f"parent-guide 本地服务已启动:{url}(Ctrl+C 退出)")
    if args.open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
