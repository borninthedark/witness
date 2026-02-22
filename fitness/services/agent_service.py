"""Multi-agent service — AI-102 Domain 3 (Agentic) demonstration.

Three specialist agents collaborate under a routing First Officer:
  - Science Officer  (SpaceAnalystAgent)  — space, astronomy, physics
  - Tactical Officer (SecurityAnalystAgent) — security, CVEs, threats
  - First Officer    (RoutingAgent)         — dispatches to specialists
"""

from __future__ import annotations

import logging

from fitness.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword routing tables
# ---------------------------------------------------------------------------

SPACE_KEYWORDS = frozenset(
    {
        "space",
        "nasa",
        "asteroid",
        "neo",
        "orbit",
        "planet",
        "star",
        "galaxy",
        "nebula",
        "apod",
        "astronomy",
        "comet",
        "exoplanet",
        "solar",
        "lunar",
        "satellite",
        "telescope",
        "cosmos",
        "supernova",
        "spacecraft",
        "mars",
        "rover",
        "celestial",
        "astrometrics",
    }
)

SECURITY_KEYWORDS = frozenset(
    {
        "security",
        "cve",
        "vulnerability",
        "threat",
        "attack",
        "exploit",
        "malware",
        "phishing",
        "firewall",
        "encryption",
        "patch",
        "nist",
        "compliance",
        "audit",
        "incident",
        "breach",
        "ransomware",
        "waf",
        "guardduty",
        "shield",
        "tactical",
        "intrusion",
        "zero-day",
    }
)

# ---------------------------------------------------------------------------
# Azure OpenAI helper
# ---------------------------------------------------------------------------

CHAT_MODEL = "gpt-4o"


def _get_openai_client():
    """Return an AzureOpenAI client (late import)."""
    from openai import AzureOpenAI

    return AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_key,
        api_version="2024-06-01",
    )


async def _chat(system_prompt: str, user_message: str) -> str:
    """Send a single chat completion request to Azure OpenAI."""
    client = _get_openai_client()
    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.4,
        max_tokens=1024,
    )
    return resp.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Specialist agents
# ---------------------------------------------------------------------------


class SpaceAnalystAgent:
    """Science Officer — analyses space and astronomy questions."""

    SYSTEM_PROMPT = (
        "You are the Science Officer aboard the USS Enterprise-D. "
        "You specialise in astrophysics, planetary science, and astrometrics. "
        "Provide clear, data-driven analyses in a professional Starfleet tone. "
        "Cite any numerical values or known phenomena you reference."
    )

    async def analyze(self, question: str) -> str:
        """Produce a Science Officer briefing for the given question."""
        logger.info("Science Officer analysing: %s", question[:80])
        return await _chat(self.SYSTEM_PROMPT, question)


class SecurityAnalystAgent:
    """Tactical Officer — analyses security and threat questions."""

    SYSTEM_PROMPT = (
        "You are the Tactical Officer aboard the USS Enterprise-D. "
        "You specialise in cyber-security, vulnerability analysis, "
        "and threat assessment. "
        "Provide actionable, concise security briefings "
        "in a professional Starfleet tone. "
        "Reference CVE IDs, NIST frameworks, "
        "or MITRE ATT&CK where applicable."
    )

    async def analyze(self, question: str) -> str:
        """Produce a Tactical Officer briefing for the given question."""
        logger.info("Tactical Officer analysing: %s", question[:80])
        return await _chat(self.SYSTEM_PROMPT, question)


class RoutingAgent:
    """First Officer — routes questions to the appropriate specialist."""

    SYSTEM_PROMPT = (
        "You are the First Officer aboard the USS Enterprise-D. "
        "A crew member has asked a general question that does not clearly fall "
        "under Science or Tactical. Provide a helpful, balanced answer drawing "
        "on your broad Starfleet training. Keep the response concise."
    )

    def __init__(self) -> None:
        self.science = SpaceAnalystAgent()
        self.tactical = SecurityAnalystAgent()

    def _classify(self, question: str) -> str:
        """Classify a question into 'space', 'security', or 'general'."""
        tokens = frozenset(question.lower().split())
        space_hits = len(tokens & SPACE_KEYWORDS)
        security_hits = len(tokens & SECURITY_KEYWORDS)

        if space_hits > security_hits:
            return "space"
        if security_hits > space_hits:
            return "security"
        if space_hits > 0:
            return "space"
        return "general"

    async def analyze(self, question: str) -> str:
        """Route the question to the best specialist and return the answer."""
        domain = self._classify(question)
        logger.info("First Officer routing '%s' -> %s", question[:60], domain)

        if domain == "space":
            return await self.science.analyze(question)
        if domain == "security":
            return await self.tactical.analyze(question)
        # General — First Officer handles directly
        return await _chat(self.SYSTEM_PROMPT, question)


# ---------------------------------------------------------------------------
# Top-level service facade
# ---------------------------------------------------------------------------


class AgentService:
    """Facade for the multi-agent system."""

    def __init__(self) -> None:
        self.router = RoutingAgent()

    @staticmethod
    def _enabled() -> bool:
        return bool(
            settings.enable_rag
            and settings.azure_openai_endpoint
            and settings.azure_openai_key
        )

    async def analyze(self, question: str) -> dict:
        """Route a question through the agent system.

        Returns a dict with 'answer', 'agent', and 'model' keys.
        When the feature is disabled, returns a stub response.
        """
        if not self._enabled():
            return {
                "answer": "Agent system is not enabled.",
                "agent": "n/a",
                "model": "n/a",
            }

        try:
            domain = self.router._classify(question)
            agent_label = {
                "space": "Science Officer",
                "security": "Tactical Officer",
                "general": "First Officer",
            }.get(domain, "First Officer")

            answer = await self.router.analyze(question)
            return {
                "answer": answer,
                "agent": agent_label,
                "model": CHAT_MODEL,
            }
        except Exception:
            logger.exception("Agent service failed")
            return {
                "answer": "The agent system encountered an error — check logs.",
                "agent": "error",
                "model": CHAT_MODEL,
            }


agent_service = AgentService()
