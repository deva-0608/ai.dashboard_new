"""
Agent-to-Agent (A2A) Protocol

Enables agents to communicate context, findings, and recommendations
to each other through a shared message bus within the pipeline state.

Each message has:
- sender: agent name
- receiver: target agent name (or "all" for broadcast)
- msg_type: category of message
- payload: the actual data
"""

import time
from typing import Dict, Any, List, Optional


class A2AMessage:
    """A single agent-to-agent message."""

    def __init__(self, sender: str, receiver: str, msg_type: str, payload: Dict[str, Any]):
        self.sender = sender
        self.receiver = receiver
        self.msg_type = msg_type
        self.payload = payload
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "msg_type": self.msg_type,
            "payload": self.payload,
            "timestamp": self.timestamp
        }


class A2ABus:
    """
    Shared message bus for inter-agent communication.

    Message types:
    - schema_info: Schema profiler shares column classifications
    - intent_info: Intent agent shares user intent analysis
    - plan_info: Planner shares analytics plan
    - chart_context: Chart agent shares generated chart details
    - memory_context: Memory agent shares session context
    - data_insight: Any agent shares a data insight
    - recommendation: Agent recommends action to another
    """

    def __init__(self, messages: Optional[List[dict]] = None):
        self.messages: List[A2AMessage] = []
        if messages:
            for m in messages:
                self.messages.append(
                    A2AMessage(m["sender"], m["receiver"], m["msg_type"], m["payload"])
                )

    def publish(self, sender: str, receiver: str, msg_type: str, payload: Dict[str, Any]):
        """Send a message from one agent to another (or broadcast to 'all')."""
        msg = A2AMessage(sender, receiver, msg_type, payload)
        self.messages.append(msg)

    def get_messages_for(self, agent_name: str, msg_type: Optional[str] = None) -> List[dict]:
        """Get all messages addressed to a specific agent (or broadcast)."""
        result = []
        for m in self.messages:
            if m.receiver in (agent_name, "all"):
                if msg_type is None or m.msg_type == msg_type:
                    result.append(m.to_dict())
        return result

    def get_all_of_type(self, msg_type: str) -> List[dict]:
        """Get all messages of a specific type."""
        return [m.to_dict() for m in self.messages if m.msg_type == msg_type]

    def get_context_for_agent(self, agent_name: str) -> str:
        """Get a formatted context string for an agent based on A2A messages."""
        messages = self.get_messages_for(agent_name)
        if not messages:
            return ""

        parts = ["=== A2A Context ==="]
        for m in messages:
            parts.append(f"[{m['sender']} -> {agent_name}] ({m['msg_type']}): {m['payload']}")
        return "\n".join(parts)

    def to_list(self) -> List[dict]:
        return [m.to_dict() for m in self.messages]
