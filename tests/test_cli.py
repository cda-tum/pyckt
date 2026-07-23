"""Tests for `cli` — subcommand parser + Result wrapper (Week 9 Phase 4)."""
from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest

from cli import ANALYSIS_REGISTRY, Result, build_parser, run

# ---------------------------------------------------------------------------
# build_parser — shape & subcommand discovery
# ---------------------------------------------------------------------------

class TestBuildParser:
    def test_returns_argument_parser(self):
        assert isinstance(build_parser(), argparse.ArgumentParser)

    def test_no_args_exits_nonzero(self):
        """A bare `pyckt` invocation must fail (subcommand is required)."""
        p = build_parser()
        with pytest.raises(SystemExit):
            p.parse_args([])

    @pytest.mark.parametrize("mode", list(ANALYSIS_REGISTRY))
    def test_each_mode_is_registered_as_subcommand(self, mode):
        """Every entry in `ANALYSIS_REGISTRY` has a subparser."""
        p = build_parser()
        # Each subcommand needs at least its own required args to parse;
        # we use `--help` because it short-circuits past required-arg checks.
        with pytest.raises(SystemExit) as exc_info:
            p.parse_args([mode, "--help"])
        # argparse exits 0 on --help; non-zero means the subcommand wasn't recognised.
        assert exc_info.value.code == 0

    def test_unknown_subcommand_rejected(self):
        p = build_parser()
        with pytest.raises(SystemExit):
            p.parse_args(["nonexistent-mode"])

    def test_log_level_choices(self):
        """Top-level --log-level-console accepts DEBUG/TRACE/OFF."""
        p = build_parser()
        for lvl in ("DEBUG", "TRACE", "OFF"):
            args = p.parse_args([
                "--log-level-console", lvl,
                "toplibgen", "--output-dir", "/tmp/x",
            ])
            assert args.log_level_console == lvl


# ---------------------------------------------------------------------------
# Per-subcommand arg shape
# ---------------------------------------------------------------------------

class TestSubcommandArgShape:
    def test_structrec_maps_short_flags_to_legacy_dests(self):
        """The new subcommand uses `--circuit` but writes to
        `args.circuit_netlist` for analysis-class backward compatibility."""
        args = build_parser().parse_args([
            "structrec",
            "--circuit", "c.hspice",
            "--device-types", "dt.xcat",
            "--mapping", "m.xcat",
            "--supply-nets", "sn.xcat",
            "--output", "out.xml",
        ])
        assert args.command == "structrec"
        assert args.circuit_netlist == "c.hspice"
        assert args.device_types_file == "dt.xcat"
        assert args.hspice_mapping_file == "m.xcat"
        assert args.hspice_supplynet_file == "sn.xcat"
        assert args.output_file == "out.xml"
        assert args.xml_structrec_library_file is None  # default

    def test_automaticsizing_optional_timeout_default(self):
        args = build_parser().parse_args([
            "automaticsizing",
            "--circuit", "c.hspice",
            "--device-types", "dt.xcat",
            "--mapping", "m.xcat",
            "--supply-nets", "sn.xcat",
            "--tech-file", "t.xml",
            "--circuit-params", "p.xml",
            "--output", "o.xml",
        ])
        assert args.runtime == 30.0
        assert args.transistor_model == "SHM"
        assert args.scaling == "1mum"

    def test_automaticsizing_timeout_override(self):
        args = build_parser().parse_args([
            "automaticsizing",
            "--circuit", "c.hspice",
            "--device-types", "dt.xcat",
            "--mapping", "m.xcat",
            "--supply-nets", "sn.xcat",
            "--tech-file", "t.xml",
            "--circuit-params", "p.xml",
            "--output", "o.xml",
            "--timeout", "60",
        ])
        assert args.runtime == 60.0

    def test_synthesis_requires_spec_and_output_dir(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args([
                "synthesis",
                "--device-types", "dt.xcat",
                "--tech-file", "t.xml",
                # missing --spec and --output-dir
            ])

    def test_toplibgen_only_requires_output_dir(self):
        args = build_parser().parse_args([
            "toplibgen", "--output-dir", "/tmp/lib",
        ])
        assert args.command == "toplibgen"
        assert args.output_dir == "/tmp/lib"


# ---------------------------------------------------------------------------
# run() — dispatch + Result wrapper
# ---------------------------------------------------------------------------

class TestRun:
    def _patch_analysis(self, command: str = "toplibgen"):
        """Replace the registry's analysis class with a MagicMock for one run."""
        module_path, class_name = ANALYSIS_REGISTRY[command]
        mock_instance = MagicMock()
        mock_class = MagicMock(return_value=mock_instance)

        import types
        fake_mod = types.ModuleType(module_path)
        setattr(fake_mod, class_name, mock_class)

        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == module_path:
                return fake_mod
            return original_import(name, *args, **kwargs)

        return mock_instance, mock_class, mock_import

    def test_returns_result_namedtuple(self, tmp_path):
        mock_instance, _, mock_import = self._patch_analysis("toplibgen")
        with (
            patch("cli.setup_logger"),
            patch("builtins.__import__", side_effect=mock_import),
        ):
            result = run([
                "--log-level-console", "OFF",
                "toplibgen", "--output-dir", str(tmp_path),
            ])
        assert isinstance(result, Result)
        assert result.returncode == 0
        assert result.data is mock_instance

    def test_run_calls_initialize_compute_write_in_order(self, tmp_path):
        mock_instance, _, mock_import = self._patch_analysis("toplibgen")
        with (
            patch("cli.setup_logger"),
            patch("builtins.__import__", side_effect=mock_import),
        ):
            run(["--log-level-console", "OFF",
                 "toplibgen", "--output-dir", str(tmp_path)])
        mock_instance.initialize.assert_called_once()
        mock_instance.compute.assert_called_once()
        mock_instance.write.assert_called_once()

    def test_run_returns_nonzero_on_exception(self, tmp_path):
        mock_instance, _, mock_import = self._patch_analysis("toplibgen")
        mock_instance.initialize.side_effect = ValueError("boom")
        with (
            patch("cli.setup_logger"),
            patch("builtins.__import__", side_effect=mock_import),
        ):
            result = run([
                "--log-level-console", "OFF",
                "toplibgen", "--output-dir", str(tmp_path),
            ])
        assert result.returncode == 1
        assert result.data is None

    def test_run_prints_runtime_summary_on_success(self, tmp_path, capsys):
        _, _, mock_import = self._patch_analysis("toplibgen")
        with (
            patch("cli.setup_logger"),
            patch("builtins.__import__", side_effect=mock_import),
        ):
            run(["--log-level-console", "OFF",
                 "toplibgen", "--output-dir", str(tmp_path)])
        out = capsys.readouterr().out
        assert "Program runtime:" in out


# ---------------------------------------------------------------------------
# main() — console-script entry point
# ---------------------------------------------------------------------------

class TestMain:
    """`main()` is the entry point that the `pyckt` console script calls.
    It must propagate `run().returncode` through `sys.exit`."""

    def test_main_exits_with_run_returncode(self):
        import cli
        with patch.object(cli, "run", return_value=Result(returncode=7, data=None)):
            with pytest.raises(SystemExit) as exc:
                cli.main()
            assert exc.value.code == 7
