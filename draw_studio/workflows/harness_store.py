"""Private SQLite records for workflow shots, proposals, undo, and tool metrics."""
from __future__ import annotations

import json
import math
import os
import re
import secrets
import sqlite3
import threading
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path

from .agent_plugins import private_dir, profile_home

SHOT_ID = re.compile(r"sh_[a-f0-9]{12}")
SHOT_LISTS = {"llm_script": "scenes", "h3_prompt": "items"}
SHOT_FIELDS = {
    "llm_script": ("keyframe_prompt", "video_prompt", "audio_notes", "search_query", "prompt"),
    "h3_prompt": ("video_prompt", "prompt"),
}
PROPOSAL_TTL = UNDO_TTL = 86400
TELEMETRY_TTL = 30 * 86400
TELEMETRY_MAX = 20_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS shots (
    run_id TEXT NOT NULL, step_id TEXT NOT NULL, shot_id TEXT PRIMARY KEY,
    generation INTEGER NOT NULL, seq INTEGER NOT NULL, title TEXT NOT NULL,
    fields_json TEXT NOT NULL, field_versions_json TEXT NOT NULL, updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS shots_step ON shots (run_id, step_id, seq);
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT PRIMARY KEY, scope_key TEXT NOT NULL, kind TEXT NOT NULL, run_id TEXT, step_id TEXT,
    target_json TEXT NOT NULL, readset_json TEXT NOT NULL, writeset_json TEXT NOT NULL,
    before_json TEXT NOT NULL, after_json TEXT NOT NULL, refs_json TEXT NOT NULL,
    model TEXT NOT NULL, status TEXT NOT NULL, undo_id TEXT, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS proposals_undo ON proposals (undo_id);
CREATE TABLE IF NOT EXISTS masks (
    mask_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, strokes_json TEXT NOT NULL,
    created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS operations (
    operation_id TEXT PRIMARY KEY, scope_key TEXT NOT NULL, tool TEXT NOT NULL, idempotency_key TEXT NOT NULL,
    spec_hash TEXT NOT NULL, state TEXT NOT NULL, spec_json TEXT NOT NULL, frozen_refs_json TEXT NOT NULL,
    executor_ids_json TEXT NOT NULL, result_json TEXT NOT NULL, error_code TEXT, error_detail TEXT,
    created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
    UNIQUE(scope_key, tool, idempotency_key)
);
CREATE INDEX IF NOT EXISTS operations_scope ON operations (scope_key, created_at DESC);
CREATE TABLE IF NOT EXISTS operation_items (
    operation_id TEXT NOT NULL, item_key TEXT NOT NULL, seq INTEGER NOT NULL, frozen_input_json TEXT NOT NULL,
    job_id TEXT, state TEXT NOT NULL, round_id TEXT, error TEXT, updated_at INTEGER NOT NULL,
    PRIMARY KEY(operation_id, item_key)
);
CREATE UNIQUE INDEX IF NOT EXISTS operation_job ON operation_items (job_id) WHERE job_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS undo_records (
    undo_id TEXT PRIMARY KEY, scope_key TEXT NOT NULL, run_id TEXT NOT NULL, step_id TEXT NOT NULL,
    inverse_json TEXT NOT NULL, expected_versions_json TEXT NOT NULL,
    consumed INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS tool_telemetry (
    id INTEGER PRIMARY KEY AUTOINCREMENT, turn_id TEXT NOT NULL, conversation_key TEXT NOT NULL,
    call_seq INTEGER NOT NULL, model TEXT NOT NULL, tool_name TEXT NOT NULL, op TEXT, ok INTEGER NOT NULL,
    error_code TEXT, retry_in_turn INTEGER NOT NULL, latency_ms INTEGER NOT NULL,
    cache_hit_tokens INTEGER NOT NULL DEFAULT 0, cache_miss_tokens INTEGER NOT NULL DEFAULT 0,
    proposal_outcome TEXT, created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS telemetry_created ON tool_telemetry (created_at);
"""


def dump(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def shot_seq(row, position):
    value = row.get("scene_index", row.get("index"))
    return value if type(value) is int and value > 0 else position


def stamp_shots(state, step_type, *, previous=None, replace=False):
    """Give the JSON checkpoint server-owned identities and field versions."""
    key = SHOT_LISTS[step_type]
    output = state.get("output") or {}
    rows = output.get(key)
    generation = state.get("shot_generation", 0)
    if type(generation) is not int or generation < 0:
        generation = 0
    if replace:
        generation += 1
    elif isinstance(rows, list) and generation == 0 and rows:
        generation = 1
    if generation:
        state["shot_generation"] = generation
    if not isinstance(rows, list) or not rows:
        return
    edits = replace or previous is not None
    old = {row["shot_id"]: row for row in previous or () if isinstance(row, dict) and "shot_id" in row}
    used = set()
    for pos, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        sid = row.get("shot_id")
        prior = None
        if not replace and previous is not None:
            if isinstance(sid, str) and sid in old:
                prior = old[sid]
            elif not sid and pos < len(previous) and isinstance(previous[pos], dict):
                prior = previous[pos]
            sid = prior.get("shot_id") if prior else None
        if replace or not isinstance(sid, str) or not SHOT_ID.fullmatch(sid) or sid in used:
            sid = "sh_" + secrets.token_hex(6)
            prior = None
        used.add(sid)
        versions = prior.get("field_versions", {}) if prior else row.get("field_versions", {}) if not edits else {}
        versions = versions if isinstance(versions, dict) else {}
        row.update(shot_id=sid, generation=generation, field_versions={
            field: (versions[field] if type(versions.get(field)) is int and versions[field] > 0 else 1)
                   + int(prior is not None and row.get(field, "") != prior.get(field, ""))
            for field in SHOT_FIELDS[step_type]
        })


class HarnessStore:
    def __init__(self, root: Path):
        folder = profile_home(root)
        folder.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        private_dir(folder)
        self.path = folder / "state.sqlite3"
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            os.fchmod(fd, 0o600)
        finally:
            os.close(fd)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.executescript(SCHEMA)
        except BaseException:
            self.db.close()
            raise

    @contextmanager
    def transaction(self):
        with self.lock, self.db:
            yield self.db

    def close(self):
        with self.lock:
            self.db.close()

    def sync_shots(self, run_id, step_id, state, step_type):
        """Reconcile the workflow checkpoint and SQLite using per-field monotonic versions.

        The engine holds its run lock. Generation/identity comes from run.json.
        Within that generation the newer field version wins after a partial write.
        """
        key = SHOT_LISTS[step_type]
        rows = (state.get("output") or {}).get(key)
        if not isinstance(rows, list) and not state.get("shot_generation"):
            return False
        before = dump(rows)
        had_generation = state.get("shot_generation")
        stamp_shots(state, step_type)
        shot_rows = rows if isinstance(rows, list) else ()
        with self.transaction() as db:
            stored = {row["shot_id"]: row for row in db.execute(
                "SELECT * FROM shots WHERE run_id=? AND step_id=?", (run_id, step_id),
            )}
            seen = set()
            for position, row in enumerate(shot_rows, 1):
                if not isinstance(row, dict):
                    continue
                sid, generation, versions = row["shot_id"], row["generation"], row["field_versions"]
                fields = {field: row.get(field, "") for field in versions}
                persisted = stored.get(sid)
                if persisted and persisted["generation"] == generation:
                    old_fields = json.loads(persisted["fields_json"])
                    for field, version in json.loads(persisted["field_versions_json"]).items():
                        if field in versions and version > versions[field]:
                            row[field] = fields[field] = old_fields[field]
                            versions[field] = version
                record = (generation, shot_seq(row, position), str(row.get("title") or ""), dump(fields), dump(versions))
                if persisted is None:
                    while db.execute("SELECT 1 FROM shots WHERE shot_id=?", (sid,)).fetchone():
                        sid = row["shot_id"] = "sh_" + secrets.token_hex(6)
                    db.execute("INSERT INTO shots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (run_id, step_id, sid, *record, int(time.time())))
                elif record != tuple(persisted[k] for k in ("generation", "seq", "title", "fields_json", "field_versions_json")):
                    db.execute("""UPDATE shots SET generation=?, seq=?, title=?, fields_json=?, field_versions_json=?, updated_at=?
                                  WHERE shot_id=?""", (*record, int(time.time()), sid))
                seen.add(sid)
            db.executemany("DELETE FROM shots WHERE shot_id=?", ((sid,) for sid in stored.keys() - seen))
        return had_generation != state.get("shot_generation") or before != dump(rows)

    def clear_shots(self, run_id, step_ids=None):
        with self.transaction() as db:
            if step_ids is None:
                db.execute("DELETE FROM shots WHERE run_id=?", (run_id,))
            else:
                db.executemany("DELETE FROM shots WHERE run_id=? AND step_id=?", ((run_id, step) for step in step_ids))

    @staticmethod
    def store_fields(db, row):
        versions = row["field_versions"]
        fields = {field: row.get(field, "") for field in versions}
        db.execute("UPDATE shots SET fields_json=?, field_versions_json=?, updated_at=? WHERE shot_id=?",
                   (dump(fields), dump(versions), int(time.time()), row["shot_id"]))

    def save_proposal(self, proposal):
        with self.transaction() as db:
            db.execute("""INSERT INTO proposals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
                proposal["proposal_id"], proposal["scope_key"], proposal["kind"], proposal["run_id"], proposal["step_id"],
                dump(proposal["target"]), dump(proposal["readset"]), dump(proposal["writeset"]),
                dump(proposal["before"]), dump(proposal["after"]), dump(proposal["references_used"]),
                proposal["model"], proposal["status"], proposal["undo_id"], proposal["created_at"], proposal["expires_at"],
            ))

    @staticmethod
    def decode_proposal(row):
        if row is None:
            return None
        proposal = {key: row[key] for key in row.keys() if not key.endswith("_json")}
        for key in ("target", "readset", "writeset", "before", "after"):
            proposal[key] = json.loads(row[key + "_json"])
        proposal["references_used"] = json.loads(row["refs_json"])
        return proposal

    @classmethod
    def read_proposal(cls, db, proposal_id):
        return cls.decode_proposal(db.execute("SELECT * FROM proposals WHERE proposal_id=?", (proposal_id,)).fetchone())

    def get_proposal(self, proposal_id):
        with self.transaction() as db:
            return self.read_proposal(db, proposal_id)

    @staticmethod
    def public_proposal(proposal):
        target = proposal["target"]
        public = {**proposal, "target": {key: value for key, value in target.items() if key not in ("telemetry", "applied")}}
        if proposal["status"] == "pending" and proposal["expires_at"] <= time.time():
            public["status"] = "expired"
        return public

    @staticmethod
    def proposal_status(db, proposal, status, *, undo_id=None):
        db.execute("UPDATE proposals SET status=?, undo_id=?, target_json=? WHERE proposal_id=?",
                   (status, undo_id, dump(proposal["target"]), proposal["proposal_id"]))
        proposal.update(status=status, undo_id=undo_id)
        if link := proposal["target"].get("telemetry"):
            db.execute("UPDATE tool_telemetry SET proposal_outcome=? WHERE id=?", (status, link))

    def tool_metric(self, *, turn_id, conversation_key, call_seq, model, tool_name, op, ok, error_code,
                    retry_in_turn, latency_ms, proposal_id=None):
        with self.transaction() as db:
            proposal = self.read_proposal(db, proposal_id) if proposal_id else None
            cursor = db.execute("""INSERT INTO tool_telemetry
                (turn_id, conversation_key, call_seq, model, tool_name, op, ok, error_code, retry_in_turn,
                latency_ms, proposal_outcome, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (turn_id, conversation_key, call_seq, model, tool_name, op, int(ok), error_code, retry_in_turn,
                 latency_ms, proposal["status"] if proposal else None, int(time.time())))
            if proposal:
                proposal["target"]["telemetry"] = cursor.lastrowid
                db.execute("UPDATE proposals SET target_json=? WHERE proposal_id=?",
                           (dump(proposal["target"]), proposal_id))
            return cursor.lastrowid

    def tool_usage(self, metric_id, hit, miss):
        with self.transaction() as db:
            db.execute("""UPDATE tool_telemetry SET cache_hit_tokens=?, cache_miss_tokens=?
                          WHERE id=?""", (hit, miss, metric_id))

    def prune_telemetry(self):
        with self.transaction() as db:
            db.execute("DELETE FROM tool_telemetry WHERE created_at < ?", (int(time.time()) - TELEMETRY_TTL,))
            db.execute("DELETE FROM tool_telemetry WHERE id IN (SELECT id FROM tool_telemetry ORDER BY id DESC LIMIT -1 OFFSET ?)",
                       (TELEMETRY_MAX,))

    def telemetry(self):
        with self.transaction() as db:
            rows = db.execute("""SELECT tool_name, ok, error_code, retry_in_turn, latency_ms, cache_hit_tokens,
                               cache_miss_tokens, proposal_outcome FROM tool_telemetry WHERE created_at >= ?
                               ORDER BY id DESC LIMIT ?""", (int(time.time()) - TELEMETRY_TTL, TELEMETRY_MAX)).fetchall()
        groups = defaultdict(list)
        errors, outcomes = Counter(), Counter()
        for row in rows:
            groups[row["tool_name"]].append(row)
            if row["error_code"]:
                errors[row["error_code"]] += 1
            if row["proposal_outcome"]:
                outcomes[row["proposal_outcome"]] += 1

        def summary(records):
            count = len(records)
            times = sorted(entry["latency_ms"] for entry in records)
            return {"total": count, "success_rate": sum(entry["ok"] for entry in records) / count if count else 0,
                    "p50_ms": times[math.ceil(count * .50) - 1] if count else 0,
                    "p95_ms": times[math.ceil(count * .95) - 1] if count else 0,
                    "retries": sum(entry["retry_in_turn"] for entry in records)}
        adopted = outcomes["applied"] + outcomes["undone"]
        decided = adopted + outcomes["rejected"]
        return {**summary(rows), "by_tool": {name: summary(group) for name, group in sorted(groups.items())},
                "by_error": dict(errors), "cache_hit_tokens": sum(row["cache_hit_tokens"] for row in rows),
                "cache_miss_tokens": sum(row["cache_miss_tokens"] for row in rows), "proposal_outcomes": dict(outcomes),
                "proposal_adoption_rate": adopted / decided if decided else 0}
