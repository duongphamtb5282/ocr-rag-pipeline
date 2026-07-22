"""RAG pipeline — orchestrates the full document processing lifecycle.

Wraps the LangGraph graph execution as an async service,
providing start, resume, cancel, and status operations.
"""

from __future__ import annotations

import logging
from typing import Any

from graph.builder import get_graph
from graph.state import OCRFormFillState, create_initial_state

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Document processing pipeline — orchestrates OCR → extraction → mapping → fill."""

    async def start_session(self, session_id: str, document_path: str, target_url: str | None = None) -> dict[str, Any]:
        """Start a new document processing session.

        Args:
            session_id: Unique session identifier.
            document_path: Path to the uploaded document.
            target_url: Optional target web form URL.

        Returns:
            Initial state dict with session metadata.
        """
        initial = create_initial_state(session_id, document_path, target_url)
        logger.info("Pipeline session %s started (doc: %s)", session_id[:8], document_path)
        return initial

    async def run(self, state: OCRFormFillState) -> OCRFormFillState:
        """Execute the full pipeline from current state.

        Args:
            state: Current pipeline state (initial or resumed).

        Returns:
            Final state after pipeline execution (may be interrupted at human review).
        """
        graph = get_graph()
        result = await graph.ainvoke(state)
        return result

    async def resume_from_review(self, session_id: str, thread_id: str, corrections: dict[str, Any]) -> OCRFormFillState:
        """Resume pipeline after human review with corrections.

        Args:
            session_id: Session identifier.
            thread_id: LangGraph thread ID for the session.
            corrections: Human-provided field corrections.

        Returns:
            Updated state after resumption.
        """
        graph = get_graph()
        state = await graph.ainvoke(
            {"session_id": session_id, "human_corrections": corrections, "review_status": "approved"},
            config={"configurable": {"thread_id": thread_id}},
        )
        return state

    async def cancel_session(self, session_id: str) -> dict[str, Any]:
        """Cancel a running session."""
        logger.info("Pipeline session %s cancelled", session_id[:8])
        return {"session_id": session_id, "status": "cancelled"}


rag_pipeline = RAGPipeline()
