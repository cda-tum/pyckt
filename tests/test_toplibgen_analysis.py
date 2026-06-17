"""Tests for `topogen.analysis.TopLibGenAnalysis` (Week 9 Phase 1).

Coverage areas
--------------
* Class import + re-export visibility
* `initialize()` rejects missing/empty `--output-dir` with `ValueError`
* `initialize/compute/write` no longer raise `NotImplementedError`
* `compute()` / `write()` before `initialize()` raise `RuntimeError`
* `write()` before `compute()` raises `RuntimeError`
* End-to-end: full pipeline writes the expected sub-directory layout
* Registry guard (Phase 4 expanded scope): NO entry in
  `pyckt.cli.ANALYSIS_REGISTRY` raises `NotImplementedError` from
  `initialize()` — all 6 wrapper classes now dispatch to real engines
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_args(**kw) -> argparse.Namespace:
    defaults = dict(output_dir=None)
    defaults.update(kw)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# TopLibGenAnalysis — basic shape
# ---------------------------------------------------------------------------

class TestTopLibGenAnalysisBasics:
    def test_class_imports(self):
        from topogen.analysis import TopLibGenAnalysis
        assert TopLibGenAnalysis is not None

    def test_initialize_no_longer_raises_not_implemented(self, tmp_path):
        from topogen.analysis import TopLibGenAnalysis
        analysis = TopLibGenAnalysis(_make_args(output_dir=str(tmp_path)))
        try:
            analysis.initialize()
        except NotImplementedError:
            pytest.fail("initialize() still raises NotImplementedError")

    def test_compute_no_longer_raises_not_implemented(self, tmp_path):
        from topogen.analysis import TopLibGenAnalysis
        analysis = TopLibGenAnalysis(_make_args(output_dir=str(tmp_path)))
        try:
            analysis.compute()
        except NotImplementedError:
            pytest.fail("compute() still raises NotImplementedError")
        except Exception:
            pass  # RuntimeError without initialize is acceptable

    def test_write_no_longer_raises_not_implemented(self, tmp_path):
        from topogen.analysis import TopLibGenAnalysis
        analysis = TopLibGenAnalysis(_make_args(output_dir=str(tmp_path)))
        try:
            analysis.write()
        except NotImplementedError:
            pytest.fail("write() still raises NotImplementedError")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# TopLibGenAnalysis — argument validation
# ---------------------------------------------------------------------------

class TestTopLibGenAnalysisArgs:
    def test_initialize_missing_output_dir_raises_value_error(self):
        from topogen.analysis import TopLibGenAnalysis
        analysis = TopLibGenAnalysis(_make_args(output_dir=None))
        with pytest.raises(ValueError, match="output-dir"):
            analysis.initialize()

    def test_initialize_empty_output_dir_raises_value_error(self):
        from topogen.analysis import TopLibGenAnalysis
        analysis = TopLibGenAnalysis(_make_args(output_dir=""))
        with pytest.raises(ValueError, match="output-dir"):
            analysis.initialize()


# ---------------------------------------------------------------------------
# TopLibGenAnalysis — lifecycle ordering
# ---------------------------------------------------------------------------

class TestTopLibGenAnalysisLifecycle:
    def test_compute_before_initialize_raises_runtime(self):
        from topogen.analysis import TopLibGenAnalysis
        analysis = TopLibGenAnalysis(_make_args())
        with pytest.raises(RuntimeError, match="not initialized"):
            analysis.compute()

    def test_write_before_compute_raises_runtime(self, tmp_path):
        from topogen.analysis import TopLibGenAnalysis
        analysis = TopLibGenAnalysis(_make_args(output_dir=str(tmp_path)))
        analysis.initialize()
        # compute() not called → library is None
        with pytest.raises(RuntimeError, match="not initialized"):
            analysis.write()


# ---------------------------------------------------------------------------
# TopLibGenAnalysis — end-to-end (slow: runs the real generator)
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestTopLibGenAnalysisEndToEnd:
    """Class-scoped fixture so generate() runs once for all tests below.

    Marked ``slow`` (Week 9 Phase 5) — the fixture's
    ``analysis.compute()`` invokes the full HL2–HL5 topology generator
    (~18 s wall time).  Run with ``pytest -m slow`` to include.
    """

    @pytest.fixture(scope="class")
    def completed_analysis(self, tmp_path_factory):
        from topogen.analysis import TopLibGenAnalysis
        out = tmp_path_factory.mktemp("toplibgen_e2e")
        analysis = TopLibGenAnalysis(_make_args(output_dir=str(out)))
        analysis.initialize()
        analysis.compute()
        analysis.write()
        return analysis, out

    def test_library_populated(self, completed_analysis):
        analysis, _ = completed_analysis
        assert analysis.library is not None
        assert analysis.library.size() > 100

    def test_writes_ckt_files(self, completed_analysis):
        _, out = completed_analysis
        ckt_files = list(out.rglob("*.ckt"))
        assert len(ckt_files) > 100

    def test_written_count_matches_library(self, completed_analysis):
        analysis, out = completed_analysis
        ckt_files = list(out.rglob("*.ckt"))
        assert len(ckt_files) == analysis.library.size()

    def test_creates_all_four_category_dirs(self, completed_analysis):
        _, out = completed_analysis
        for category in (
            "one_stage_single_output",
            "one_stage_fully_differential",
            "two_stage_single_output",
            "two_stage_fully_differential",
        ):
            assert (out / category).is_dir(), f"missing category dir {category}"


# ---------------------------------------------------------------------------
# Phase 4 acceptance criterion: NO ANALYSIS_REGISTRY entry stubs out
# ---------------------------------------------------------------------------

class TestRegistryHasNoStubs:
    """Promoted from Phase 1's narrow `TestToplibgenRegistryEntry` to cover
    all 6 entries now that Phase 4 wired the remaining `structrec`,
    `rulegen`, and `partitioning` analyses.

    For each registry entry, instantiates the class with an empty argparse
    namespace and calls `initialize()`.  A `NotImplementedError` is a fatal
    failure (the analysis is still a stub).  Any *other* exception
    (`ValueError` for missing args, `FileNotFoundError`, etc.) is acceptable
    here — this test only protects against the stub regression.
    """

    def test_no_entry_raises_not_implemented(self):
        from pyckt.cli import ANALYSIS_REGISTRY

        empty = argparse.Namespace()
        for name, (module_path, class_name) in ANALYSIS_REGISTRY.items():
            module = __import__(module_path, fromlist=[class_name])
            analysis_class = getattr(module, class_name)
            instance = analysis_class(empty)
            try:
                instance.initialize()
            except NotImplementedError as exc:
                pytest.fail(
                    f"ANALYSIS_REGISTRY[{name!r}] still raises "
                    f"NotImplementedError: {exc}"
                )
            except Exception:
                pass  # any other error is acceptable for this stub-regression guard
