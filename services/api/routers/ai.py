"""AI Assistant Router — Grounded Citizen & Municipal Assistant (JalDrishti).

Safety Rules:
1. NEVER hallucinate flood predictions, depths, or shelters.
2. Ground responses in real-time PostGIS data, Open-Meteo rainfall, and hydrodynamic model runs.
3. Explicitly state data source, acquisition timestamp, and confidence status.
4. If data is unavailable, state so honestly without inventing numbers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.connection import get_db
from services.ai.operator import get_ai_operator, KNOWN_LOCATIONS

logger = structlog.get_logger()
router = APIRouter(prefix="/ai", tags=["AI Assistant"])


@router.get("/status")
async def get_ai_status():
    """Get operational status and configuration of AI Assistant."""
    operator = get_ai_operator()
    return {
        "status": "online",
        "assistant_name": "JalDrishti",
        "llm_provider": operator.llm_provider,
        "tools_registered": len(operator.tools),
        "grounding_enforced": True,
        "safety_rules_active": [
            "no_hallucinated_depths",
            "deterministic_tool_coupling",
            "provenance_and_timestamp_attribution",
            "hedged_predictions",
        ],
    }


@router.get("/tools")
async def list_ai_tools():
    """List all registered deterministic tools available to the AI Assistant."""
    operator = get_ai_operator()
    tools_list = []
    for name, tool in operator.tools.items():
        tools_list.append({
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        })
    return {
        "total_tools": len(tools_list),
        "tools": tools_list,
    }


@router.post("/chat")
async def chat_with_assistant(
    payload: Dict[str, Any] = Body(...),
    db: Optional[AsyncSession] = Depends(get_db),
):
    """Grounding-first conversational query endpoint for citizens & municipal operators."""
    message = str(payload.get("message", "")).strip()
    user_lat = payload.get("latitude")
    user_lon = payload.get("longitude")
    user_ward = payload.get("ward")

    if not message:
        raise HTTPException(status_code=400, detail="Query message cannot be empty")

    operator = get_ai_operator()
    result = await operator.process_query(
        user_message=message,
        latitude=user_lat or 19.076,
        longitude=user_lon or 72.877,
        ward=user_ward,
    )

    return result
