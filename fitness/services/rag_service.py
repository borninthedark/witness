"""RAG query service — Azure OpenAI + Azure AI Search hybrid retrieval."""

from __future__ import annotations

import logging

from pydantic import BaseModel

from fitness.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class RagSource(BaseModel):
    """A single source document returned from hybrid search."""

    source: str
    data_type: str
    content: str
    score: float


class RagResponse(BaseModel):
    """Grounded answer with source citations."""

    answer: str
    sources: list[RagSource]
    model: str


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are the Enterprise-D main computer, designation LCARS. "
    "You answer questions using ONLY the context provided below. "
    "If the context does not contain enough information, state: "
    "'Insufficient data available in memory banks.' "
    "Always cite which source documents you relied on. "
    "Respond in a concise, professional Starfleet briefing style."
)

# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

INDEX_NAME = "witness-data"
EMBEDDING_MODEL = "text-embedding-3-large"
CHAT_MODEL = "gpt-4o"
TOP_K = 5


class RagService:
    """Hybrid RAG: embed -> search -> generate grounded answer."""

    @staticmethod
    def _enabled() -> bool:
        return bool(
            settings.enable_rag
            and settings.azure_openai_endpoint
            and settings.azure_openai_key
            and settings.azure_search_endpoint
            and settings.azure_search_key
        )

    async def query(self, question: str) -> RagResponse:
        """Run a full RAG pipeline: embed, search, generate.

        Returns an empty response when the feature is disabled.
        """
        if not self._enabled():
            return RagResponse(answer="RAG is not enabled.", sources=[], model="n/a")

        try:
            # Late imports — only needed when RAG is actually on
            from azure.core.credentials import AzureKeyCredential
            from azure.search.documents import SearchClient
            from azure.search.documents.models import VectorizableTextQuery
            from openai import AzureOpenAI

            # ------ 1. Embed the user question ------
            oai = AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_key,
                api_version="2024-06-01",
            )
            embed_resp = oai.embeddings.create(
                input=[question],
                model=EMBEDDING_MODEL,
            )
            _ = embed_resp.data[0].embedding  # consumed by VectorizableTextQuery

            # ------ 2. Hybrid search (vector + keyword + semantic) ------
            search_client = SearchClient(
                endpoint=settings.azure_search_endpoint,
                index_name=INDEX_NAME,
                credential=AzureKeyCredential(settings.azure_search_key),
            )

            vector_query = VectorizableTextQuery(
                text=question,
                k_nearest_neighbors=TOP_K,
                fields="content_vector",
            )

            results = search_client.search(
                search_text=question,
                vector_queries=[vector_query],
                query_type="semantic",
                semantic_configuration_name="default",
                top=TOP_K,
            )

            # ------ 3. Assemble context from top-K results ------
            sources: list[RagSource] = []
            context_parts: list[str] = []

            for hit in results:
                source = RagSource(
                    source=hit.get("source", hit.get("title", "unknown")),
                    data_type=hit.get("data_type", "document"),
                    content=hit.get("content", "")[:500],
                    score=float(hit.get("@search.score", 0.0)),
                )
                sources.append(source)
                context_parts.append(
                    f"[Source: {source.source}]\n{hit.get('content', '')}"
                )

            context_block = (
                "\n---\n".join(context_parts)
                if context_parts
                else "No relevant documents found."
            )

            # ------ 4. Generate grounded answer ------
            chat_resp = oai.chat.completions.create(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Context:\n{context_block}\n\nQuestion: {question}"
                        ),
                    },
                ],
                temperature=0.3,
                max_tokens=1024,
            )

            answer = chat_resp.choices[0].message.content or "No response generated."

            return RagResponse(
                answer=answer,
                sources=sources,
                model=CHAT_MODEL,
            )

        except Exception:
            logger.exception("RAG query failed")
            return RagResponse(
                answer="Unable to process query — check logs for details.",
                sources=[],
                model=CHAT_MODEL,
            )


rag_service = RagService()
