"""Offline regression checks; all model calls are replaced before imports."""

import contextlib
import importlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def no_model_calls(*args, **kwargs):
    raise AssertionError("A real model call is not allowed in these tests")


def parse_json(text, default_value=None):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return default_value


offline_llm = types.ModuleType("llm_client")
offline_llm.get_completion = no_model_calls
offline_llm.parse_json_response = parse_json
with patch.dict(sys.modules, {"llm_client": offline_llm}):
    simulation = importlib.import_module("simulation")
    runner = importlib.import_module("runner")

from simulator_prompts import (
    DEFAULT_SIMULATOR_VERSION, PAPER_V1_PROMPT, V2_PROMPT,
    get_simulator_prompt, simulator_prompt_metadata,
)

USER = {"base_profile": {"name": "Test user"}, "memory_bank": {"assistance_preference": []}}


class SimulatorVersionsTest(unittest.TestCase):
    def setUp(self):
        self.load_user = patch.object(simulation, "load_user", return_value=USER)
        self.load_user.start()
        self.addCleanup(self.load_user.stop)

    def respond(self, simulator):
        return simulator.respond("Review my draft", "Please paste your draft", [], 1)

    def test_original_prompt_is_preserved_exactly(self):
        self.assertEqual(
            simulator_prompt_metadata("paper-v1")["sha256"],
            "616c776b3552789aa3b0cbc6fb5aab2bba4026928a8fcf33831a47428eabd799",
        )
        self.assertEqual(simulation._USER_SYSTEM_PROMPT, PAPER_V1_PROMPT)
        self.assertNotEqual(PAPER_V1_PROMPT, V2_PROMPT)

    def test_invalid_version_fails_before_loading_user_or_calling_model(self):
        with patch.object(simulation, "load_user") as loader:
            with self.assertRaises(ValueError):
                simulation.UserSimulator("user_001", prompt_version="missing")
            loader.assert_not_called()

    def test_version_selects_actual_system_message(self):
        reply = json.dumps({"feedback_type": "add_context", "text": "Here is my draft."})
        for version in ("v2", "paper-v1"):
            with self.subTest(version=version), patch.object(
                simulation, "get_completion", return_value=reply
            ) as completion:
                feedback = self.respond(simulation.UserSimulator("user_001", version))
                self.assertFalse(feedback.is_done)
                self.assertEqual(completion.call_args.args[0][0]["content"], get_simulator_prompt(version))
                self.assertEqual(completion.call_args.kwargs, {"temperature": 0.85})
                self.assertEqual(completion.call_count, 1)
        self.assertEqual(DEFAULT_SIMULATOR_VERSION, "v2")

    def test_v2_retries_bad_shapes_and_accepts_valid_reply(self):
        valid = json.dumps({"feedback_type": "satisfied", "text": "That answers my question."})
        invalids = ["null", "[]", "not json", '{"feedback_type":"satisfied","text":42}',
                    '{"feedback_type":"satisfied","text":"  "}']
        for invalid in invalids:
            with self.subTest(invalid=invalid), patch.object(
                simulation, "get_completion", side_effect=[invalid, valid]
            ) as completion:
                feedback = self.respond(simulation.UserSimulator("user_001"))
                self.assertTrue(feedback.is_done)
                self.assertEqual(completion.call_count, 2)

    def test_v2_invalid_output_exhaustion_does_not_end_episode(self):
        for raw in ("null", '{"feedback_type":"satisfied","text":null}',
                    '{"feedback_type":"unknown","text":"The task is done."}'):
            with self.subTest(raw=raw), patch.object(simulation, "get_completion", return_value=raw) as completion:
                feedback = self.respond(simulation.UserSimulator("user_001"))
                self.assertEqual(completion.call_count, 3)
                self.assertEqual(feedback.feedback_type, simulation.FeedbackType.FOLLOWUP)
                self.assertFalse(feedback.is_done)
                self.assertTrue(feedback.text)
                self.assertNotEqual(feedback.text, "The task is done.")

    def test_legacy_parser_behavior_is_kept_for_paper_mode(self):
        with patch.object(simulation, "get_completion", return_value='{"feedback_type":"satisfied","text":""}') as completion:
            feedback = self.respond(simulation.UserSimulator("user_001", "paper-v1"))
            self.assertTrue(feedback.is_done)
            self.assertEqual(feedback.text, "")
            self.assertEqual(completion.call_count, 1)

    def test_episode_writes_selected_prompt_metadata(self):
        for version in ("v2", "paper-v1"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as tmp:
                episode = simulation.Episode("user_001", "Review my draft", simulator_version=version)
                episode.pref_checker.check = Mock(return_value=simulation.PrefJudgment(None, [], "fixture"))
                with patch.object(simulation, "get_completion", return_value='{"feedback_type":"satisfied","text":"Done."}'):
                    result = episode.run(lambda task, history: "Here is the revision.")
                path = Path(tmp) / "episode.json"
                result.save_history(str(path))
                saved = json.loads(path.read_text())
                self.assertEqual(saved["simulator_config"], simulator_prompt_metadata(version))
                self.assertEqual(saved["end_reason"], "satisfied")
                self.assertEqual(len(saved["turns"]), 1)

    def test_old_episode_constructor_remains_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = simulation.EpisodeResult("user_001", "Task", None)
            path = Path(tmp) / "episode.json"
            result.save_history(str(path))
            self.assertNotIn("simulator_config", json.loads(path.read_text()))


class RunnerVersionsTest(unittest.TestCase):
    def test_defaults_are_separated_and_release_ids_are_protected(self):
        self.assertEqual(runner.BenchmarkRunner(["user_001"], tasks=[])._rid, "default_v2")
        self.assertEqual(runner.BenchmarkRunner(["user_001"], tasks=[], simulator_version="paper-v1")._rid, "default")
        for rid in ("amem_pooled_50", "mem0_pooled_50_retrieve", "./nomem_pooled_50"):
            with self.subTest(rid=rid), self.assertRaises(ValueError):
                runner.BenchmarkRunner(["user_001"], tasks=[], run_id=rid)
        with self.assertRaises(ValueError):
            runner.BenchmarkRunner(["user_001"], tasks=[], simulator_version="missing")

    def test_runner_propagates_version_through_both_scoring_modes(self):
        for version in ("v2", "paper-v1"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as tmp:
                fake_episode = Mock()
                fake_result = Mock(turns=[])
                fake_episode.run.return_value = fake_result
                score = Mock()
                aggregate = Mock()
                with patch.object(runner, "_HERE", tmp), patch.object(runner, "Episode", return_value=fake_episode) as factory, \
                     patch.object(runner, "make_agent"), patch.object(runner, "load_user", return_value=USER), \
                     patch.object(runner, "UserScorer", return_value=score), \
                     patch.object(runner, "BenchmarkScorer", return_value=aggregate):
                    benchmark = runner.BenchmarkRunner(
                        ["user_001"], tasks=[("Task", None)], simulator_version=version,
                        run_id="offline_fixture", scoring_modes=["dump_all", "retrieve"],
                    )
                    reports = benchmark.run()
                self.assertEqual(factory.call_args.kwargs["simulator_version"], version)
                fake_episode.run.assert_called_once()
                self.assertEqual(score.score.call_count, 2)
                self.assertEqual(set(reports), {"dump_all", "retrieve"})

    def test_cli_help_lists_versions_without_model_access(self):
        output = io.StringIO()
        with patch.dict(sys.modules, {"llm_client": offline_llm}), \
             patch.object(sys, "argv", ["runner.py", "--help"]), \
             contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as result:
            runpy.run_path(str(ROOT / "runner.py"), run_name="__main__")
        self.assertEqual(result.exception.code, 0)
        self.assertIn("--simulator-version {paper-v1,v2}", output.getvalue())


if __name__ == "__main__":
    unittest.main()
