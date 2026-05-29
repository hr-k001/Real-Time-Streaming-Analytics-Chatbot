from typing import Any, Literal

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, HttpUrl

from app.core.error_handler import structured_error, with_retry

_RETRYABLE = (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)


class RESTAPICallerInput(BaseModel):
    url: HttpUrl = Field(..., description="The HTTPS REST API endpoint to call.")
    method: Literal["GET"] = Field("GET", description="Only GET is supported for safety.")
    params: dict[str, str | int | float | bool] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)


@with_retry(max_attempts=3, delay_seconds=1.0, backoff_factor=2.0, retryable_exceptions=_RETRYABLE)
def _get_with_retry(
    url_str: str,
    params: dict[str, Any],
    headers: dict[str, str],
) -> httpx.Response:
    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        response = client.get(url_str, params=params, headers=headers)
        if response.status_code >= 500:
            raise httpx.RemoteProtocolError(
                f"Server returned {response.status_code}", request=response.request
            )
        return response


def call_rest_api(
    url: HttpUrl,
    method: Literal["GET"] = "GET",
    params: dict[str, str | int | float | bool] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    if method != "GET":
        return structured_error(
            tool="rest_api_caller",
            message="Only GET requests are supported.",
            error_type="UnsupportedMethod",
            suggestion="Change the method to GET.",
        )
    try:
        response = _get_with_retry(str(url), params or {}, headers or {})
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        data: Any = response.json() if "application/json" in content_type else response.text[:5000]
        return {"status_code": response.status_code, "data": data}
    except httpx.HTTPStatusError as exc:
        return structured_error(
            tool="rest_api_caller",
            message=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            error_type="HTTPError",
            suggestion="Check the URL and ensure the API is reachable.",
        )
    except Exception as exc:
        return structured_error(
            tool="rest_api_caller",
            message=f"REST API call failed: {exc}",
            error_type="NetworkError",
            retries_attempted=3,
            suggestion="Check network connectivity and verify the endpoint URL.",
        )


rest_api_caller_tool = StructuredTool.from_function(
    name="rest_api_caller",
    description="Call a live external REST API with a safe GET request and return JSON or text data.",
    func=call_rest_api,
    args_schema=RESTAPICallerInput,
)
