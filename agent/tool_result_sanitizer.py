"""
Tool Result Sanitizer — Strips internal metadata from tool results before LLM injection.

Problem:
  Tools like skill_view, skills_list, memory, read_file, terminal etc. return
  rich JSON with internal fields (path, readiness_status, setup_needed,
  skill_dir, linked_files, etc.). The LLM sees these and may echo them
  in its reply, leaking system internals to end users.

Solution:
  A pre-injection sanitizer that runs on every tool result before it is
  packaged into a role="tool" message. This is defense-in-depth at the
  DATA LEVEL — the LLM literally never sees the sensitive fields.

Architecture:
  - Per-tool sanitizers: Known tools get custom extraction logic that keeps
    only user-meaningful content.
  - Generic JSON stripper: Unknown JSON tools have common internal fields removed.
  - Non-JSON passthrough: Plain-text results are left alone (they're usually
    already clean, e.g. terminal output, web search snippets).

Integration points:
  1. environments/agent_loop.py  — main agent loop (RL / training)
  2. model_tools.py           — handle_function_call() (CLI / gateway)
  3. gateway/run.py            — lightweight regex safety net (last resort)

Usage:
  from agent.tool_result_sanitizer import sanitize_tool_result
  clean_result = sanitize_tool_result(raw_result, tool_name)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)

# =============================================================================
# Field blacklist — internal fields that should NEVER reach the LLM context
# =============================================================================

# Fields that are purely operational/internal and have no value for the LLM's
# response to the user. These appear across many tools' JSON output.
_GENERIC_INTERNAL_FIELDS: Set[str] = {
    # Skill system internals
    "path",
    "skill_dir",
    "absolute_path",
    "readiness_status",
    "setup_needed",
    "setup_note",
    "compatibility",
    "metadata",
    "linked_files",
    "usage_hint",
    "required_environment_variables",
    "missing_required_environment_variables",
    "category",
    "tags",  # tags are for skill discovery, not for users
    "related_skills",
    "description",  # often redundant with content; LLM can infer from content
    # File system internals
    "_warning",
    "_stale",
    "line_count",
    "offset",
    "limit",
    # Execution metadata
    "exit_code",
    "returncode",
    "duration_ms",
    "timestamp",
    "task_id",
    # Memory system internals
    "memory_file",
    "memory_path",
    "session_id_internal",
    # Generic
    "version",
    "schema_version",
    "internal",
    "_internal",
}

# Tool names whose output should be aggressively simplified.
# For these tools, we ONLY keep a safe subset of fields.
_AGGRESSIVE_SANITIZE_TOOLS: Set[str] = {
    "skill_view",
    "skills_list",
    "skill_manage",
    "memory",
    "session_search",
    "read_file",
    "search_files",
    "search_content",  # if exists
}

# Safe fields to preserve for aggressive-sanitization tools.
# Everything else gets stripped.
_SKILL_VIEW_SAFE_FIELDS = {"success", "name", "content", "error", "message"}
_SKILLS_LIST_SAFE_FIELDS = {"success", "skills", "count", "error", "message"}
_MEMORY_SAFE_FIELDS = {"status", "saved", "retrieved", "summary", "error", "message"}
_READ_FILE_SAFE_FIELDS = {"content", "error", "message", "truncated"}
_SEARCH_SAFE_FIELDS = {"matches", "count", "error", "message", "truncated"}

# Map of tool_name -> safe field set
_TOOL_SAFE_FIELDS: Dict[str, Set[str]] = {
    "skill_view": _SKILL_VIEW_SAFE_FIELDS,
    "skills_list": _SKILLS_LIST_SAFE_FIELDS,
    "skill_manage": _SKILL_VIEW_SAFE_FIELDS,  # same structure as skill_view
    "memory": _MEMORY_SAFE_FIELDS,
    "read_file": _READ_FILE_SAFE_FIELDS,
    "search_files": _SEARCH_SAFE_FIELDS,
    "search_content": _SEARCH_SAFE_FIELDS,
    "session_search": _SEARCH_SAFE_FIELDS,
}


# =============================================================================
# Core sanitization functions
# =============================================================================


def _is_json(s: str) -> bool:
    """Check if a string looks like JSON (object or array)."""
    s = s.strip()
    return (s.startswith("{") and s.endswith("}")) or (
        s.startswith("[") and s.endswith("]")
    )


def _sanitize_skill_view(data: Dict[str, Any]) -> str:
    """
    Extract only user-meaningful content from skill_view result.

    Input (typical, ~20+ fields):
      { success, name, description, tags, related_skills, content,
        path, skill_dir, linked_files, usage_hint, readiness_status,
        setup_needed, setup_note, compatibility, metadata, ... }

    Output (only what the LLM needs to form a helpful reply):
      { content }   -- or { error } on failure
    """
    if data.get("success") is False or "error" in data:
        # Keep errors so the LLM knows something went wrong (but strip path info)
        msg = data.get("error", "Unknown error")
        # Strip paths from error messages
        msg = re.sub(r"/[^\s]*/\.hermes/skills/[^\s]*", "[skill path]", msg)
        msg = re.sub(r'/[^\s]*/\.hermes/skills/[^\s]*', "[skill path]", msg)
        return json.dumps({"error": msg}, ensure_ascii=False)

    # The primary value is `content` — the actual skill instructions.
    # The LLM needs this to use the skill knowledge in its reply.
    # Everything else (path, status, metadata) is operational noise.
    result: Dict[str, Any] = {}

    if data.get("content"):
        result["content"] = data["content"]
    elif data.get("name"):
        # Fallback: if no content, at least tell the LLM the skill name
        result["content"] = f"[Skill: {data['name']}]"

    return json.dumps(result, ensure_ascii=False)


def _sanitize_skills_list(data: Dict[str, Any]) -> str:
    """
    Simplify skills_list to just names + brief descriptions.

    Strips all per-skill metadata (paths, tags, categories, readiness, etc.)
    so the LLM sees a clean catalog.
    """
    if data.get("success") is False or "error" in data:
        return json.dumps({"error": data.get("error", "Unknown error")}, ensure_ascii=False)

    skills = data.get("skills", [])
    if isinstance(skills, list):
        simplified = []
        for s in skills:
            if isinstance(s, dict):
                entry: Dict[str, Any] = {}
                if s.get("name"):
                    entry["name"] = s["name"]
                if s.get("brief"):
                    entry["brief"] = s["brief"]
                elif s.get("description"):
                    # Truncate long descriptions to one line
                    desc = s["description"].split("\n")[0][:120]
                    entry["brief"] = desc
                simplified.append(entry)
            elif isinstance(s, str):
                simplified.append(s)
        return json.dumps(
            {"skills": simplified, "count": len(simplified)},
            ensure_ascii=False,
        )

    return json.dumps({"skills": [], "count": 0}, ensure_ascii=False)


def _sanitize_memory(data: Dict[str, Any]) -> str:
    """Strip memory system internals, keep only semantic content."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if k in _MEMORY_SAFE_FIELDS:
                cleaned[k] = v
        return json.dumps(cleaned, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)


def _sanitize_read_file(data: Dict[str, Any]) -> str:
    """Strip file path/line-count metadata, keep only content."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if k in _READ_FILE_SAFE_FIELDS:
                cleaned[k] = v
        return json.dumps(cleaned, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)


def _strip_generic_internal_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove known internal fields from any tool result dict.
    Used as fallback for tools without custom sanitizers.
    """
    if not isinstance(data, dict):
        return data

    return {k: v for k, v in data.items() if k not in _GENERIC_INTERNAL_FIELDS}


def _deep_clean(obj: Any) -> Any:
    """
    Recursively clean nested structures.
    - Removes None values from dicts
    - Cleans up empty containers
    - Ensures all string values are reasonable
    """
    if isinstance(obj, dict):
        return {k: _deep_clean(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [_deep_clean(item) for item in item if item is not None]
    elif isinstance(obj, str):
        # Strip control characters except newline
        return re.sub(r"[\x00-\x09\x0b\x0c\x0e-\x1f]", "", obj)
    return obj


# =============================================================================
# Public API
# =============================================================================


def sanitize_tool_result(raw_result: str, tool_name: str) -> str:
    """
    Sanitize a tool result string before it reaches the LLM context.

    This is the main entry point. Call it wherever tool results are
    packaged into conversation messages.

    Args:
        raw_result: The raw JSON string returned by the tool.
        tool_name: Name of the tool that produced the result.

    Returns:
        Sanitized JSON string safe for LLM injection.
        If the input isn't JSON or can't be parsed, returns it unchanged.
    """
    if not raw_result or not isinstance(raw_result, str):
        return raw_result

    if not _is_json(raw_result):
        # Non-JSON results (plain text like terminal output, web excerpts)
        # are already reasonably clean — pass through.
        # But do a light strip of obvious leaks.
        return _strip_text_leaks(raw_result)

    try:
        data = json.loads(raw_result)
    except (json.JSONDecodeError, ValueError):
        # Malformed JSON — don't break things, pass through
        return raw_result

    if not isinstance(data, dict):
        # Top-level array or primitive — pass through after deep cleaning
        return json.dumps(_deep_clean(data), ensure_ascii=False)

    # ── Per-tool specific sanitizers ──
    if tool_name == "skill_view":
        return _sanitize_skill_view(data)
    elif tool_name == "skills_list":
        return _sanitize_skills_list(data)
    elif tool_name == "memory":
        return _sanitize_memory(data)
    elif tool_name == "read_file":
        return _sanitize_read_file(data)
    elif tool_name in _AGGRESSIVE_SANITIZE_TOOLS:
        # Use safe-field whitelist for other known tools
        safe_fields = _TOOL_SAFE_FIELDS.get(tool_name)
        if safe_fields:
            cleaned = {k: v for k, v in data.items() if k in safe_fields}
            return json.dumps(_deep_clean(cleaned), ensure_ascii=False)

    # ── Generic fallback: strip known internal fields ──
    cleaned = _strip_generic_internal_fields(data)
    cleaned = _deep_clean(cleaned)

    return json.dumps(cleaned, ensure_ascii=False)


def _strip_text_leaks(text: str) -> str:
    """Light cleanup for non-JSON tool output text."""
    # Strip absolute paths to .hermes directory
    text = re.sub(r"/[^\s]*/\.hermes/[^\s]*", "[path]", text)
    text = re.sub(r'/[^\s]*/\.hermes/[^\s]*', "[path]", text)
    # Strip common leak patterns in plain text
    text = re.sub(r"skill_dir[:\s]+[^\s\n]+", "", text)
    text = re.sub(r"skill_view\(['\"][^'\"]*['\"]\)", "[loaded skill]", text)
    return text


# =============================================================================
# Statistics & diagnostics (optional, for debugging)
# =============================================================================

_sanitizer_stats: Dict[str, int] = {}


def get_sanitizer_stats() -> Dict[str, int]:
    """Return how many times each tool was sanitized (debug helper)."""
    return dict(_sanitizer_stats)


def reset_sanitizer_stats() -> None:
    """Reset statistics."""
    _sanitizer_stats.clear()
