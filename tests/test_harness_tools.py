"""Tool edits use the same workflow model as the browser without changing a stored run."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from draw_studio.workflows.agent_plugins import inventory
from draw_studio.workflows.agent_tools import TOOLS, EditorTools, editor_revision
from draw_studio.workflows.definitions import normalize_workflow_def
from draw_studio.workflows.harness_errors import ERROR_DEFAULTS, HARNESS_ERROR_CODES, HarnessError
from tests.harness_fixture import local_runtime
from tests.http_fixture import png


def step(id, type, **config):
    return {"id": id, "type": type, "config": config}


def operation(op, **args):
    return {"op": op, **args}


def editor(*steps, run=False, status="draft"):
    workflow = normalize_workflow_def({"name": "Cut", "steps": list(steps)}) if steps else {"name": "Cut", "steps": []}
    snapshot = {"topic": "Moon", "workflow": workflow}
    record = {**snapshot, "status": status, "step_states": {}}
    runtime = SimpleNamespace(
        workflows=SimpleNamespace(get_run=lambda id: record),
        store=SimpleNamespace(list=lambda **kw: {"rounds": [{"id": "007", "kind": "image", "prompt": "Moon"}]}),
    )
    return EditorTools(runtime, snapshot, selected="script", run_id="wr_saved" if run else None)


class HarnessToolTests(unittest.TestCase):
    def edit(self, tools, *ops):
        return tools.call("studio_edit_workflow", {"operations": list(ops)})

    def config(self, tools, id):
        return next(st["config"] for st in tools.editor["workflow"]["steps"] if st["id"] == id)

    def assert_code(self, code, fn, *args):
        with self.assertRaises(HarnessError) as caught:
            fn(*args)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_add_step_repairs_only_inherited_connections(self):
        tools = editor()
        self.edit(tools, operation("add_step", step_type="image_gen", step_id="first"))
        self.assertEqual(self.config(tools, "first")["ref_sources"], [])
        self.assertEqual(self.config(tools, "first")["scenes_from"], "")

        tools = editor(step("character_assets", "asset_input"), step("web_refs", "llm_script"))
        self.edit(tools, operation("add_step", step_type="image_gen", step_id="image"))
        self.assertEqual(self.config(tools, "image")["ref_sources"], ["character_assets"])
        self.assertEqual(self.config(tools, "image")["scenes_from"], "web_refs")
        for ref in ("web_refs", "missing"):
            self.assert_code("invalid_argument", self.edit, tools, operation(
                "add_step", step_type="image_gen", step_id="invalid", config={"ref_sources": [ref]},
            ))

        tools = editor(step("another", "asset_input"))
        self.assert_code("invalid_argument", self.edit, tools, operation(
            "add_step", step_type="h3_prompt", step_id="h3", config={"extra_ref_sources": ["missing"]},
        ))
        self.edit(tools, operation("add_step", step_type="h3_prompt", step_id="h3",
                                   config={"extra_ref_sources": ["another"]}))
        self.assertEqual(self.config(tools, "h3")["extra_ref_sources"], ["another"])

    def test_video_edges_and_gallery_ids_have_different_types(self):
        tools = editor(step("script", "llm_script"), step("video", "video_gen"),
                       step("cut", "video_stitch", clips_from="video"))
        self.edit(tools, operation("add_step", step_type="h3_prompt", step_id="h3",
                                   config={"workflow": "ref2va", "video_from": "cut", "video_task": "continue",
                                           "last_frame_round_id": "005"}))
        self.assertEqual(self.config(tools, "h3")["video_from"], "cut")
        self.assert_code("invalid_argument", self.edit, tools,
                         operation("move_step", step_id="cut", after="h3"))
        self.assert_code("invalid_argument", self.edit, tools, operation(
            "update_step", step_id="h3", config={"video_from": "script"},
        ))
        self.assert_code("invalid_argument", self.edit, tools, operation(
            "update_step", step_id="h3", config={"video_round_id": "001"},
        ))
        self.edit(tools, operation("update_step", step_id="h3", config={"video_from": "", "video_round_id": "001"}))
        self.assertEqual(self.config(tools, "h3")["video_round_id"], "001")
        self.assertEqual(self.config(tools, "h3")["last_frame_round_id"], "005")
        for field, value in (("video_from", "003"), ("video_round_id", "video"),
                             ("last_frame_round_id", 5), ("video_task", "publish")):
            with self.subTest(field=field):
                self.assert_code("invalid_argument", self.edit, tools,
                                 operation("update_step", step_id="h3", config={field: value}))

    def test_all_edit_operations_and_atomic_rejection(self):
        tools = editor(step("script", "llm_script"), run=True)
        applied = self.edit(tools, operation("set_topic", text="New topic"), operation("rename_workflow", name="New cut"),
                            operation("set_variable", name="style", value="film"),
                            operation("set_variable", name="flag", value=False),
                            operation("add_step", step_type="video_gen", step_id="video", after="",
                                      position={"x": 12.4, "y": 8000}, config={"offload_mode": "group"}),
                            operation("update_step", step_id="script", config={"scene_count": 5.0}, pause_after=True),
                            operation("move_step", step_id="script", after=""),
                            operation("remove_variable", name="flag"))
        self.assertEqual(applied["step_ids"], ["script", "video"])
        self.assertEqual(applied["staged"], 8)
        self.assertEqual(tools.editor["topic"], "New topic")
        self.assertEqual(tools.editor["workflow"]["name"], "New cut")
        self.assertEqual(tools.editor["workflow"]["variables"], {"style": "film"})
        self.assertEqual(tools.editor["workflow"]["steps"][1]["position"], {"x": 12, "y": 8000})
        self.assertIs(type(self.config(tools, "script")["scene_count"]), int)
        self.assertEqual(self.config(tools, "video")["offload_mode"], "group")
        before = copy.deepcopy(tools.editor)
        self.assert_code("invalid_argument", self.edit, tools, operation("set_topic", text="Discard this"),
                         operation("update_step", step_id="video", config={"offload_mode": "unknown"}))
        self.assertEqual(tools.editor, before)
        self.edit(tools, operation("update_step", step_id="script", position={"x": 3, "y": 5}),
                  operation("remove_step", step_id="video"))
        self.assertEqual(tools.editor["workflow"]["steps"][0]["position"], {"x": 3, "y": 5})
        self.assert_code("invalid_argument", self.edit, tools, operation("remove_step", step_id="script"))

    def test_strict_validation_and_ranges(self):
        invalid = [
            ("llm_script", "scene_count", True), ("llm_script", "scene_count", 0),
            ("llm_script", "scene_count", 9), ("llm_script", "scene_count", 2.5),
            ("image_gen", "cfg", float("nan")), ("image_gen", "cfg", float("inf")),
            ("image_gen", "cfg", False), ("image_gen", "cfg", 13), ("image_gen", "width", 511),
            ("image_gen", "height", True), ("image_gen", "steps", 61), ("image_gen", "max_scenes", 0),
            ("image_gen", "gpu_pool", [123]), ("image_gen", "gpu_pool", ["imaginary"]),
            ("image_gen", "ref_sources", [None]), ("image_gen", "ref_sources", [""]),
            ("image_gen", "loras", [True]), ("image_gen", "loras", [{}]),
            ("image_gen", "loras", [{"repo_id": "owner/repo", "scale": True}]),
            ("image_gen", "loras", [{"repo_id": "owner/repo", "scale": float("inf")}]),
            ("image_gen", "loras", [{"repo_id": "owner/repo", "scale": 3}]),
            ("image_gen", "loras", [{"repo_id": "owner/repo"}] * 5),
            ("video_gen", "num_frames", 346), ("video_gen", "poll_rounds", 11),
            ("video_stitch", "fps", 11), ("video_stitch", "target_height", 9000),
            ("video_stitch", "fade_s", float("-inf")), ("video_stitch", "fade_s", .05),
            ("asset_input", "round_ids", [22]), ("video_stitch", "clip_round_ids", ["clip"]),
            ("web_asset_fetch", "max_images", 7),
        ]
        for kind, key, value in invalid:
            with self.subTest(key=key, value=value):
                tools = editor()
                self.assert_code("invalid_argument", self.edit, tools, operation(
                    "add_step", step_type=kind, step_id="new", config={key: value},
                ))
                self.assertEqual(tools.editor, tools.original)
        tools = editor(step("refs", "asset_input"))
        self.assert_code("invalid_argument", self.edit, tools, operation("update_step", step_id="refs", enabled=1))
        self.assert_code("invalid_argument", self.edit, tools, operation("update_step", step_id="refs",
                                                                         position={"x": True, "y": 1}))
        self.edit(tools, operation("update_step", step_id="refs", config={"round_ids": ["001", "000008"]}),
                  operation("add_step", step_id="image", step_type="image_gen",
                            config={"gpu_pool": ["A100", "h100"], "loras": [{"repo_id": "owner/repo", "scale": 1.2}]}))
        self.assertEqual(self.config(tools, "refs")["round_ids"], ["001", "000008"])
        self.assertEqual(self.config(tools, "image")["gpu_pool"], ["A100", "H100"])

    def test_legacy_bad_reference_can_be_edited_but_not_supplied_again(self):
        tools = editor(step("image", "image_gen", ref_sources=["missing"]))
        self.edit(tools, operation("rename_workflow", name="Retitle"))
        self.assert_code("invalid_argument", self.edit, tools, operation(
            "update_step", step_id="image", config={"ref_sources": ["missing"]},
        ))
        self.edit(tools, operation("update_step", step_id="image", config={"ref_sources": []}))
        self.assertEqual(self.config(tools, "image")["ref_sources"], [])

    def test_run_requests_are_rechecked_after_edits_and_before_delivery(self):
        tools = editor(step("script", "llm_script"), step("asset", "asset_input"), run=True)
        self.assertTrue(tools.call("studio_request_run", {"step_id": "script"})["requested"])
        self.assertEqual(tools.final_run_request(), {"step_id": "script", "single_step": False})
        self.assertTrue(tools.call("studio_request_run", {"step_id": "script", "single_step": True})["requested"])
        self.assertEqual(tools.final_run_request(), {"step_id": "script", "single_step": True})
        for op in (operation("update_step", step_id="script", enabled=False),
                   operation("remove_step", step_id="script")):
            with self.subTest(op=op):
                tools = editor(step("script", "llm_script"), step("asset", "asset_input"), run=True)
                request = tools.call("studio_request_run", {"step_id": "script", "single_step": False})
                self.assertTrue(request["requested"])
                self.assertFalse(tools.final_run_request()["single_step"])
                self.assertTrue(self.edit(tools, op)["run_request_invalidated"])
                self.assertIsNone(tools.final_run_request())
                self.assert_code("invalid_argument", tools.call, "studio_request_run", {"step_id": "script"})
        tools = editor(step("script", "llm_script"))
        tools.call("studio_request_run", {})
        self.assertEqual(tools.final_run_request(), {"step_id": "", "single_step": False})
        self.assertTrue(self.edit(tools, operation("update_step", step_id="script", enabled=False))["run_request_invalidated"])
        self.assertIsNone(tools.final_run_request())
        self.assert_code("invalid_argument", tools.call, "studio_request_run", {"step_id": "script"})

    def test_catalog_read_library_read_only_guard_and_limit(self):
        tools = editor(step("script", "llm_script"), run=True, status="running")
        self.assertEqual(tools.call("studio_read_workflow", {})["status"], "running")
        self.assertEqual(tools.call("studio_list_nodes", {"step_type": "video_gen"})["default_config"]["offload_mode"], "auto")
        self.assertEqual(tools.call("studio_find_assets", {"query": "Moon", "kind": "image"})[0]["id"], "007")
        self.assert_code("running_locked", self.edit, tools, operation("rename_workflow", name="Locked"))
        self.assert_code("running_locked", tools.call, "studio_request_run", {})
        for _ in range(27):
            tools.call("studio_read_workflow", {})
        self.assert_code("tool_limit_reached", tools.call, "studio_read_workflow", {})
        self.assertEqual(len(tools.calls), 32)
        self.assertEqual(tools.context()["selected_step"], "script")

    def test_revision_tracks_editable_fields_and_run_state(self):
        tools = editor(step("script", "llm_script"))
        snapshot = tools.editor
        self.assertEqual(editor_revision(snapshot), editor_revision({**snapshot, "logs": ["log"]}))
        self.assertNotEqual(editor_revision(snapshot), editor_revision({**snapshot, "status": "running"}))
        self.edit(tools, operation("set_variable", name="flag", value=True))
        self.assertNotEqual(editor_revision(tools.original), editor_revision(tools.editor))

    def test_error_contract_has_all_standard_codes(self):
        self.assertEqual(len(HARNESS_ERROR_CODES), 18)
        self.assertEqual(set(HARNESS_ERROR_CODES), set(ERROR_DEFAULTS))
        error = HarnessError("revision_conflict", details={"current_revision": "abc"})
        self.assertEqual(error.status, 409)
        self.assertEqual(error.body(), {"error": error.message, "code": "revision_conflict", "details": {"current_revision": "abc"}})
        self.assertEqual(error.event(), {"type": "error", "code": "revision_conflict", "message": error.message})
        self.assertEqual(HarnessError("model_error").status, 502)
        self.assertEqual(HarnessError("turn_timeout").status, 504)

    def test_registry_is_static_and_creative_only(self):
        expected = (
            "studio_read_context", "studio_get_catalog", "studio_list_templates", "studio_manage_template", "studio_list_runs",
            "studio_create_draft", "studio_read_workflow", "studio_list_nodes", "studio_edit_workflow", "studio_validate_workflow",
            "studio_manage_run_assets", "studio_read_shots", "studio_rewrite_prompt", "studio_apply_shot_edits", "studio_undo_change",
            "studio_request_run", "studio_run_status", "studio_find_assets", "studio_inspect_asset",
            "studio_edit_media", "studio_prepare_mask", "studio_references", "studio_library_actions",
            "studio_presets", "studio_generation", "studio_jobs",
        )
        self.assertEqual(tuple(TOOLS), expected)
        with tempfile.TemporaryDirectory() as tmp:
            labels = inventory(Path(tmp))["builtin_tools"]
        self.assertEqual(tuple(labels), expected)
        copy_source = (Path(__file__).resolve().parents[1] / "web/src/features/workflow/agentCopy.ts").read_text()
        for name, label in labels.items():
            self.assertIn(f"{name}: '{label}'", copy_source)

        tools = editor(step("script", "llm_script"))
        for name in ("studio_colab", "studio_hf_token", "studio_idle_timeout", "studio_proxy", "studio_llm_provider", "studio_purge"):
            self.assert_code("invalid_argument", tools.call, name, {})
        self.assertNotIn("idle", tools.call("studio_get_catalog", {"section": "limits"}))
        self.assert_code("invalid_argument", tools.call, "studio_get_catalog", {"section": "providers"})
        self.assert_code("invalid_argument", tools.call, "studio_list_runs", {"limit": True})
        self.assert_code("invalid_argument", tools.call, "studio_read_context", {"include_api_key": True})
        self.assert_code("invalid_argument", tools.call, "studio_find_assets", {"starred": 1})
        self.assert_code("invalid_argument", tools.call, "studio_find_assets", {"offset": -1})
        self.assert_code("invalid_argument", tools.call, "studio_find_assets", {"limit": 25})
        self.assert_code("invalid_argument", tools.call, "studio_inspect_asset", {"round_id": 7})
        self.assert_code("invalid_argument", tools.call, "studio_run_status", {"op": "cancel"})
        self.assert_code("invalid_argument", tools.call, "studio_create_draft", {"definition": {"steps": [step("refs", "asset_input", hf_token="no")]}})

    def test_context_preflight_templates_and_draft_idempotency(self):
        with tempfile.TemporaryDirectory() as tmp, local_runtime(Path(tmp)) as runtime:
            definition = {"name": "Cut", "variables": {"tone": "blue"}, "steps": [
                step("refs", "asset_input", asset_files=["missing.png"]),
                step("script", "llm_script", instruction="{{vars.palette}}"),
                step("prompts", "h3_prompt", scenes_from="script", video_from="missing"),
                step("clips", "video_gen", scenes_from="script", prompts_from="prompts", extra_ref_sources=["refs"]),
            ]}
            run = runtime.workflows.create_run({"workflow": definition, "topic": "Moon"})
            tools = EditorTools(runtime, run, run_id=run["id"], selected="script", selected_shot="sh_abcdef123456")
            context = tools.call("studio_read_context", {})
            self.assertEqual((context["workspace"], context["run_id"], context["selected_step"], context["selected_shot"]),
                             ("workflow", run["id"], "script", "sh_abcdef123456"))
            self.assertEqual(context["revision"], editor_revision(run))
            self.assertEqual(context["references"], {"image_count": 0, "first": False, "last": False, "video": False})
            preflight = tools.call("studio_validate_workflow", {})
            self.assertFalse(preflight["valid"])
            self.assertEqual(preflight["affected_steps"], ["refs", "script", "prompts", "clips"])
            self.assertIn({"code": "upstream_invalid", "step_id": "prompts", "field": "video_from", "source": "missing"}, preflight["issues"])
            self.assertIn({"code": "variable_missing", "step_id": "script", "variable": "palette"}, preflight["issues"])
            self.assertIn({"code": "media_invalid", "step_id": "refs", "field": "asset_files"}, preflight["issues"])
            self.assertEqual(runtime.workflows.get_run(run["id"])["status"], "draft")
            self.assert_code("invalid_argument", tools.call, "studio_manage_template", {"op": "delete", "template_id": "builtin:story-short"})

            definition["steps"][2]["config"]["video_from"] = ""
            runtime.workflows.update_run_config(run["id"], {"workflow": definition, "topic": "Last light"})
            self.assertEqual(tools.call("studio_read_workflow", {})["topic"], "Last light")
            tools = EditorTools(runtime, runtime.workflows.get_run(run["id"]), run_id=run["id"], selected="script")
            saved = tools.call("studio_manage_template", {"op": "save", "name": "Saved cut"})
            template_id = saved["template_id"]
            self.assertEqual(runtime.workflows.get_workflow(template_id)["steps"][0]["config"]["asset_files"], [])
            self.assertIn({"id": template_id, "name": "Saved cut", "description": "", "builtin": False, "step_count": 4},
                          tools.call("studio_list_templates", {}))
            args = {"template_id": template_id, "request_id": "f" * 32}
            draft = tools.call("studio_create_draft", args)
            self.assertEqual(tools.call("studio_create_draft", args), draft)
            self.assertEqual((draft["run_id"], draft["status"]), ("wr_" + "f" * 32, "draft"))
            self.assertEqual(sum(item["id"] == draft["run_id"] for item in tools.call("studio_list_runs", {})), 1)
            self.assertEqual(tools.call("studio_manage_template", {"op": "delete", "template_id": template_id}), {"deleted": template_id})

    def test_run_assets_gallery_whitelist_and_incremental_logs(self):
        with tempfile.TemporaryDirectory() as tmp, local_runtime(Path(tmp)) as runtime:
            wf = {"name": "Cut", "steps": [step("refs", "asset_input")]}
            run = runtime.workflows.create_run({"workflow": wf})
            rid = run["id"]
            uploaded = runtime.workflows.upload_asset(rid, png(), step_id="refs")
            original = runtime.workflows.get_run(rid)
            tools = EditorTools(runtime, original, run_id=rid, selected="refs", revision=editor_revision(original))
            first, second = "007", "008"
            for gallery_id in (first, second):
                (runtime.store.rounds / (gallery_id + ".png")).write_bytes(png((24, 12)))
                (runtime.store.rounds / (gallery_id + ".json")).write_text(json.dumps({"prompt": "Evening light", "steps": 30,
                    "starred": True, "source_rounds": ["003", 4], "api_key": "SECRET", "cookie": "SECRET"}))
            self.assertEqual(tools.call("studio_find_assets", {"query": "evening", "kind": "image", "starred": True,
                                                                 "offset": 1, "limit": 1})[0]["id"], first)
            asset = tools.call("studio_inspect_asset", {"round_id": first})
            self.assertEqual((asset["id"], asset["width"], asset["height"], asset["steps"], asset["source_rounds"]),
                             (first, 24, 12, 30, ["003"]))
            self.assertNotIn("SECRET", json.dumps(asset))
            self.assert_code("media_invalid", tools.call, "studio_manage_run_assets", {"op": "bind_rounds", "round_ids": ["009"]})
            tool = "studio_manage_run_assets"
            self.assertEqual(tools.call(tool, {"op": "bind_rounds", "round_ids": [first, first]})["round_ids"], [first])
            record = runtime.workflows.get_run(rid)
            self.assertEqual(tools.revision, editor_revision(record))
            self.assertEqual(tools.editor, tools.original)
            self.assertEqual(tools.call(tool, {"op": "list"})["assets"][0]["filename"], uploaded["filename"])
            self.assertEqual(tools.call(tool, {"op": "remove", "round_ids": [first]})["round_ids"], [])
            self.assertEqual(tools.call(tool, {"op": "remove", "filename": uploaded["filename"]}), {"assets": []})
            self.assertIsNotNone(runtime.store.media_path(first))
            self.assert_code("not_found", tools.call, tool, {"op": "remove", "filename": "../007.png"})

            engine = runtime.workflows
            with engine.shot_run(rid, write=True) as current, patch.object(engine, "log"):
                current["status"] = "paused"
                for n in range(250):
                    engine._append_log_locked(current, f"Step {n}")
                engine._write_run_locked(current)
            status = tools.call("studio_run_status", {"op": "watch", "log_offset": 249})
            self.assertEqual(status["next_log_offset"], 251)
            self.assertTrue(status["logs"][0].endswith("Step 248"))
            self.assert_code("invalid_argument", tools.call, "studio_run_status", {"op": "cancel"})
            canceled = tools.call("studio_run_status", {"op": "cancel", "run_id": rid})
            self.assertEqual(canceled["status"], "canceled")
            after = tools.call("studio_run_status", {"op": "watch", "log_offset": status["next_log_offset"]})
            self.assertEqual(len(after["logs"]), 1)

    def test_composer_proposal_and_shot_parameter_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp, local_runtime(Path(tmp)) as runtime:
            snapshot = {"workflow": {"name": "Cut", "steps": []}, "topic": ""}
            composer = {"prompt": "A street flooded with cool light", "model": "image-model", "num_frames": 129}
            tools = EditorTools(runtime, snapshot, workspace="video", composer=composer)
            self.assertEqual(tools.call("studio_read_context", {})["composer"], composer)
            provider = SimpleNamespace(id="fixture", key="secret")
            with patch.object(runtime.studio.llm, "resolve", return_value=(provider, "test")), \
                 patch.object(runtime.studio, "write_prompt_rich", return_value={"prompt": "New shot"}) as writer:
                proposal = tools.call("studio_rewrite_prompt", {"instruction": "Warmer light"})
            self.assertEqual((proposal["kind"], proposal["before"][0]["n"], proposal["after"][0]["text"]), ("composer", 0, "New shot"))
            self.assertEqual(writer.call_args.kwargs["mode"], "video")
            self.assertEqual(runtime.harness_store.get_proposal(proposal["proposal_id"]), proposal)
            self.assert_code("approval_required", tools.call, "studio_apply_shot_edits", {"proposal_id": proposal["proposal_id"]})
            other = EditorTools(runtime, snapshot)
            self.assert_code("not_found", other.call, "studio_apply_shot_edits", {"proposal_id": proposal["proposal_id"]})
            self.assert_code("invalid_argument", tools.call, "studio_rewrite_prompt", {"target": "composer", "instruction": "x", "field": "video_prompt"})
            edit = {"shot_id": "sh_abcdef123456", "field": "keyframe_prompt", "generation": True, "expected_version": 1, "value": "x"}
            self.assert_code("invalid_argument", tools.call, "studio_apply_shot_edits", {"run_id": "wr_other", "step_id": "script", "edits": [edit]})

    def test_media_tools_and_library_scope(self):
        from tests.http_fixture import mp4

        with tempfile.TemporaryDirectory() as tmp, local_runtime(Path(tmp)) as runtime:
            tools = EditorTools(runtime, {"topic": "", "workflow": {"name": "Cut", "steps": []}})
            picture = Path(tmp) / "source.png"
            picture.write_bytes(png((64, 48)))
            rid = runtime.store.save(picture, "image", {})
            clip = runtime.store.save(mp4(Path(tmp) / "source.mp4", 3, audio=True), "video", {})
            crop = {"op": "crop", "round_id": rid, "x": 4, "y": 6, "width": 20, "height": 16}
            result = tools.call("studio_edit_media", crop)["round_id"]
            asset = runtime.store.get(result)
            self.assertEqual((asset["width"], asset["height"], asset["source_rounds"]), (20, 16, [rid]))
            self.assert_code("media_invalid", tools.call, "studio_edit_media", {**crop, "width": 1000})
            self.assert_code("invalid_argument", tools.call, "studio_edit_media", {**crop, "x": True})
            self.assert_code("media_invalid", tools.call, "studio_edit_media", {**crop, "round_id": clip})

            framed = tools.call("studio_edit_media", {"op": "extract_frame", "round_id": clip, "time_s": 1})["round_id"]
            self.assertEqual(runtime.store.get(framed)["source_rounds"], [clip])
            cut = tools.call("studio_edit_media", {"op": "clip_video", "round_id": clip, "start_s": .5, "end_s": 2.5, "mute": True})
            self.assertEqual(runtime.store.get(cut["round_id"])["media_duration_s"], 2)
            self.assert_code("media_invalid", tools.call, "studio_edit_media", {"op": "extract_frame", "round_id": clip, "time_s": 9})

            name = "studio_library_actions"
            self.assertTrue(tools.call(name, {"op": "star", "round_id": rid})["starred"])
            self.assertEqual(tools.call(name, {"op": "trash", "round_id": rid})["state"], "trashed")
            self.assertEqual(tools.call(name, {"op": "list_trash"})["rounds"][0]["id"], rid)
            self.assert_code("invalid_argument", tools.call, name, {"op": "purge", "round_id": rid})
            self.assert_code("invalid_argument", tools.call, name, {"op": "trash", "round_id": rid, "permanent": True})
            self.assertEqual(tools.call(name, {"op": "restore", "round_id": rid})["state"], "restored")
            self.assertTrue(runtime.store.get(rid)["starred"])

    def test_reference_order_masks_presets_and_composer_patch(self):
        with tempfile.TemporaryDirectory() as tmp, local_runtime(Path(tmp)) as runtime:
            source = Path(tmp) / "source.png"
            source.write_bytes(png((24, 16)))
            first, second, third = [runtime.store.save(source, "image", {}) for _ in range(3)]
            tools = EditorTools(runtime, {"topic": "", "workflow": {"name": "Cut", "steps": []}},
                                workspace="image", composer={"prompt": "Fog", "revision": "a" * 32})
            ref = "studio_references"
            def bind(rid, **fields):
                return tools.call(ref, {"op": "use_round", "slot": "first", "round_id": rid, **fields})
            bind(first)
            after = bind(second, append=True)
            a, b = [item["id"] for item in after["items"]]
            replaced = bind(third, reference_id=a)
            self.assertEqual([(item["id"], item["source"]) for item in replaced["items"]], [(a, "round:" + third), (b, "round:" + second)])
            removed = tools.call(ref, {"op": "remove", "slot": "first", "reference_id": a})
            self.assertEqual(removed["items"][0]["id"], b)
            tools.call(ref, {"op": "use_round", "slot": "last", "round_id": first})
            self.assertTrue(tools.call(ref, {"op": "read"})["last"]["set"])
            self.assertFalse(tools.call(ref, {"op": "clear", "slot": "last"})["last"]["set"])

            hint = tools.call("studio_prepare_mask", {"source_id": third})["mask_editor"]
            self.assertEqual(hint, {"source_id": third, "mask_id": None})
            self.assert_code("invalid_argument", tools.call, "studio_prepare_mask",
                             {"source_id": third, "strokes": [{"size": True, "points": [[0, .5]]}]})
            strokes = [{"size": .1, "points": [[.3, .4]]}]
            mask = tools.call("studio_prepare_mask", {"source_id": third, "strokes": strokes})
            self.assertEqual(tools.mask_editor["mask_id"], mask["mask_id"])
            self.assertEqual(runtime.operations.get_mask(mask["mask_id"])["source_id"], third)

            preset = "studio_presets"
            parsed = tools.call(preset, {"op": "parse_comfy_link", "url": "org/repo :: weights/main.gguf"})
            self.assertEqual(parsed["spec"]["basename"], "main.gguf")
            sp = tools.call(preset, {"op": "save", "preset": {"name": "Preview", "width": 1024}})["preset"]
            self.assertEqual(tools.call(preset, {"op": "list"})["custom"][0]["id"], sp["id"])
            cp = tools.call(preset, {"op": "save", "kind": "comfy", "preset": {"name": "Comfy", "comfy": {
                "diffusion": "test/weights:q.gguf"}}})["preset"]
            self.assertEqual(tools.call(preset, {"op": "list", "kind": "comfy"})["custom"][0]["id"], cp["id"])
            self.assertEqual(tools.call(preset, {"op": "delete", "kind": "comfy", "preset_id": cp["id"]})["deleted"], cp["id"])
            self.assert_code("invalid_argument", tools.call, preset, {"op": "delete", "preset_id": "builtin:qwen"})
            self.assert_code("invalid_argument", tools.call, preset, {"op": "save", "preset": {"name": "Infra", "idle_minutes": 5}})
            patch_result = tools.call("studio_generation", {"op": "edit_composer", "spec": {"width": 1000, "mask_id": mask["mask_id"]}})
            self.assertEqual(patch_result["composer_patch"]["changes"]["width"], 1024)
            self.assertEqual(patch_result["composer_patch"]["base_revision"], "a" * 32)
            prepared = tools.call("studio_generation", {"op": "prepare"})
            self.assertEqual(prepared["references"], {"images": 1, "last": False, "video": False, "mask": True})
            self.assert_code("invalid_argument", tools.call, "studio_generation", {"op": "edit_composer",
                             "spec": {"workflow": "ref2va"}})
            self.assert_code("invalid_argument", tools.call, "studio_generation", {"op": "submit_video", "idempotency_key": "z",
                             "spec": {"model": "MiniMax-H3", "prompt": "Fog"}})
            self.assert_code("invalid_argument", tools.call, "studio_generation", {"op": "submit_image", "idempotency_key": "z",
                             "spec": {"poll_all_proxies": True}})
            self.assertFalse(runtime.studio.snapshot()["queue"])
