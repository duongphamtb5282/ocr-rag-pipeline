"""Backward-compat shim — use components.hybrid_retriever instead.

SemanticSearch is now HybridRetriever in the canonical components/ package.
"""

from __future__ import annotations

from components.hybrid_retriever import hybrid_retriever as semantic_search  # noqa: F401
from components.hybrid_retriever import HybridRetriever as SemanticSearch  # noqa: F401
