#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: tests/model/test_script_model.py
# ----------------------------------------------------------------------------------
# Purpose:
# Tests for ScriptModel hooks file creation, source I/O, and hot-reload via
# importlib.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------

import textwrap

from crystalsweep.model.script_model import ScriptModel


class TestScriptModelInit:
    """Verify ScriptModel creates the hooks file and respects an existing one."""

    def test_creates_hooks_file_on_first_init(self, tmp_path):
        model = ScriptModel(tmp_path)
        assert model.hooks_path.is_file()

    def test_hooks_path_is_inside_directory(self, tmp_path):
        model = ScriptModel(tmp_path)
        assert model.hooks_path.parent == tmp_path

    def test_hooks_path_named_hooks_py(self, tmp_path):
        model = ScriptModel(tmp_path)
        assert model.hooks_path.name == "hooks.py"

    def test_directory_property_matches_input(self, tmp_path):
        model = ScriptModel(tmp_path)
        assert model.directory == tmp_path

    def test_directory_created_if_missing(self, tmp_path):
        nested = tmp_path / "a" / "b"
        ScriptModel(nested)
        assert nested.is_dir()

    def test_does_not_overwrite_existing_hooks(self, tmp_path):
        (tmp_path / "hooks.py").write_text("# custom", encoding="utf-8")
        ScriptModel(tmp_path)
        assert (tmp_path / "hooks.py").read_text(encoding="utf-8") == "# custom"


class TestScriptModelLoadSource:
    """Verify load_source() returns current file content."""

    def test_returns_file_content(self, tmp_path):
        (tmp_path / "hooks.py").write_text("x = 1", encoding="utf-8")
        model = ScriptModel.__new__(ScriptModel)
        model._directory = tmp_path
        assert model.load_source() == "x = 1"

    def test_default_hooks_contains_pre_scan(self, tmp_path):
        model = ScriptModel(tmp_path)
        source = model.load_source()
        assert "def pre_scan" in source

    def test_default_hooks_contains_post_scan(self, tmp_path):
        model = ScriptModel(tmp_path)
        source = model.load_source()
        assert "def post_scan" in source

    def test_default_hooks_contains_pre_collection(self, tmp_path):
        model = ScriptModel(tmp_path)
        source = model.load_source()
        assert "def pre_collection" in source

    def test_default_hooks_contains_post_collection(self, tmp_path):
        model = ScriptModel(tmp_path)
        source = model.load_source()
        assert "def post_collection" in source


class TestScriptModelSaveSource:
    """Verify save_source() writes to hooks_path and is immediately readable."""

    def test_saves_custom_source(self, tmp_path):
        model = ScriptModel(tmp_path)
        custom = "def pre_scan(point, config): return 'skip'"
        model.save_source(custom)
        assert model.hooks_path.read_text(encoding="utf-8") == custom

    def test_saved_source_is_readable_again(self, tmp_path):
        model = ScriptModel(tmp_path)
        model.save_source("# hello world")
        assert model.load_source() == "# hello world"

    def test_overwrite_existing_content(self, tmp_path):
        model = ScriptModel(tmp_path)
        model.save_source("version 1")
        model.save_source("version 2")
        assert model.load_source() == "version 2"


class TestScriptModelCall:
    """Verify call() hot-loads hooks.py and dispatches to the named function."""

    def _write_hooks(self, tmp_path, source):
        (tmp_path / "hooks.py").write_text(textwrap.dedent(source), encoding="utf-8")

    def test_calls_defined_function(self, tmp_path):
        self._write_hooks(
            tmp_path,
            """\
            def greet():
                return "hello"
        """,
        )
        model = ScriptModel.__new__(ScriptModel)
        model._directory = tmp_path
        assert model.call("greet") == "hello"

    def test_passes_positional_args(self, tmp_path):
        self._write_hooks(
            tmp_path,
            """\
            def add(a, b):
                return a + b
        """,
        )
        model = ScriptModel.__new__(ScriptModel)
        model._directory = tmp_path
        assert model.call("add", 2, 3) == 5

    def test_passes_keyword_args(self, tmp_path):
        self._write_hooks(
            tmp_path,
            """\
            def greet(greeting="world"):
                return f"hello {greeting}"
        """,
        )
        model = ScriptModel.__new__(ScriptModel)
        model._directory = tmp_path
        assert model.call("greet", greeting="tester") == "hello tester"

    def test_missing_function_returns_none(self, tmp_path):
        self._write_hooks(
            tmp_path,
            """\
            def other():
                pass
        """,
        )
        model = ScriptModel.__new__(ScriptModel)
        model._directory = tmp_path
        assert model.call("nonexistent_function") is None

    def test_function_raising_exception_returns_none(self, tmp_path):
        self._write_hooks(
            tmp_path,
            """\
            def bad():
                raise RuntimeError("oops")
        """,
        )
        model = ScriptModel.__new__(ScriptModel)
        model._directory = tmp_path
        assert model.call("bad") is None

    def test_syntax_error_in_hooks_returns_none(self, tmp_path):
        (tmp_path / "hooks.py").write_text("def broken(: pass", encoding="utf-8")
        model = ScriptModel.__new__(ScriptModel)
        model._directory = tmp_path
        assert model.call("broken") is None

    def test_missing_hooks_file_returns_none(self, tmp_path):
        model = ScriptModel.__new__(ScriptModel)
        model._directory = tmp_path
        assert model.call("anything") is None

    def test_function_returning_none(self, tmp_path):
        self._write_hooks(
            tmp_path,
            """\
            def noop():
                return None
        """,
        )
        model = ScriptModel.__new__(ScriptModel)
        model._directory = tmp_path
        assert model.call("noop") is None

    def test_function_returning_false(self, tmp_path):
        self._write_hooks(
            tmp_path,
            """\
            def falsy():
                return False
        """,
        )
        model = ScriptModel.__new__(ScriptModel)
        model._directory = tmp_path
        assert model.call("falsy") is False


class TestScriptModelHotReload:
    """Verify that edits to hooks.py are picked up on the next call() without reinitialising."""

    def test_edit_takes_effect_without_reinit(self, tmp_path):
        model = ScriptModel(tmp_path)
        model.save_source(
            textwrap.dedent("""\
            def value():
                return 1
        """)
        )
        assert model.call("value") == 1

        model.save_source(
            textwrap.dedent("""\
            def value():
                return 42
        """)
        )
        assert model.call("value") == 42

    def test_add_new_function_visible_without_reinit(self, tmp_path):
        model = ScriptModel(tmp_path)
        model.save_source("def first(): return 'a'")
        assert model.call("first") == "a"

        model.save_source("def first(): return 'a'\ndef second(): return 'b'")
        assert model.call("second") == "b"

    def test_delete_function_returns_none_after_edit(self, tmp_path):
        model = ScriptModel(tmp_path)
        model.save_source("def fn(): return 1")
        assert model.call("fn") == 1

        model.save_source("# fn removed")
        assert model.call("fn") is None
