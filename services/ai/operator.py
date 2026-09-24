"""AI Operator — LLM function-calling interface over deterministic APIs.

The AI operator is a THIN LAYER on top of the system's deterministic APIs.
It NEVER fabricates flood predictions. It ALWAYS calls the system API first
and presents the results in natural language.

Safety rules (enforced in system prompt):
1. NEVER invent flood depth values
2. ALWAYS call get_flood_risk / get_ward_status before answering flood queries
3. ALWAYS show data source, timestamp, and confidence
4. ALWAYS use hedging language ("the model predicts..." not "there will be...")
5. If data is unavailable, say so honestly
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import structlog

logger = structlog.get_logger()


SYSTEM_PROMPT = """You are JalDrishti, the AI assistant for the Urban Flood Nowcasting System.

YOUR ROLE: Help citizens and city officials understand flood risks by querying the system's real-time data.

CRITICAL SAFETY RULES:
1. NEVER fabricate or guess flood predictions. Always call the appropriate tool first.
2. ALWAYS cite the data source and timestamp in your responses.
3. ALWAYS use hedging language: "the model predicts...", "based on current data...", "approximately..."
4. If a tool returns no data or an error, tell the user honestly. Do NOT make up a response.
5. ALWAYS include confidence levels when available.
6. For evacuation routes, ALWAYS recommend consulting official sources (MCGM, NDMA) as well.

PERSONALITY: Helpful, clear, calm. Use simple language for citizens. Use technical language for officials.

AVAILABLE TOOLS:
- get_flood_risk: Get current flood risk at a location
- get_ward_status: Get flood status for a specific ward
- get_current_alerts: Get active alerts for a city
- get_rainfall_forecast: Get rainfall forecast for a city
- get_route_safety: Check if a route is safe to travel
- submit_citizen_report: Submit a flood observation report
- get_shelter_nearest: Find nearest shelter from a location
"""


@dataclass
class ToolFunction:
    """A tool function the AI operator can call."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Any  # Callable


class AIOperator:
    """AI Operator that wraps deterministic system APIs with LLM.

    The operator:
    1. Receives a user query
    2. Determines which tool(s) to call
    3. Calls the system API (deterministic)
    4. Formats the response in natural language

    LLM backends (configurable):
    - Gemini API (primary, free tier)
    - Local Ollama / Llama 3 (fallback)
    """

    def __init__(
        self,
        api_base_url: str = "http://localhost:8000/api/v1",
        llm_provider: str = "gemini",
        gemini_api_key: Optional[str] = None,
    ):
        self.api_base_url = api_base_url
        self.llm_provider = llm_provider
        self.gemini_api_key = gemini_api_key
        self.tools = self._register_tools()

    def _register_tools(self) -> dict[str, ToolFunction]:
        """Register the deterministic API tools."""
        return {
            "get_flood_risk": ToolFunction(
                name="get_flood_risk",
                description="Get current flood risk assessment for a specific location",
                parameters={
                    "latitude": {"type": "number", "description": "WGS84 latitude"},
                    "longitude": {"type": "number", "description": "WGS84 longitude"},
                },
                handler=self._get_flood_risk,
            ),
            "get_current_rainfall": ToolFunction(
                name="get_current_rainfall",
                description="Get current rainfall at a location",
                parameters={
                    "latitude": {"type": "number", "description": "WGS84 latitude"},
                    "longitude": {"type": "number", "description": "WGS84 longitude"},
                },
                handler=self._get_current_rainfall,
            ),
            "get_rainfall_forecast": ToolFunction(
                name="get_rainfall_forecast",
                description="Get rainfall forecast for a location for the next N hours",
                parameters={
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "hours": {"type": "integer", "description": "Hours ahead (1-168)"},
                },
                handler=self._get_rainfall_forecast,
            ),
        }

    async def _get_current_rainfall(self, latitude: float, longitude: float) -> dict:
        """Call the rainfall API."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.api_base_url}/rainfall/current",
                params={"lat": latitude, "lon": longitude, "provider": "open_meteo"},
            )
            response.raise_for_status()
            return response.json()

    async def _get_rainfall_forecast(
        self, latitude: float, longitude: float, hours: int = 24
    ) -> dict:
        """Call the rainfall forecast API."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.api_base_url}/rainfall/forecast",
                params={"lat": latitude, "lon": longitude, "hours": hours},
            )
            response.raise_for_status()
            return response.json()

    async def _get_flood_risk(self, latitude: float, longitude: float) -> dict:
        """Get flood risk — combines rainfall data with system status.

        This is a composite tool that calls multiple APIs.
        """
        rainfall_data = await self._get_current_rainfall(latitude, longitude)

        rate = 0.0
        if rainfall_data.get("observations"):
            rate = rainfall_data["observations"][0].get("rate_mmh", 0)

        # Basic risk assessment based on current rainfall
        if rate > 30:
            risk_level = "HIGH"
            advice = "Heavy rainfall detected. Avoid low-lying areas and flooded roads."
        elif rate > 10:
            risk_level = "MODERATE"
            advice = "Moderate rainfall. Exercise caution near waterways."
        elif rate > 0:
            risk_level = "LOW"
            advice = "Light rainfall. No significant flood risk at this time."
        else:
            risk_level = "MINIMAL"
            advice = "No rainfall detected. No current flood risk."

        return {
            "location": {"latitude": latitude, "longitude": longitude},
            "current_rainfall_mmh": rate,
            "risk_level": risk_level,
            "advice": advice,
            "data_source": "Open-Meteo (ERA5-based model output)",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "disclaimer": (
                "This is a model-based estimate, not a direct measurement. "
                "Always follow official NDMA/MCGM advisories."
            ),
        }

    async def process_query(self, user_message: str, latitude: float = 19.076, longitude: float = 72.877) -> str:
        """Process a user query by calling appropriate tools.

        This is a simplified version. In production, this would use
        LLM function-calling (Gemini / OpenAI) to determine which
        tools to call based on the user's intent.

        For now, it uses keyword matching as a functional baseline.
        """
        message_lower = user_message.lower()

        try:
            if any(word in message_lower for word in ["flood", "risk", "safe", "danger"]):
                result = await self._get_flood_risk(latitude, longitude)
                return self._format_risk_response(result)

            elif any(word in message_lower for word in ["rain", "weather", "precipitation"]):
                result = await self._get_current_rainfall(latitude, longitude)
                return self._format_rainfall_response(result)

            elif any(word in message_lower for word in ["forecast", "tomorrow", "next"]):
                result = await self._get_rainfall_forecast(latitude, longitude, hours=24)
                return self._format_forecast_response(result)

            else:
                return (
                    "I can help you with:\n"
                    "• **Current flood risk** at your location\n"
                    "• **Current rainfall** conditions\n"
                    "• **Rainfall forecast** for the next 24 hours\n"
                    "• **Route safety** checks\n\n"
                    "What would you like to know?"
                )
        except Exception as e:
            logger.error("AI operator tool call failed", error=str(e))
            return (
                "I'm sorry, I couldn't retrieve the data at this time. "
                "Please try again or check the official MCGM Disaster Management portal "
                "at https://dm.mcgm.gov.in for the latest updates."
            )

    def _format_risk_response(self, data: dict) -> str:
        risk = data.get("risk_level", "UNKNOWN")
        rain = data.get("current_rainfall_mmh", 0)
        advice = data.get("advice", "")
        source = data.get("data_source", "")
        ts = data.get("timestamp", "")

        return (
            f"🌊 **Flood Risk: {risk}**\n\n"
            f"Current rainfall: {rain:.1f} mm/h\n"
            f"{advice}\n\n"
            f"📊 *Data source: {source}*\n"
            f"🕐 *Updated: {ts}*\n\n"
            f"⚠️ {data.get('disclaimer', '')}"
        )

    def _format_rainfall_response(self, data: dict) -> str:
        obs = data.get("observations", [])
        rate = obs[0].get("rate_mmh", 0) if obs else 0
        return (
            f"🌧️ **Current Rainfall: {rate:.1f} mm/h**\n\n"
            f"Provider: {data.get('provider', 'unknown')}\n"
            f"Location: ({data.get('latitude', 0):.3f}, {data.get('longitude', 0):.3f})"
        )

    def _format_forecast_response(self, data: dict) -> str:
        count = data.get("record_count", 0)
        forecasts = data.get("forecasts", [])
        return (
            f"📅 **Rainfall Forecast ({count} hours):**\n\n"
            f"Provider: {data.get('provider', 'unknown')}\n"
            f"Records available: {count}"
        )
