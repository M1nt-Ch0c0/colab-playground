"""Check PR metadata and the Codex review of the current head. Uses the authenticated gh CLI."""
import argparse
import json
import os
import re
import subprocess
import sys

TYPES = {"feature", "bug"}
SCOPES = {"前端", "后端", "文档", "构建/部署"}
SECTIONS = ("类型、范围与目的", "具体改动", "验证与证据", "兼容与发布")
BOT_ID = 199175422  # chatgpt-codex-connector[bot] on github.com
SUMMARY = "<!-- codex-pull-request-review-summary -->"
CONTEXT = "PR policy"
REPO = "repos/{owner}/{repo}"  # gh expands these placeholders from the current checkout.


def parse_body(body):
    sections = {}
    choices = []
    current = None
    fence = ""
    for line in re.sub(r"<!--.*?(?:-->|\Z)", "", body, flags=re.S).splitlines():
        value = line.strip()
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fence:
            if value.startswith(fence) and not value.strip(fence[0]):
                fence = ""
            elif current in SECTIONS and value:
                sections[current].append("code")  # Counts as evidence without interpreting example Markdown.
            continue
        if marker:
            fence = marker[1]
            continue
        if value.startswith("## "):
            current = value[3:].strip()
            if current in SECTIONS:
                sections.setdefault(current, [])
            continue
        if current not in SECTIONS:
            continue
        if current == SECTIONS[0]:
            box = re.fullmatch(r"[-*] \[([ xX])\]\s+(.+)", value)
            if box:
                if box[1].lower() == "x":
                    choices.append(box[2].strip())
                continue
            if value in {"类型（单选）", "范围（可多选）"}:
                continue
        if current == SECTIONS[1] and value.startswith("### "):
            sections[current].append(value)
        elif not value.startswith("#") and re.search(r"\w", value):
            sections[current].append(value)
    return sections, choices


def description_errors(title, body):
    errors = []
    match = re.fullmatch(r"\[(feature|bug)\]\[([^]\r\n]+)\]\s+(\S.*)", title.strip())
    title_scopes = match[2].split("+") if match else []
    if not match or not set(title_scopes) <= SCOPES or len(title_scopes) != len(set(title_scopes)):
        errors.append("标题请使用 [feature或bug][范围] 具体行为变化，多范围用 + 连接")

    sections, choices = parse_body(body or "")
    if list(sections) not in (list(SECTIONS), list(SECTIONS[:3])):
        errors.append("请按模板顺序填写前三个板块，兼容与发布按需填写")
    for name in SECTIONS[:3]:
        if name in sections and not sections[name]:
            errors.append(f"请填写「{name}」的具体内容")
    kinds = TYPES.intersection(choices)
    scopes = SCOPES.intersection(choices)
    if len(kinds) != 1 or not scopes or len(kinds) + len(scopes) != len(choices):
        errors.append("正文请勾选一个类型和至少一个范围，每项只选一次")
    elif match and (kinds != {match[1]} or scopes != set(title_scopes)):
        errors.append("正文勾选的类型和范围须与标题一致")
    if sections.get(SECTIONS[1]):
        missing = scopes - described_scopes(sections[SECTIONS[1]])
        if missing:
            errors.append("请在「具体改动」中按范围填写实际变化：" + "、".join(sorted(missing)))
    return errors


def described_scopes(lines):
    filled = set()
    scope = None
    for line in lines:
        if line.startswith("### "):
            scope = line[4:].strip()
            continue
        label = re.match(r"^(?:[-*]\s+)?\*\*([^*]+)\*\*\s*[：:]?\s*", line)
        if label and label[1] in SCOPES:
            scope = label[1]
            line = line[label.end():]
        if scope in SCOPES and re.search(r"\w", line):
            filled.add(scope)
    return filled


def review_result(head, comments):
    reports = [c for c in comments if (c.get("user") or {}).get("id") == BOT_ID
               and (c.get("body") or "").startswith(SUMMARY)]
    if not reports:
        return "pending", "等待 Codex 发布当前提交的评审报告", None
    latest = max(reports, key=lambda c: (c["updated_at"], c["id"]))
    link = latest["html_url"]
    marker = re.search(r"<!--\s*codex-review-state:v1\s+(.+?)\s*-->", latest["body"], flags=re.S)
    try:
        report = json.loads(marker[1])["code_review"] if marker else {}
    except (ValueError, TypeError, KeyError):
        report = {}
    if not isinstance(report, dict) or report.get("commit_sha") != head:
        return "pending", "等待与当前提交 SHA 匹配的 Codex 评审", link
    if report.get("status") != "completed":
        return "pending", "当前提交的 Codex 评审尚未完成", link
    if report.get("has_unresolved_findings") is not False:
        return "failure", "请处理评审报告中的意见并复核当前提交", link
    return "success", "PR 说明已填写，当前提交的 Codex 评审已完成", link


def gh(endpoint, *, paginate=False, payload=None):
    args = ["gh", "api", endpoint]
    if paginate:
        args.extend(["--paginate", "--slurp"])
    data = None
    if payload is not None:
        args.extend(["--method", "POST", "--input", "-"])
        data = json.dumps(payload)
    return json.loads(subprocess.check_output(args, input=data, text=True))


def publish(head, state, message, details_url):
    gh(f"{REPO}/statuses/{head}", payload={
        "context": CONTEXT, "state": state, "description": message[:140], "target_url": details_url,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("number", type=int, help="GitHub pull request number")
    parser.add_argument("--publish", action="store_true", help="publish the outcome as a commit status")
    args = parser.parse_args()
    if args.number < 1:
        parser.error("PR 编号必须为正整数")
    pr = gh(f"{REPO}/pulls/{args.number}")
    if pr["base"]["ref"] != "main":
        print("此检查适用于目标分支为 main 的 PR")
        return 0

    head = pr["head"]["sha"]
    details_url = pr["html_url"]
    if os.environ.get("GITHUB_RUN_ID"):
        details_url = f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    errors = description_errors(pr["title"], pr["body"])
    if errors:
        state, message = "failure", errors[0]
        print("\n".join(errors))
    elif pr["draft"]:
        state, message = "pending", "等待草稿进入评审"
    else:
        try:
            pages = gh(f"{REPO}/issues/{args.number}/comments?per_page=100", paginate=True)
        except (OSError, subprocess.CalledProcessError, ValueError):
            if args.publish:
                publish(head, "error", "无法读取评审，请重新运行检查", details_url)
            raise
        state, message, report_url = review_result(head, [c for page in pages for c in page])
        if report_url:
            print(report_url)
    print(f"PR #{args.number} {head} {state} — {message}")
    if args.publish:
        publish(head, state, message, details_url)
        return 0
    return {"success": 0, "failure": 1, "pending": 2}[state]


if __name__ == "__main__":
    sys.exit(main())
