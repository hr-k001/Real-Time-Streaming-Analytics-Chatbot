from typing import Any, Literal

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, HttpUrl


class RESTAPICallerInput(BaseModel):
    url: HttpUrl = Field(..., description="The HTTPS REST API endpoint to call.")
    method: Literal["GET"] = Field("GET", description="Only GET is supported for safety.")
    params: dict[str, str | int | float | bool] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)


def call_rest_api(
    url: HttpUrl,
    method: Literal["GET"] = "GET",
    params: dict[str, str | int | float | bool] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        if method != "GET":
            return {"error": "Only GET requests are supported."}
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(str(url), params=params or {}, headers=headers or {})
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                data: Any = response.json()
            else:
                data = response.text[:5000]
            return {"status_code": response.status_code, "data": data}
    except Exception as exc:
        return {"error": f"REST API call failed: {exc}"}


rest_api_caller_tool = StructuredTool.from_function(
    name="rest_api_caller",
    description="Call a live external REST API with a safe GET request and return JSON or text data.",
    func=call_rest_api,
    args_schema=RESTAPICallerInput,
)
