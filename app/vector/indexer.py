"""Indexing pipeline — indexes documents, templates, and field mappings after each session."""

from __future__ import annotations

import json
import logging

from app.gateway.service import gateway_embed
from graph.state import OCRFormFillState
from app.vector import vector_db

logger = logging.getLogger(__name__)


class IndexingPipeline:
    """Indexes all artifacts from a completed session into the vector DB."""

    async def index_session(self, state: OCRFormFillState):
        """Index all session artifacts."""
        session_id = state["session_id"]
        logger.info(f"Indexing session {session_id}")

        try:
            # 1. Index document text + extracted fields
            await self._index_document(state)
            # 2. Index field mappings for future reuse
            await self._index_field_mappings(state)
        except Exception as e:
            logger.error(f"Indexing failed for {session_id}: {e}")

    async def _index_document(self, state: OCRFormFillState):
        """Generate document embedding and store in vector DB."""
        text_parts = []
        text_parts.append(state.get("raw_text", "")[:2000])
        extracted = state.get("extracted_fields", {}) or {}
        for key, data in extracted.items():
            text_parts.append(f"{key}: {data.get('value', '')}")
        text_for_embedding = "\n".join(text_parts)

        if not text_for_embedding.strip():
            return

        embedding = await gateway_embed(text_for_embedding, model="text-embedding-3-large", dimensions=1536)

        await vector_db.upsert(
            collection="documents",
            point_id=state["session_id"],
            vector=embedding,
            payload={
                "session_id": state["session_id"],
                "doc_type": state.get("doc_type"),
                "quality": state.get("doc_quality"),
                "extracted_fields": extracted,
                "fill_status": state.get("fill_status"),
                "created_at": state.get("created_at"),
            },
        )

    async def _index_field_mappings(self, state: OCRFormFillState):
        """Index approved field mappings for future reuse."""
        mappings = state.get("field_mappings", {}) or {}
        if not mappings:
            return

        for extracted_key, mapping in mappings.items():
            text = f"{extracted_key} -> {mapping.get('form_field_id', 'unknown')}"
            embedding = await gateway_embed(text, model="text-embedding-3-small", dimensions=512)

            await vector_db.upsert(
                collection="field_mappings",
                point_id=f"map_{state['session_id']}_{extracted_key}",
                vector=embedding,
                payload={
                    "extracted_field_key": extracted_key,
                    "form_field_id": mapping.get("form_field_id"),
                    "confidence": mapping.get("confidence", 0.0),
                    "session_id": state["session_id"],
                },
            )


indexing_pipeline = IndexingPipeline()
