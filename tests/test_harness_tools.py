"""Tool edits use the same workflow model as the browser without changing a stored run."""
import copy
import unittest
from types import SimpleNamespace

from draw_studio.workflows.agent_tools import EditorTools, editor_revision
from draw_studio.workflows.definitions import normalize_workflow_def
from draw_studio.workflows.harness_errors import ERROR_DEFAULTS, HARNESS_ERROR_CODES, HarnessError


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
