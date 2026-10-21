"""A framework for building static, installable, multilingual phrasebooks.

The framework holds no language and no phrases. A project (a folder under content/) supplies them as
language-neutral pages and per-language packs; see docs/FRAMEWORK.md.
"""
from .cli import build, find_project, main
from .content import (ContentError, coverage, draft_sources, pick_edition, read, validate)
from .messages import Messages
from .site import Site

__all__ = ["build", "find_project", "main", "ContentError", "coverage", "draft_sources", "pick_edition",
           "read", "validate", "Messages", "Site"]
