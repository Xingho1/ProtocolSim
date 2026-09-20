"""Server-side video streaming protocol engine.

Streams real video files from the server's `videos/` folder to the frontend,
generating wire-level protocol traces for HTTP Range requests (RFC 7233)
and real-time media chunk packetization.
"""

import os
import mimetypes
from typing import List, Dict, Any, Optional

from backend.models import (
    StreamRequest,
    ProtocolStep,
    ProtocolTraceResponse,
    VideoInfo,
)

# Directory where server videos are stored
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEOS_DIR = os.path.join(BACKEND_DIR, "videos")



def format_bytes(size: int) -> str:
    """Format bytes into human readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def list_server_videos() -> List[VideoInfo]:
    """Scan and list all playable video files in the videos/ directory."""
    if not os.path.exists(VIDEOS_DIR):
        os.makedirs(VIDEOS_DIR, exist_ok=True)

    allowed_exts = {".mp4", ".webm", ".mov", ".mkv", ".ts", ".m4v"}
    videos: List[VideoInfo] = []

    try:
        for fname in os.listdir(VIDEOS_DIR):
            ext = os.path.splitext(fname)[1].lower()
            if ext in allowed_exts:
                fpath = os.path.join(VIDEOS_DIR, fname)
                if os.path.isfile(fpath):
                    sz = os.path.getsize(fpath)
                    videos.append(
                        VideoInfo(
                            filename=fname,
                            size_bytes=sz,
                            size_formatted=format_bytes(sz),
                            format=ext.replace(".", "").upper(),
                        )
                    )
    except Exception:
        pass

    videos.sort(key=lambda v: v.filename)
    return videos


def _generate_server_file_trace(req: StreamRequest) -> ProtocolTraceResponse:
    """Generate real protocol trace for a video file stored in videos/."""
    available = list_server_videos()
    video_filename = req.video_file.strip() if req.video_file else ""

    # Pick requested video or first available
    target_video = None
    if video_filename:
        for v in available:
            if v.filename == video_filename:
                target_video = v
                break

    if not target_video and available:
        target_video = available[0]

    if not target_video:
        # No videos found in directory
        return ProtocolTraceResponse(
            mode="streaming",
            title="Server Video Stream: No Video Files",
            summary=f"No video files found in {VIDEOS_DIR}. Add .mp4 or .webm files to start streaming.",
            total_steps=1,
            steps=[
                ProtocolStep(
                    step_number=1,
                    timestamp_ms=0.0,
                    protocol="HTTP/1.1",
                    layer="Application (L7)",
                    direction="s2c",
                    source_node="Video Streaming Server (127.0.0.1:8000)",
                    dest_node="Frontend Video Player (127.0.0.1)",
                    command="404 Not Found (No Videos in Server Folder)",
                    status_code="404",
                    summary=f"Place an .mp4 or .webm file into {VIDEOS_DIR}",
                    details={"Folder": VIDEOS_DIR, "Status": "Empty"},
                    raw_wire="HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n",
                    duration_ms=5.0,
                )
            ],
            metadata={"video_file": None, "total_bytes": 0, "available_videos": []},
        )

    file_path = os.path.join(VIDEOS_DIR, target_video.filename)
    file_size = target_video.size_bytes
    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "video/mp4"

    # Chunk parameters (default 512 KB)
    chunk_size = 512 * 1024
    seg_idx = max(1, req.segment_index)
    start_byte = (seg_idx - 1) * chunk_size
    if start_byte >= file_size:
        start_byte = max(0, file_size - chunk_size)
    end_byte = min(start_byte + chunk_size - 1, file_size - 1)
    chunk_len = end_byte - start_byte + 1

    # Read real byte header from video file for packet inspector
    raw_hex_preview = ""
    try:
        with open(file_path, "rb") as vf:
            vf.seek(start_byte)
            header_sample = vf.read(min(chunk_len, 64))
            raw_hex_preview = " ".join(f"{b:02X}" for b in header_sample)
    except Exception:
        raw_hex_preview = "00 00 00 18 66 74 79 70 69 73 6F 6D"

    client_endpoint = "Frontend Player (127.0.0.1:54320)"
    server_endpoint = "FastAPI Video Server (127.0.0.1:8000)"

    steps: List[ProtocolStep] = []
    t = 0.0

    # Step 1: TCP Handshake (SYN, SYN-ACK, ACK)
    steps.append(
        ProtocolStep(
            step_number=1,
            timestamp_ms=t,
            protocol="TCP",
            layer="Transport (L4 TCP 3-Way Handshake)",
            direction="c2s",
            source_node=client_endpoint,
            dest_node=server_endpoint,
            command="TCP [SYN] Seq=0 Win=65535 MSS=1460 WS=256",
            status_code=None,
            summary=f"Player establishes reliable L4 TCP socket with video server at 127.0.0.1:8000",
            details={
                "Flags": "[SYN]",
                "Window Size": "65,535 bytes",
                "MSS": "1460 bytes (Standard MTU 1500)",
            },
            raw_wire="TCP SYN: Sport=54320 Dport=8000 Seq=0 Ack=0 Win=65535",
            duration_ms=6.5,
        )
    )
    t += 6.5

    # Step 2: TCP Connection Established
    steps.append(
        ProtocolStep(
            step_number=2,
            timestamp_ms=t,
            protocol="TCP",
            layer="Transport (L4 TCP Handshake Complete)",
            direction="s2c",
            source_node=server_endpoint,
            dest_node=client_endpoint,
            command="TCP [SYN, ACK] Seq=0 Ack=1 Win=65535",
            status_code="ESTABLISHED",
            summary="Server accepts TCP socket channel for continuous media streaming",
            details={"Flags": "[SYN, ACK]", "Status": "Socket ESTABLISHED"},
            raw_wire="TCP SYN-ACK: Sport=8000 Dport=54320 Seq=0 Ack=1 Win=65535",
            duration_ms=5.2,
        )
    )
    t += 5.2

    # Step 3: Client HTTP Range Request
    req_uri = f"/api/stream/video/{target_video.filename}"
    raw_range_req = (
        f"GET {req_uri} HTTP/1.1\r\n"
        f"Host: 127.0.0.1:8000\r\n"
        f"Range: bytes={start_byte}-{end_byte}\r\n"
        f"Accept: {mime_type}, video/*;q=0.9, */*;q=0.8\r\n"
        f"User-Agent: Mozilla/5.0 (HTML5 Media Source Engine)\r\n"
        f"Connection: keep-alive\r\n\r\n"
    )
    steps.append(
        ProtocolStep(
            step_number=3,
            timestamp_ms=t,
            protocol="HTTP/1.1",
            layer="Application (L7 HTTP Range Request)",
            direction="c2s",
            source_node=client_endpoint,
            dest_node=server_endpoint,
            command=f"GET {req_uri} (Range: bytes={start_byte}-{end_byte})",
            status_code=None,
            summary=f"HTML5 video player requests chunk #{seg_idx} ({format_bytes(chunk_len)}) via HTTP Range header",
            details={
                "Method": "GET",
                "Range Header": f"bytes={start_byte}-{end_byte}",
                "Requested Bytes": chunk_len,
                "Segment Index": seg_idx,
            },
            raw_wire=raw_range_req,
            duration_ms=12.0,
        )
    )
    t += 12.0

    # Step 4: Server HTTP 206 Partial Content Response Header
    raw_206_resp = (
        f"HTTP/1.1 206 Partial Content\r\n"
        f"Content-Type: {mime_type}\r\n"
        f"Content-Range: bytes {start_byte}-{end_byte}/{file_size}\r\n"
        f"Content-Length: {chunk_len}\r\n"
        f"Accept-Ranges: bytes\r\n"
        f"Connection: keep-alive\r\n\r\n"
    )
    steps.append(
        ProtocolStep(
            step_number=4,
            timestamp_ms=t,
            protocol="HTTP/1.1",
            layer="Application (L7 Partial Content)",
            direction="s2c",
            source_node=server_endpoint,
            dest_node=client_endpoint,
            command=f"HTTP/1.1 206 Partial Content (bytes {start_byte}-{end_byte}/{file_size})",
            status_code="206 Partial Content",
            summary=f"Server streams media chunk: bytes {start_byte} to {end_byte} of total {format_bytes(file_size)}",
            details={
                "Status Code": "206 Partial Content",
                "Content-Type": mime_type,
                "Content-Range": f"bytes {start_byte}-{end_byte}/{file_size}",
                "Content-Length": f"{chunk_len} bytes",
                "Total File Size": format_bytes(file_size),
            },
            raw_wire=raw_206_resp,
            duration_ms=15.0,
        )
    )
    t += 15.0

    # Step 5: Binary Media Payload Delivery
    steps.append(
        ProtocolStep(
            step_number=5,
            timestamp_ms=t,
            protocol="MEDIA-STREAM",
            layer=f"Payload ({target_video.format} Bitstream Chunks)",
            direction="s2c",
            source_node=server_endpoint,
            dest_node=client_endpoint,
            command=f"Stream Delivery: {format_bytes(chunk_len)} binary frame payload",
            status_code="200 STREAMING",
            summary=f"Buffered {format_bytes(chunk_len)} into HTML5 MediaSource buffer. Hex Header: [{raw_hex_preview[:32]}...]",
            details={
                "File": target_video.filename,
                "Chunk Transferred": format_bytes(chunk_len),
                "Hex Signature": raw_hex_preview[:48],
                "Progress": f"{round((end_byte / file_size) * 100, 1)}%",
            },
            raw_wire=f"[BINARY VIDEO PAYLOAD: {chunk_len} bytes]\nHex Header:\n{raw_hex_preview}...\n",
            duration_ms=22.0,
        )
    )
    t += 22.0

    # Step 6: Player TCP Window ACK / Buffer Status
    action_text = "Stream Active (Buffer Healthy)" if req.action == "play" else f"Playback State: {req.action.upper()}"
    steps.append(
        ProtocolStep(
            step_number=6,
            timestamp_ms=t,
            protocol="TCP",
            layer="Transport (Flow Control & Acknowledgement)",
            direction="c2s",
            source_node=client_endpoint,
            dest_node=server_endpoint,
            command=f"TCP [ACK] Window Update ({action_text})",
            status_code="ACK",
            summary=f"Player acknowledges chunk delivery. Buffer healthy, playback action: {req.action}",
            details={
                "Action": req.action,
                "Buffered Chunk": f"#{seg_idx}",
                "Bytes Received": f"{end_byte + 1} / {file_size}",
            },
            raw_wire=f"TCP ACK: Ack={end_byte + 1} Win=131072 Action={req.action}",
            duration_ms=8.0,
        )
    )

    return ProtocolTraceResponse(
        mode="streaming",
        title=f"Server Video Stream: {target_video.filename}",
        summary=f"Streaming '{target_video.filename}' ({format_bytes(file_size)}) from server folder via HTTP 206 Range requests. Chunk #{seg_idx} ({format_bytes(chunk_len)}) delivered.",
        total_steps=len(steps),
        steps=steps,
        metadata={
            "source_type": "server_file",
            "video_file": target_video.filename,
            "total_bytes": file_size,
            "total_formatted": format_bytes(file_size),
            "range_start": start_byte,
            "range_end": end_byte,
            "chunk_bytes": chunk_len,
            "chunk_formatted": format_bytes(chunk_len),
            "segment_index": seg_idx,
            "action": req.action,
            "mime_type": mime_type,
            "stream_url": f"/api/stream/video/{target_video.filename}",
            "available_videos": [v.model_dump() for v in available],
        },
    )


def generate_streaming_trace(req: StreamRequest) -> ProtocolTraceResponse:
    """Generate Streaming protocol trace for server video files."""
    return _generate_server_file_trace(req)
