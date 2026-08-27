"""Optional execution graph for replay, investigation, and research.

Deployments are not required to materialize this graph. It is derived from ledger traces.
"""

from __future__ import annotations

from typing import Any

from veritas.ports import LedgerStore

NODE_TYPES = frozenset(
    {"action", "agent", "principal", "resource", "tool", "approval", "capability", "state"}
)
EDGE_TYPES = frozenset(
    {
        "caused_by",
        "delegated_from",
        "reads_from",
        "writes_to",
        "approved_by",
        "consumes",
        "produces",
        "precedes",
    }
)


def graph_from_trace(ledger: LedgerStore, trace_id: str) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []
    previous_action: str | None = None

    def add_node(node_id: str, kind: str, label: str) -> None:
        nodes[node_id] = {"id": node_id, "kind": kind, "label": label}

    for item in ledger.trace(trace_id):
        payload = item["payload"]
        ntype = item["type"]
        if ntype == "ASIR":
            action_id = f"action:{payload.get('asir_hash', item['node_id'])}"
            add_node(action_id, "action", str(payload.get("action", "")))
            agent_id = f"agent:{payload.get('agent_id', '')}"
            add_node(agent_id, "agent", str(payload.get("agent_id", "")))
            principal_id = f"principal:{payload.get('principal', '')}"
            add_node(principal_id, "principal", str(payload.get("principal", "")))
            resource_id = f"resource:{payload.get('resource', '')}"
            add_node(resource_id, "resource", str(payload.get("resource", "")))
            edges.append({"type": "caused_by", "from": agent_id, "to": action_id})
            edges.append({"type": "delegated_from", "from": principal_id, "to": agent_id})
            edges.append({"type": "writes_to", "from": action_id, "to": resource_id})
            if previous_action is not None:
                edges.append({"type": "precedes", "from": previous_action, "to": action_id})
            previous_action = action_id
        elif ntype == "HUMAN_APPROVAL":
            approval_id = f"approval:{payload.get('approval_nonce', item['node_id'])}"
            add_node(approval_id, "approval", str(payload.get("approver", "")))
            if previous_action is not None:
                edges.append({"type": "approved_by", "from": previous_action, "to": approval_id})
        elif ntype == "CAPABILITY":
            cap_id = f"capability:{payload.get('cap_id', item['node_id'])}"
            add_node(cap_id, "capability", str(payload.get("cap_id", "")))
            if previous_action is not None:
                edges.append({"type": "produces", "from": previous_action, "to": cap_id})
        elif ntype == "PREPARE":
            resource_id = f"resource:{payload.get('resource_key', '')}"
            add_node(resource_id, "resource", str(payload.get("resource_key", "")))
            if previous_action is not None:
                edges.append({"type": "consumes", "from": previous_action, "to": resource_id})
        elif ntype == "TOOL_INPUT":
            tool_id = f"tool:{payload.get('action', 'tool')}"
            add_node(tool_id, "tool", str(payload.get("action", "tool")))
            cap_id = f"capability:{payload.get('cap_id', '')}"
            edges.append({"type": "reads_from", "from": tool_id, "to": cap_id})
    return {"trace_id": trace_id, "nodes": list(nodes.values()), "edges": edges}
