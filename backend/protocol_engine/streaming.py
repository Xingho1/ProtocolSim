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
    server_endpoint = "UDP Media Server (127.0.0.1:5004)"

    steps: List[ProtocolStep] = []
    t = 0.0

    # Step 1: UDP Datagram Stream Request / Initialization
    steps.append(
        ProtocolStep(
            step_number=1,
            timestamp_ms=round(t, 1),
            protocol="UDP",
            layer="Transport (L4 UDP Datagram)",
            direction="c2s",
            source_node=client_endpoint,
            dest_node=server_endpoint,
            command=f"UDP Datagram: Stream Request [File: {target_video.filename}, Chunk #{seg_idx}]",
            status_code=None,
            summary=f"Player transmits connectionless UDP datagram to port 5004 requesting video chunk #{seg_idx} (Zero handshake latency, 8-byte header)",
            details={
                "Transport": "UDP (User Datagram Protocol)",
                "Connection": "Connectionless (No 3-way handshake)",
                "Source Port": 54320,
                "Dest Port": 5004,
                "Header Size": "8 bytes (Minimal overhead vs TCP 20-60 bytes)",
                "Checksum": "0x5E8B",
                "Length": "48 bytes",
            },
            raw_wire=f"UDP Header: Sport=54320 Dport=5004 Len=48 Csum=0x5E8B\nPayload: REQ_CHUNK id={seg_idx} file={target_video.filename} action={req.action}\r\n",
            duration_ms=4.5,
        )
    )
    t += 4.5

    # Step 2: UDP Packetization & Header Inspection
    steps.append(
        ProtocolStep(
            step_number=2,
            timestamp_ms=round(t, 1),
            protocol="UDP",
            layer="Transport (L4 UDP Packetization)",
            direction="s2c",
            source_node=server_endpoint,
            dest_node=client_endpoint,
            command=f"UDP Packet Header: Chunk #{seg_idx} ({format_bytes(chunk_len)}) Range: {start_byte}-{end_byte}",
            status_code="200 UDP-STREAM",
            summary=f"UDP media server packetizes {target_video.format} bitstream into sequence-numbered UDP datagrams without connection setup overhead",
            details={
                "Transport": "UDP",
                "Datagram Sequence": f"#{seg_idx}",
                "Range": f"{start_byte}-{end_byte} ({format_bytes(chunk_len)})",
                "Payload Type": f"Video/{target_video.format}",
                "Header Overhead": "8 bytes (vs TCP 20-60 bytes)",
                "Flow Control": "Rate-paced UDP burst",
            },
            raw_wire=f"UDP Datagram Header:\n  Source Port: 5004\n  Dest Port: 54320\n  Length: {min(chunk_len + 8, 65535)} bytes\n  Checksum: 0x82A1\nVideo Header Preview: {raw_hex_preview[:36]}...\r\n",
            duration_ms=6.8,
        )
    )
    t += 6.8

    # Step 3: UDP Binary Media Stream Delivery (Real-time Transmission)
    steps.append(
        ProtocolStep(
            step_number=3,
            timestamp_ms=round(t, 1),
            protocol="UDP",
            layer="Transport (L4 UDP Stream Transmission)",
            direction="s2c",
            source_node=server_endpoint,
            dest_node=client_endpoint,
            command=f"UDP Media Burst: Transmitting {format_bytes(chunk_len)} bitstream datagrams",
            status_code="STREAMING",
            summary=f"Server streams {format_bytes(chunk_len)} payload directly to player jitter buffer without waiting for acknowledgements",
            details={
                "Transport": "UDP",
                "File": target_video.filename,
                "Chunk Size": format_bytes(chunk_len),
                "Transmission Mode": "Real-time UDP Stream",
                "Progress": f"{round((end_byte / file_size) * 100, 1)}%",
                "Hex Signature": raw_hex_preview[:48],
            },
            raw_wire=f"[UDP BINARY MEDIA PAYLOAD: {chunk_len} bytes]\nUDP Header: 8 bytes | Data: {chunk_len} bytes\nHex Header:\n{raw_hex_preview}...\n",
            duration_ms=18.5,
        )
    )
    t += 18.5

    # Step 4: UDP Player Buffer & Jitter Telemetry
    steps.append(
        ProtocolStep(
            step_number=4,
            timestamp_ms=round(t, 1),
            protocol="UDP",
            layer="Transport (L4 UDP Datagram Ingestion)",
            direction="c2s",
            source_node=client_endpoint,
            dest_node=server_endpoint,
            command=f"UDP Telemetry: Chunk #{seg_idx} Ingested (Action: {req.action.upper()})",
            status_code="INGESTED",
            summary=f"Player jitter buffer receives UDP datagram stream. Zero retransmission delay ensures smooth continuous media playback without head-of-line blocking.",
            details={
                "Transport": "UDP",
                "Action": req.action,
                "Ingested Chunk": f"#{seg_idx}",
                "Retransmission Delay": "0 ms (Unacknowledged / Low Latency)",
                "Jitter Buffer": "Healthy",
                "Packet Loss": "0.0%",
            },
            raw_wire=f"UDP Telemetry: Ingested chunk={seg_idx} bytes={chunk_len} action={req.action} jitter=1.2ms loss=0.0%\r\n",
            duration_ms=5.0,
        )
    )

    return ProtocolTraceResponse(
        mode="streaming",
        title=f"Server Video Stream: {target_video.filename}",
        summary=f"Streaming '{target_video.filename}' ({format_bytes(file_size)}) from server folder via connectionless L4 UDP datagrams. Chunk #{seg_idx} ({format_bytes(chunk_len)}) delivered with zero handshake latency.",
        total_steps=len(steps),
        steps=steps,
        metadata={
            "source_type": "server_file",
            "video_file": target_video.filename,
            "transport": "UDP",
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
