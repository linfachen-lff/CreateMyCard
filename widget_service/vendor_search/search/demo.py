"""Small local Web UI for exercising the Search decision chain."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from api_schema import SearchRequest

from .errors import InvalidSearchRequest
from .json_boundary import parse_search_http_request
from .repository import SQLiteTemplateDAO
from .retriever import get_default_search_service

MAX_REQUEST_BYTES = 1_000_000
DEMO_HTML = Path(__file__).with_name("demo.html")

app = FastAPI(title="Search 检索链路 Demo", docs_url=None, redoc_url=None)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(DEMO_HTML)


@app.post("/api/search")
async def run_search(request: Request) -> JSONResponse:
    """Validate the HTTP boundary, then invoke the existing Search service."""

    try:
        query, input_data = parse_search_http_request(
            await request.body(), max_bytes=MAX_REQUEST_BYTES
        )
    except InvalidSearchRequest as exc:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    service = get_default_search_service()
    result = service.search(SearchRequest(query=query, input_data=input_data))
    material: dict[str, object] | None = None
    if result.template_id and isinstance(service.template_dao, SQLiteTemplateDAO):
        matched = next(
            (
                item
                for item in service.template_dao.list_all()
                if item.template_id == result.template_id
            ),
            None,
        )
        if matched is not None:
            material = {
                "template_id": matched.template_id,
                "description": matched.description,
                "tags": list(matched.tags),
            }
    return JSONResponse({"search_result": result.to_dict(), "material": material})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Search Web demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8020)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
