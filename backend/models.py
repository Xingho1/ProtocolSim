"""Pydantic data models for requests, trace steps, and responses."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class BrowseRequest(BaseModel):
    url: str = Field(default="https://example.com", description="Target URL to visit")
    fetch_real: bool = Field(default=True, description="Attempt real HTTP fetch with fallback")


class MailRequest(BaseModel):
    to: str = Field(default="recipient@domain.com", description="Recipient email address")
    subject: str = Field(default="Project Status Update", description="Email subject")
    body: str = Field(default="Hello,\n\nThe system synchronization is complete.\n\nBest regards,\nAntigravity", description="Email body content")
    sender: str = Field(default="user@antigravity.net", description="Sender email address")
    real_send: bool = Field(default=False, description="Send real email via SMTP relay")
    smtp_host: Optional[str] = Field(default=None, description="SMTP server host (e.g. smtp.gmail.com)")
    smtp_port: Optional[int] = Field(default=587, description="SMTP server port (e.g. 587 or 465)")
    smtp_user: Optional[str] = Field(default=None, description="SMTP authentication username")
    smtp_password: Optional[str] = Field(default=None, description="SMTP authentication password / app password")
    use_tls: bool = Field(default=True, description="Enable STARTTLS")


class VideoInfo(BaseModel):
    filename: str
    size_bytes: int
    size_formatted: str
    format: str


class StreamRequest(BaseModel):
    video_file: str = Field(default="sample_stream.mp4", description="Video file in videos/ folder")
    action: str = Field(default="play", description="'play', 'pause', or 'seek'")
    quality: str = Field(default="1080p", description="Stream quality profile: 480p, 720p, 1080p, 4K")
    segment_index: int = Field(default=1, description="Current chunk or segment index")
    byte_offset: int = Field(default=0, description="Byte range start offset")
    source_type: str = Field(default="server_file", description="'server_file' or 'hls'")




class ProtocolStep(BaseModel):
    step_number: int
    timestamp_ms: float
    protocol: str  # DNS, HTTP/1.1, SMTP, TCP, MEDIA-STREAM
    layer: str     # Application (L7), Transport (L4 TCP/UDP)
    direction: str # "c2s" (Client -> Server) or "s2c" (Server -> Client)
    source_node: str
    dest_node: str
    command: str
    status_code: Optional[str] = None
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
    raw_wire: str
    duration_ms: float = 12.5


class ProtocolTraceResponse(BaseModel):
    mode: str
    title: str
    summary: str
    total_steps: int
    steps: List[ProtocolStep]
    html_content: Optional[str] = Field(default=None, description="HTML payload for browser rendering")
    metadata: Dict[str, Any] = Field(default_factory=dict)

