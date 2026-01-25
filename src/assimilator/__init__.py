"""Codebase Assimilator - Generate compressed manifests for LLM context."""

from .core import Assimilator
from .manifest import Manifest, Component, Pattern, Language

__all__ = ["Assimilator", "Manifest", "Component", "Pattern", "Language"]
