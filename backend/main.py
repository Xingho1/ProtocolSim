"""FastAPI backend server exposing REST endpoints for network protocol simulations."""

import os
import mimetypes
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from backend.models import (
    BrowseRequest,
    MailRequest,
    StreamRequest,
    ProtocolTraceResponse,
    VideoInfo,
)
from backend.protocol_engine import (
    generate_browsing_trace,
    generate_mail_trace,
    generate_streaming_trace,
    list_server_videos,
    VIDEOS_DIR,
)

app = FastAPI(
    title="Dual-Panel Protocol Simulator API",
    description="Backend service providing real-time protocol traces for DNS, HTTP, SMTP (TCP), and UDP media streaming.",
    version="1.0.0",
)

# Enable CORS for frontend flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "service": "Protocol Simulation Engine",
        "version": "1.0.0",
    }


@app.post("/api/browse", response_model=ProtocolTraceResponse)
def simulate_browse(req: BrowseRequest):
    """
    Generate DNS query/response and full HTTP request/response for a URL.
    """
    return generate_browsing_trace(req)


@app.post("/api/mail", response_model=ProtocolTraceResponse)
def simulate_mail(req: MailRequest):
    """
    Generate full RFC 5321 SMTP conversation (EHLO, MAIL FROM, RCPT TO, DATA, QUIT)
    or execute real SMTP delivery if toggled on.
    """
    try:
        return generate_mail_trace(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/stream", response_model=ProtocolTraceResponse)
def simulate_stream(req: StreamRequest):
    """
    Generate video streaming protocol trace for real server video files or legacy streams.
    """
    return generate_streaming_trace(req)


@app.get("/api/videos")
def get_videos():
    """List all available video files in the server's videos/ directory."""
    return list_server_videos()


@app.get("/api/stream/video/{filename}")
def stream_video(filename: str, request: Request):
    """
    Stream a video file from the videos/ folder with HTTP 206 Partial Content support.
    Enables smooth playback and seeking in web video players.
    """
    clean_name = os.path.basename(filename)
    video_path = os.path.join(VIDEOS_DIR, clean_name)
    if not os.path.isfile(video_path):
        raise HTTPException(status_code=404, detail=f"Video '{clean_name}' not found on server")

    file_size = os.path.getsize(video_path)
    mime_type, _ = mimetypes.guess_type(video_path)
    mime_type = mime_type or "video/mp4"

    range_header = request.headers.get("range")
    if not range_header:
        def iter_full():
            with open(video_path, "rb") as f:
                while chunk := f.read(64 * 1024):
                    yield chunk

        return StreamingResponse(
            iter_full(),
            status_code=200,
            media_type=mime_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Content-Disposition": f'inline; filename="{clean_name}"',
            },
        )

    try:
        range_val = range_header.replace("bytes=", "").strip()
        parts = range_val.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))
        content_length = end - start + 1
    except Exception:
        raise HTTPException(status_code=416, detail="Requested Range Not Satisfiable")

    def iter_range():
        with open(video_path, "rb") as f:
            f.seek(start)
            remaining = content_length
            while remaining > 0:
                chunk_to_read = min(64 * 1024, remaining)
                data = f.read(chunk_to_read)
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": mime_type,
    }
    return StreamingResponse(iter_range(), status_code=206, headers=headers)


@app.post("/api/videos/upload")
async def upload_video(file: UploadFile = File(...)):
    """Upload a video file to the server's videos/ directory."""
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    clean_filename = os.path.basename(file.filename)
    dest_path = os.path.join(VIDEOS_DIR, clean_filename)
    with open(dest_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            buffer.write(chunk)
    return {"filename": clean_filename, "size": os.path.getsize(dest_path), "status": "uploaded"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
