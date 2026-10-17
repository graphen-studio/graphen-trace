"""Minimal streaming OpenAI-compatible reverse proxy."""

from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from graphen_trace.config.settings import settings

router = APIRouter()
_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def proxy(path: str, request: Request) -> Response:
    """Streams a request and its response to the configured OpenAI API."""
    upstream_url = f"{settings.openai_upstream.rstrip('/')}/{path}"
    if request.url.query:
        upstream_url = f"{upstream_url}?{request.url.query}"
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in _HOP_BY_HOP
    }
    client = httpx.AsyncClient(timeout=None, follow_redirects=False)
    upstream_request = client.build_request(
        request.method,
        upstream_url,
        headers=headers,
        content=request.stream(),
    )
    try:
        upstream_response = await client.send(upstream_request, stream=True)
    except httpx.HTTPError as error:
        await client.aclose()
        return Response(str(error), status_code=502)

    async def stream_body() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream_response.aiter_raw():
                yield chunk
        finally:
            await upstream_response.aclose()
            await client.aclose()

    response_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower() not in _HOP_BY_HOP
    }
    return StreamingResponse(
        stream_body(),
        status_code=upstream_response.status_code,
        headers=response_headers,
    )
