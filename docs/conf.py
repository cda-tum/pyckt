"""Sphinx configuration for the pyckt documentation.

Build locally with::

    pip install -e ".[docs]"
    sphinx-build -b html docs docs/_build/html

The ``src/`` layout means the packages (``pyckt``, ``topogen``, ``recognition``,
``partitioning``) are not importable until ``src/`` is on ``sys.path`` — added
below so ``autodoc`` can import them and render their docstrings.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

# -- Project information -----------------------------------------------------

project = "pyckt"
author = "pyckt contributors"
copyright = "2026, pyckt contributors"
release = "0.1.0"

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",       # pull docstrings from the source
    "sphinx.ext.napoleon",      # parse the numpydoc-style docstrings used here
    "sphinx.ext.viewcode",      # add [source] links next to each object
    "sphinx.ext.intersphinx",   # cross-link to the Python stdlib docs
    "myst_parser",              # allow Markdown (.md) pages alongside .rst
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# ortools (CP-SAT) is a heavy native dependency only needed at *runtime* for
# sizing/synthesis — mock it so the docs build without installing it.
autodoc_mock_imports = ["ortools"]

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}

# Shared dataclasses (Specifications, CircuitParameter, TransistorTechParams, …)
# are re-exported across several packages, so autodoc documents them on more
# than one page and Sphinx flags the cross-references as ambiguous.  These are
# cosmetic; the build still renders every object.  Suppressing keeps the log
# readable.  (Collapsing the re-exports onto a single canonical page is a
# follow-up — see SUPERVISOR_FEEDBACK.md §3.)
suppress_warnings = ["ref.python"]
autodoc_member_order = "bysource"
autodoc_typehints = "description"

napoleon_numpy_docstring = True
napoleon_google_docstring = False

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# -- HTML output -------------------------------------------------------------

html_theme = "furo"
html_title = "pyckt"
