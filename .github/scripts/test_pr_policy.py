import json
from pathlib import Path
import unittest
from unittest.mock import patch

from pr_policy import BOT_ID, CONTEXT, SECTIONS, SUMMARY, description_errors, main, review_result

TEMPLATE = (Path(__file__).resolve().parents[1] / "pull_request_template.md").read_text()
HEAD = "a" * 40
URL = "https://github.com/example/studio/pull/7"


def filled(kind="feature", scopes=("前端", "后端")):
    body = TEMPLATE
    for choice in (kind, *scopes):
        body = body.replace(f"- [ ] {choice}", f"- [x] {choice}")
    details = ["续拍时可保留原片的走位。", "- **前端** 增加续拍入口。\n- **后端** 接受原片引用。", "通过续拍接口及浏览器回归。"]
    for heading, detail in zip(SECTIONS, details):
        body = body.replace(f"## {heading}\n", f"## {heading}\n\n{detail}\n")
    return body


def summary(sha=HEAD, status="completed", unresolved=False, author=BOT_ID, updated="2026-11-28T00:00:00Z"):
    review = {"code_review": {"commit_sha": sha, "status": status, "has_unresolved_findings": unresolved}}
    return {"id": 1, "user": {"id": author}, "updated_at": updated, "html_url": URL + "#issuecomment-1",
            "body": f"{SUMMARY}\n<!-- codex-review-state:v1 {json.dumps(review)} -->"}


class PrPolicyTests(unittest.TestCase):
    def test_feature_multiple_scopes_and_bug_with_optional_section_removed(self):
        self.assertEqual(description_errors("[feature][后端+前端] 从片尾续拍", filled()), [])
        bug = filled("bug", ("后端",)).split("## 兼容与发布")[0].replace(
            "续拍时可保留原片的走位。", "复现时删除上游，原先保存成功，预期保存失败。")
        self.assertEqual(description_errors("[bug][后端] 拦住已删除的来源", bug), [])

    def test_template_checkboxes_are_not_evidence(self):
        checked = TEMPLATE.replace("[ ] feature", "[x] feature").replace("[ ] 文档", "[x] 文档")
        errors = description_errors("[feature][文档] 添加指引", checked)
        self.assertEqual(len(errors), 3)
        for heading in SECTIONS[:3]:
            self.assertTrue(any(heading in e for e in errors))

    def test_missing_or_mismatched_metadata(self):
        for title, body in [
            ("[fix][前端+后端] 续拍", filled()),
            ("[feature][前端] 续拍", filled()),
            ("[feature][前端+前端] 续拍", filled(scopes=("前端",))),
            ("[feature][前端+后端] 续拍", filled().replace("[ ] bug", "[x] bug")),
            ("[feature][前端+后端] 续拍", filled().replace("## 验证与证据", "## 其他")),
        ]:
            with self.subTest(title=title):
                self.assertTrue(description_errors(title, body))

    def test_example_in_fence_does_not_change_actual_type_or_sections(self):
        body = filled().replace("续拍时可保留原片的走位。", "续拍时可保留原片的走位。\n~~~md\n- [x] bug\n## 验证与证据\n~~~")
        self.assertEqual(description_errors("[feature][前端+后端] 从片尾续拍", body), [])

    def test_each_selected_scope_needs_a_concrete_change(self):
        body = filled().replace("- **后端** 接受原片引用。", "### 后端")
        self.assertTrue(description_errors("[feature][前端+后端] 从片尾续拍", body))
        self.assertEqual(description_errors("[feature][前端+后端] 从片尾续拍", body.replace(
            "### 后端", "### 后端\n- 接受原片引用。")), [])

    def test_empty_stale_running_or_copied_report_never_passes(self):
        for comments in ([], [{"user": None, "body": None}], [summary(sha="b" * 40)], [summary(status="in_progress")],
                         [summary(author=7)], [{**summary(), "body": "> quoted\n" + summary()["body"]}],
                         [{**summary(), "body": SUMMARY + "\n<!-- codex-review-state:v1 {} -->"}]):
            with self.subTest(comments=comments):
                self.assertEqual(review_result(HEAD, comments)[0], "pending")

    def test_review_requires_completed_head_with_no_outstanding_findings(self):
        self.assertEqual(review_result(HEAD, [summary()])[0], "success")
        self.assertEqual(review_result(HEAD, [summary(unresolved=True)])[0], "failure")
        self.assertEqual(review_result(HEAD, [summary(unresolved=None)])[0], "failure")
        rerun = summary(status="in_progress", updated="2026-11-28T00:01:00Z")
        self.assertEqual(review_result(HEAD, [rerun, summary()])[0], "pending")

    def test_publishes_against_pr_head_and_searches_all_comment_pages(self):
        pr = {"base": {"ref": "main"}, "head": {"sha": HEAD}, "title": "[feature][前端+后端] 从片尾续拍",
              "body": filled(), "draft": False, "html_url": URL}
        with patch("sys.argv", ["pr_policy.py", "7", "--publish"]), \
             patch("pr_policy.gh", side_effect=[pr, [[], [summary()]], {}]) as api:
            self.assertEqual(main(), 0)
        self.assertTrue(api.call_args_list[1].kwargs["paginate"])
        self.assertTrue(api.call_args.args[0].endswith("/statuses/" + HEAD))
        self.assertEqual(api.call_args.kwargs["payload"]["state"], "success")
        self.assertEqual(api.call_args.kwargs["payload"]["context"], CONTEXT)
