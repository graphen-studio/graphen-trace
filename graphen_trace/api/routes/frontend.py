"""Routes for the compiled frontend application."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()
WEB_ROOT = Path(__file__).resolve().parents[2] / "web" / "dist"
RESERVED_PREFIXES = {"api", "v1"}


@router.get("/{asset_path:path}", include_in_schema=False)
async def serve_frontend(asset_path: str) -> FileResponse:
    """Serves a frontend asset or the SPA entry point."""

    if asset_path.split("/", maxsplit=1)[0] in RESERVED_PREFIXES:
        raise HTTPException(status_code=404)

    web_root = WEB_ROOT.resolve()
    requested = (web_root / asset_path).resolve()
    try:
        requested.relative_to(web_root)
    except ValueError as error:
        raise HTTPException(status_code=404) from error

    if requested.is_file():
        return FileResponse(requested)

    index = web_root / "index.html"
    if index.is_file():
        return FileResponse(index)

    raise HTTPException(status_code=404, detail="Frontend build not found")
