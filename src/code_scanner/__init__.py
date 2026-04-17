"""Code Scanner - Local AI-driven code scanner."""

try:
    from importlib.metadata import version

    __version__ = version("code-scanner")
except Exception:
    __version__ = "0.0.0"

from .ctags_index import CtagsIndex, CtagsNotFoundError, CtagsError, Symbol
from .ai_tools import RipgrepNotFoundError, verify_ripgrep
