"""Regress synchronous Slate re-entry and Color property restoration."""
import runpy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class CaptureTests(unittest.TestCase):
    def test_capture_reentry_and_restore(self):
        calls = []
        comp = types.SimpleNamespace(intensity=5, light_color="original_color")
        comp.set_intensity = lambda value: calls.append(("intensity", value))
        comp.set_light_color = lambda value: calls.append(("linear", value))
        comp.set_editor_property = lambda key, value: calls.append((key, value))
        class Light:
            tags = []
            def get_component_by_class(self, cls):
                return comp
            def get_actor_rotation(self):
                return "original_rotation"
            def set_actor_rotation(self, *args):
                pass
        callback = []
        def capture(*args):
            calls.append(("capture", args))
            callback[0](0)
        fake = types.SimpleNamespace(
            DirectionalLight=Light, DirectionalLightComponent=object, EditorActorSubsystem=object,
            get_editor_subsystem=lambda cls: types.SimpleNamespace(get_all_level_actors=lambda: [Light()]),
            register_slate_post_tick_callback=lambda fn: callback.append(fn),
            unregister_slate_post_tick_callback=lambda handle: None,
            log=lambda message: None, log_error=lambda message: self.fail(message),
            Rotator=lambda **kwargs: kwargs, LinearColor=lambda *args: args,
            AutomationLibrary=types.SimpleNamespace(take_high_res_screenshot=capture))
        script = Path(__file__).resolve().parents[1] / "light_matrix_capture.py"
        if not script.exists():
            script = script.parent / "ue/python/light_matrix_capture.py"
        with patch.dict(sys.modules, {"unreal": fake}):
            namespace = runpy.run_path(str(script))
        runner = namespace["_runner"]
        runner.state, runner.wait = "shoot", 0
        runner.tick(0)
        self.assertEqual(runner.idx, 1)
        self.assertEqual(len([c for c in calls if c[0] == "capture"]), 1)
        runner.finish()
        runner.finish()
        self.assertIn(("light_color", "original_color"), calls)
        self.assertTrue(runner.finished)


if __name__ == "__main__":
    unittest.main()
