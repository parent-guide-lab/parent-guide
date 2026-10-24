#!/usr/bin/env python3
"""Unit tests for the production server.py (stdlib only).

Runs the server in-process on a worker thread against temp dirs, then checks
the API contract: template bootstrap fallback, atomic writes, validation
rejections, static hosting. Run: python3 tests/test_server.py
"""
import http.client
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

import sys, os
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import server  # noqa: E402

HOST, PORT = "127.0.0.1", 18765  # test fixture constants


def call(method, path, payload=None):
    """Talk to the in-process test server over http.client."""
    conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
    try:
        headers, body = {}, None
        if payload is not None:
            body = json.dumps(payload)
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        return resp.status, json.loads(resp.read() or b"{}")
    finally:
        conn.close()


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="pg-server-test-"))
        cls.data_dir = cls.tmp / "data"
        cls.web_dir = cls.tmp / "web"
        cls.web_dir.mkdir()
        (cls.web_dir / "render.html").write_text("<!DOCTYPE html><title>stub</title>",
                                                 encoding="utf-8")
        cls.httpd = server.make_server(PORT, cls.data_dir, cls.web_dir)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_01_get_page_bootstraps_from_template(self):
        code, body = call("GET", "/api/page")
        self.assertEqual(code, 200)
        self.assertTrue(isinstance(body.get("blocks"), list))
        self.assertTrue(body.get("bootstrapped"), "missing-file GET must flag bootstrapped")

    def test_02_get_data_bootstraps_from_template(self):
        code, body = call("GET", "/api/data")
        self.assertEqual(code, 200)
        keys = [k for k in body if not k.startswith("_")]
        self.assertTrue(keys, "template data must contain a child key")
        self.assertTrue(body.get("bootstrapped"))

    def test_03_static_hosting(self):
        conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
        try:
            conn.request("GET", "/")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)
            self.assertIn("stub", resp.read().decode())
        finally:
            conn.close()

    def test_03b_cache_control_no_store(self):
        # 2026-10-23:全响应禁缓存(判例:用户本地看旧版多为缓存,曾误判为 bug)
        conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
        try:
            conn.request("GET", "/")
            resp = conn.getresponse()
            resp.read()
            self.assertEqual(resp.getheader("Cache-Control"), "no-store")
        finally:
            conn.close()
        st, _ = call("GET", "/api/page")
        self.assertEqual(st, 200)
        # API 侧同样带头(经 call 的原始连接验证)
        conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
        try:
            conn.request("GET", "/api/page")
            resp = conn.getresponse()
            resp.read()
            self.assertEqual(resp.getheader("Cache-Control"), "no-store")
        finally:
            conn.close()

    def test_04_post_bad_json_rejected(self):
        conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
        try:
            conn.request("POST", "/api/page", body=b"{not json",
                         headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            self.assertEqual(resp.status, 400)
            resp.read()
        finally:
            conn.close()

    def test_05_post_page_without_blocks_rejected(self):
        code, _ = call("POST", "/api/page", {"version": 2, "blocks": "nope"})
        self.assertEqual(code, 400)

    def test_06_post_data_without_child_rejected(self):
        code, _ = call("POST", "/api/data", {"_meta": {"notice": "no child"}})
        self.assertEqual(code, 400)

    def test_07_post_page_atomic_roundtrip(self):
        page = {"version": 2, "title": "t", "child": "c", "blocks":
                [{"id": "b1", "type": "profile", "x": 0, "y": 0, "w": 4, "h": 5}]}
        code, _ = call("POST", "/api/page", page)
        self.assertEqual(code, 200)
        code, got = call("GET", "/api/page")
        self.assertEqual(code, 200)
        self.assertEqual(got["blocks"][0]["id"], "b1")
        self.assertNotIn("bootstrapped", got, "after a real file exists, no bootstrap flag")
        leftovers = [f.name for f in self.data_dir.iterdir() if f.name.endswith(".tmp")]
        self.assertEqual(leftovers, [], "atomic write must leave no tmp files")

    def test_08_post_data_writes_child(self):
        child = {"_meta": {"notice": "n"}, "taozi": {"name": "桃子", "birthdate": "2024-04-10"}}
        code, _ = call("POST", "/api/data", child)
        self.assertEqual(code, 200)
        code, got = call("GET", "/api/data")
        self.assertEqual(code, 200)
        self.assertEqual(got["taozi"]["name"], "桃子")

    def test_09_post_page_duplicate_ids_rejected(self):
        page = {"version": 2, "blocks": [
            {"id": "b1", "type": "profile", "x": 0, "y": 0, "w": 4, "h": 5},
            {"id": "b1", "type": "list", "x": 4, "y": 0, "w": 4, "h": 5,
             "props": {"title": "出门清单", "items": [{"text": "水杯", "done": False}]}}]}
        code, resp = call("POST", "/api/page", page)
        self.assertEqual(code, 400)
        self.assertIn("重复", resp["error"])

    def test_10_post_page_missing_id_rejected(self):
        page = {"version": 2, "blocks": [
            {"type": "profile", "x": 0, "y": 0, "w": 4, "h": 5}]}
        code, resp = call("POST", "/api/page", page)
        self.assertEqual(code, 400)

    # tracker 自定义卡 props 校验(2026-10-22 M1:验收集背书,docs/custom-card-acceptance-2026-10-22.md)
    def _tracker(self, **over):
        props = {"title": "绘本管理",
                 "head": [{"count": "items", "label": "共"},
                          {"count": "group", "eq": "读完", "label": "读完", "tone": "ok"}],
                 "items": [{"text": "晚安,月亮", "group": "读完", "badge": "读完",
                            "tone": "ok", "meta": "09-30"}]}
        props.update(over)
        return {"version": 2, "blocks": [
            {"id": "b1", "type": "tracker", "x": 0, "y": 0, "w": 6, "h": 5, "props": props}]}

    def test_15_post_valid_tracker_accepted(self):
        code, _ = call("POST", "/api/page", self._tracker())
        self.assertEqual(code, 200)

    def test_16_post_tracker_missing_items_rejected(self):
        code, resp = call("POST", "/api/page", self._tracker(items=None))
        self.assertEqual(code, 400)
        self.assertIn("items", resp["error"])

    def test_17_post_tracker_item_without_text_rejected(self):
        code, _ = call("POST", "/api/page",
                       self._tracker(items=[{"text": "  "}, {"group": 3}]))
        self.assertEqual(code, 400)

    def test_18_post_tracker_bad_tone_rejected(self):
        code, _ = call("POST", "/api/page",
                       self._tracker(items=[{"text": "x", "tone": "blue"}]))
        self.assertEqual(code, 400)

    def test_19_post_tracker_head_group_without_eq_rejected(self):
        code, _ = call("POST", "/api/page",
                       self._tracker(head=[{"count": "group", "label": "在读"}]))
        self.assertEqual(code, 400)

    def test_20_post_tracker_head_bad_count_rejected(self):
        code, _ = call("POST", "/api/page",
                       self._tracker(head=[{"count": "sum", "label": "共"}]))
        self.assertEqual(code, 400)

    # page 页面卡 props 校验(2026-10-24 拍板:卡=小页面,AI 从锁定词汇表自由组装;
    # text/list 退役存量兼容。fail-soft 原则同 tracker:结构坏=拒写)
    def _page(self, **over):
        props = {"title": "英语启蒙",
                 "blocks": [{"kind": "rows", "items": ["真人互动为主", "每天固定 15 分钟"]},
                            {"kind": "callout", "tone": "hint", "text": "发音不准不纠正"}]}
        props.update(over)
        return {"version": 2, "blocks": [
            {"id": "b9", "type": "page", "x": 0, "y": 0, "w": 5, "h": 5, "props": props}]}

    def test_21_post_valid_page_accepted(self):
        code, _ = call("POST", "/api/page", self._page())
        self.assertEqual(code, 200)

    def test_22_post_page_missing_title_rejected(self):
        code, resp = call("POST", "/api/page", self._page(title="  "))
        self.assertEqual(code, 400)
        self.assertIn("title", resp["error"])

    def test_23_post_page_bad_kind_rejected(self):
        code, _ = call("POST", "/api/page",
                       self._page(blocks=[{"kind": "chart", "text": "x"}]))
        self.assertEqual(code, 400)

    def test_24_post_page_rows_without_items_rejected(self):
        code, _ = call("POST", "/api/page", self._page(blocks=[{"kind": "rows"}]))
        self.assertEqual(code, 400)

    def test_25_post_page_check_bad_done_rejected(self):
        code, _ = call("POST", "/api/page",
                       self._page(blocks=[{"kind": "check", "items": [{"text": "x", "done": "yes"}]}]))
        self.assertEqual(code, 400)

    def test_26_post_page_callout_bad_tone_rejected(self):
        code, _ = call("POST", "/api/page",
                       self._page(blocks=[{"kind": "callout", "tone": "blue", "text": "x"}]))
        self.assertEqual(code, 400)

    def test_27_post_page_kv_missing_label_rejected(self):
        code, _ = call("POST", "/api/page",
                       self._page(blocks=[{"kind": "kv", "text": "x"}]))
        self.assertEqual(code, 400)

    def test_11_site_knowledge_pages_served(self):
        def raw(path):
            conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
            try:
                conn.request("GET", path)
                resp = conn.getresponse()
                return resp.status, resp.read().decode("utf-8", "ignore")
            finally:
                conn.close()
        code, body = raw("/site/index.html")
        self.assertEqual(code, 200)
        self.assertIn("知识", body[:800])            # knowledge index renders
        code, _ = raw("/site/quick-ref.html")
        self.assertEqual(code, 200)
        code, _ = raw("/site/../../data/child.json")  # traversal must not escape
        self.assertNotEqual(code, 200)

    def test_12_knowledge_index_lists_both_layers(self):
        code, body = call("GET", "/api/knowledge")
        self.assertEqual(code, 200)
        self.assertTrue(body["official"], "official topics must be non-empty")
        for t in body["official"]:
            self.assertTrue(t["file"].endswith(".md"))
            self.assertTrue(t["slug"] and t["title"])
        self.assertNotIn("README.md", [u["file"] for u in body["user"]],
                         "user/README.md is the convention doc, not self-built content")

    def test_13_knowledge_read_renders_user_doc(self):
        fixture = ROOT / "knowledge/user/_test-fixture.md"
        fixture.write_text(
            "# 测试专题\n"
            "> 自建:2026-10-13;类型=调研转述;来源=测试来源;核对=转述级\n\n"
            "## 口径\n\n- 参考 sleep.md §2 的分阶思路\n",
            encoding="utf-8")
        self.addCleanup(fixture.unlink)
        code, body = call("GET", "/api/knowledge/read?file=user/_test-fixture.md")
        self.assertEqual(code, 200)
        self.assertEqual(body["title"], "测试专题")
        self.assertEqual(body["meta"]["type"], "调研转述")
        self.assertIn("<h2>", body["html"])
        # in-app doc keeps its knowledge refs plain; the page linkifies client-side
        self.assertIn("sleep.md §2", body["html"])

    def test_13b_knowledge_read_renders_official_and_quickref(self):
        code, body = call("GET", "/api/knowledge/read?file=sleep.md")
        self.assertEqual(code, 200)
        self.assertTrue(body["title"] and "<h2>" in body["html"])
        code, body = call("GET", "/api/knowledge/read?file=quickref.md")
        self.assertEqual(code, 200)
        self.assertIn("速查", body["title"])

    def test_14_knowledge_read_rejects_bad_names(self):
        for path in ("/api/knowledge/read?file=../growth.md",       # traversal
                     "/api/knowledge/read?file=sub/x.md",           # subdirectory
                     "/api/knowledge/read?file=user/sub/x.md",      # user subdirectory
                     "/api/knowledge/read?file=user/README.md",     # convention doc
                     "/api/knowledge/read?file=README.md",          # meta file
                     "/api/knowledge/read?file=BACKLOG.md",         # meta file
                     "/api/knowledge/read?file=nope.md",            # unregistered
                     "/api/knowledge/read?file=user/nope.md",       # missing user doc
                     "/api/knowledge/read"):                        # no param
            code, body = call("GET", path)
            self.assertIn(code, (400, 404), path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
