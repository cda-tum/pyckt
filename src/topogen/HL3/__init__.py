"""HL3 — amplifier-stage building blocks.

The third hierarchy level groups HL2 cells into the functional parts of a single
amplifier stage.  HL4 wires these into complete (non-)inverting stages:

==================================================  ==============================================
Factory                                             Produces
==================================================  ==============================================
:class:`~topogen.HL3.tc.TransconductanceManager`    transconductors (the gm input devices)
:class:`~topogen.HL3.l.LoadManager`                 stage loads (mirror / resistive / cascoded)
:class:`~topogen.HL3.lp.LoadPartManager`            load sub-parts shared across load variants
:class:`~topogen.HL3.sb.StageBiasManager`           per-stage bias networks
==================================================  ==============================================

See :mod:`topogen` for the full HL1–HL5 hierarchy.
"""

from .l import *
from .lp import *
from .sb import *
from .tc import *
