"""Bundled data package — XML libraries, configuration files, etc.

This package exists so setuptools picks up ``src/data/`` as an installable
Python package, which in turn lets ``[tool.setuptools.package-data]`` ship
the bundled XML libraries (``structrec/``) inside the wheel.

The XMLs are loaded by :func:`recognition.library.Library.from_directory`
via a path resolved relative to the recognition module
(``recognition/library.py``).  After install, both the ``recognition``
package and the ``data`` package land under the same site-packages root,
so the relative path still works.
"""
