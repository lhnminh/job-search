from __future__ import annotations

from typing import Any


STRING_ARRAY: dict[str, Any] = {"type": "array", "items": {"type": "string"}}

TAILOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["suggested_slug", "summary", "source_tex", "questions"],
    "properties": {
        "suggested_slug": {"type": "string"},
        "summary": STRING_ARRAY,
        "source_tex": {"type": "string"},
        "questions": STRING_ARRAY,
    },
}

BULLET_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "strengths",
        "concerns",
        "relevance_score",
        "clarity_score",
        "impact_score",
        "recommendation",
        "suggested_text",
        "question",
        "uses_unverified_fact",
    ],
    "properties": {
        "strengths": STRING_ARRAY,
        "concerns": STRING_ARRAY,
        "relevance_score": {"type": "integer", "minimum": 1, "maximum": 10},
        "clarity_score": {"type": "integer", "minimum": 1, "maximum": 10},
        "impact_score": {"type": "integer", "minimum": 1, "maximum": 10},
        "recommendation": {"type": "string", "enum": ["keep", "rewrite", "ask"]},
        "suggested_text": {"type": "string"},
        "question": {"type": "string"},
        "uses_unverified_fact": {"type": "boolean"},
    },
}

SECTION_ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["entry_title", "bullet_id", "action", "text", "reason"],
    "properties": {
        "entry_title": {"type": "string"},
        "bullet_id": {"type": "string"},
        "action": {"type": "string", "enum": ["keep", "replace", "remove", "add"]},
        "text": {"type": "string"},
        "reason": {"type": "string"},
    },
}

SECTION_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "strengths", "concerns", "actions"],
    "properties": {
        "summary": {"type": "string"},
        "strengths": STRING_ARRAY,
        "concerns": STRING_ARRAY,
        "actions": {"type": "array", "items": SECTION_ACTION_SCHEMA},
    },
}

VISUAL_ISSUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["page", "severity", "description"],
    "properties": {
        "page": {"type": "integer", "minimum": 1},
        "severity": {"type": "string", "enum": ["error", "warning"]},
        "description": {"type": "string"},
    },
}

VISUAL_QA_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["approved", "summary", "issues"],
    "properties": {
        "approved": {"type": "boolean"},
        "summary": {"type": "string"},
        "issues": {"type": "array", "items": VISUAL_ISSUE_SCHEMA},
    },
}

FACT_ISSUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["claim", "reason"],
    "properties": {
        "claim": {"type": "string"},
        "reason": {"type": "string"},
    },
}

FACT_AUDIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["approved", "summary", "unsupported_claims"],
    "properties": {
        "approved": {"type": "boolean"},
        "summary": {"type": "string"},
        "unsupported_claims": {"type": "array", "items": FACT_ISSUE_SCHEMA},
    },
}
