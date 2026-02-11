"""
In-memory session store for persisting chat history, memory, and chart context
across multiple requests within a session.
"""

import time
import os
from typing import Dict, Any, Optional


SESSION_TTL = int(os.getenv("SESSION_TTL_MINUTES", "60")) * 60  # seconds


class SessionData:
    """Holds all persistent state for a single user session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = time.time()
        self.last_accessed = time.time()

        # Chat history (user + AI messages)
        self.chat_history: list = []

        # Semantic memory: key facts extracted from conversation
        self.memory: Dict[str, Any] = {
            "key_insights": [],       # important findings from previous queries
            "user_preferences": {},   # chart type preferences, etc.
            "data_context": {},       # column meanings, domain context
        }

        # Previously generated chart IDs (to avoid duplicates)
        self.previous_charts: list = []

        # Previous chart contexts (full specs for memory)
        self.chart_contexts: list = []

        # Active data filters
        self.filters: Dict[str, Any] = {}

        # A2A message log (inter-agent communication)
        self.a2a_messages: list = []

    def touch(self):
        self.last_accessed = time.time()

    def is_expired(self) -> bool:
        return (time.time() - self.last_accessed) > SESSION_TTL

    def add_chat(self, role: str, content: str):
        self.chat_history.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })

    def add_insight(self, insight: str):
        self.memory["key_insights"].append(insight)
        # Keep last 20 insights
        self.memory["key_insights"] = self.memory["key_insights"][-20:]

    def add_chart_context(self, chart_id: str, chart_type: str, title: str, columns_used: list):
        self.chart_contexts.append({
            "id": chart_id,
            "type": chart_type,
            "title": title,
            "columns_used": columns_used,
            "timestamp": time.time()
        })
        self.previous_charts.append(chart_id)

    def get_context_summary(self) -> str:
        """Get a summary of session context for agents."""
        parts = []

        if self.chat_history:
            recent = self.chat_history[-6:]  # last 3 exchanges
            parts.append("Recent conversation:")
            for msg in recent:
                parts.append(f"  {msg['role']}: {msg['content'][:200]}")

        if self.memory["key_insights"]:
            parts.append(f"Key insights: {', '.join(self.memory['key_insights'][-5:])}")

        if self.chart_contexts:
            recent_charts = self.chart_contexts[-5:]
            chart_summary = [f"{c['type']}:{c['title']}" for c in recent_charts]
            parts.append(f"Previous charts: {', '.join(chart_summary)}")

        if self.filters:
            parts.append(f"Active filters: {self.filters}")

        return "\n".join(parts) if parts else "No previous context."

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "chat_history": self.chat_history,
            "memory": self.memory,
            "previous_charts": self.previous_charts,
            "chart_contexts": self.chart_contexts,
            "filters": self.filters,
            "a2a_messages": self.a2a_messages,
        }


class SessionStore:
    """Global in-memory session store."""

    _sessions: Dict[str, SessionData] = {}

    @classmethod
    def get_or_create(cls, session_id: str) -> SessionData:
        cls._cleanup_expired()

        if session_id not in cls._sessions:
            cls._sessions[session_id] = SessionData(session_id)

        session = cls._sessions[session_id]
        session.touch()
        return session

    @classmethod
    def get(cls, session_id: str) -> Optional[SessionData]:
        session = cls._sessions.get(session_id)
        if session and not session.is_expired():
            session.touch()
            return session
        return None

    @classmethod
    def _cleanup_expired(cls):
        expired = [
            sid for sid, s in cls._sessions.items()
            if s.is_expired()
        ]
        for sid in expired:
            del cls._sessions[sid]

    @classmethod
    def list_sessions(cls) -> list:
        cls._cleanup_expired()
        return [
            {"session_id": s.session_id, "messages": len(s.chat_history)}
            for s in cls._sessions.values()
        ]
