"""Deprecated import path.

Agent 5 (proctoring) now lives with the other agents at::

    agents.proctoring_agent

Example::

    from agents.proctoring_agent.integration import startup_agent5
"""

from __future__ import annotations

import warnings

warnings.warn(
    "Importing 'agent5' is deprecated; use 'agents.proctoring_agent' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from agents.proctoring_agent.integration import (  # noqa: E402,F401
    agent5_ready,
    shutdown_agent5,
    startup_agent5,
)
