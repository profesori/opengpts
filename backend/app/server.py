import logging
import os
from pathlib import Path

import orjson
from fastapi import FastAPI, Form, UploadFile
from fastapi.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles

import app.storage as storage
from app.api import router as api_router
from app.auth.handlers import AuthedUser
from app.lifespan import lifespan
from app.upload import ingest_runnable

logger = logging.getLogger(__name__)

app = FastAPI(title="OpenGPTs API", lifespan=lifespan)

# Get root of app, used to point to directory containing static files
ROOT = Path(__file__).parent.parent

""" class streamVapiMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[JSONResponse]]):
        # Read the request body as JSON
        # Check if the URL path matches the specific API endpoint
        if re.match(r"^/runs/[a-f0-9\-]+/chat/completions$", request.url.path):
            body = await request.json()
            print('Request', body, request.headers)

        # Continue processing the request
        response = await call_next(request)
        return response

# Add the middleware to the app
app.add_middleware(streamVapiMiddleware) """

app.include_router(api_router)

@app.post("/ingest", description="Upload files and/or urls to the given assistant.")
async def ingest_files(
    user: AuthedUser, files: list[UploadFile] | None = None, url: str | None = Form(...), config: str = Form(...)
) -> None:
        
    """Ingest a list of files."""
    config = orjson.loads(config)

    assistant_id = config["configurable"].get("assistant_id")
    if assistant_id is not None:
        assistant = await storage.get_assistant(user["user_id"], assistant_id)
        if assistant is None:
            raise HTTPException(status_code=404, detail="Assistant not found.")

    thread_id = config["configurable"].get("thread_id")
    if thread_id is not None:
        thread = await storage.get_thread(user["user_id"], thread_id)
        if thread is None:
            raise HTTPException(status_code=404, detail="Thread not found.")
        
    print(files, url, config)

    if files:
        print('ingesting files', files)
        ingest_runnable.batch([file.file for file in files], config)

    if url:
        ingest_runnable.invoke(url, config)

    return True

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


ui_dir = str(ROOT / "ui")

if os.path.exists(ui_dir):
    app.mount("", StaticFiles(directory=ui_dir, html=True), name="ui")
else:
    logger.warn("No UI directory found, serving API only.")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8100)
