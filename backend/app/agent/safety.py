"""Validation of LLM-generated aggregation pipelines.

The agent only ever runs read-only `aggregate` calls. Any stage or operator that
can write data or execute server-side JavaScript is rejected before execution.
"""
from typing import Any

from bson import json_util

from app.config import settings

FORBIDDEN = {"$out", "$merge", "$function", "$accumulator", "$where", "$currentOp",
             "$listSessions", "$listLocalSessions", "$planCacheStats", "$collStats", "$indexStats"}


class UnsafePipelineError(ValueError):
    pass


def _walk(node: Any) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in FORBIDDEN:
                raise UnsafePipelineError(f"Operator {key} is not allowed (read-only agent).")
            _walk(value)
    elif isinstance(node, list):
        for item in node:
            _walk(item)


def parse_pipeline(pipeline_json: str) -> list[dict]:
    """Parse Extended JSON (so {"$date": "..."} becomes a datetime) and validate it."""
    # Tolerate common LLM formatting slips: markdown fences and "\$" escapes (invalid JSON).
    pipeline_json = pipeline_json.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    pipeline_json = pipeline_json.replace("\\$", "$")
    try:
        pipeline = json_util.loads(pipeline_json)
    except Exception as exc:  # noqa: BLE001 - surface any parse error to the LLM
        raise ValueError(f"Pipeline is not valid JSON: {exc}") from exc
    if not isinstance(pipeline, list) or not all(isinstance(s, dict) and len(s) == 1 for s in pipeline):
        raise ValueError("Pipeline must be a JSON array of single-key stage objects.")
    _walk(pipeline)
    if not any("$limit" in stage for stage in pipeline):
        pipeline.append({"$limit": settings.max_result_docs})
    return pipeline
