"""Protocol simulation engine package.

Exposes trace generators and models for Browsing, Mail, and Streaming protocols,
with full backward compatibility.
"""

from backend.protocol_engine.browsing import generate_browsing_trace
from backend.protocol_engine.mail import (
    generate_mail_trace,
    _send_real_smtp,
)
from backend.protocol_engine.streaming import (
    generate_streaming_trace,
    list_server_videos,
    VIDEOS_DIR,
)
from backend.protocol_engine.utils import _get_simulated_ip, _get_http_date

__all__ = [
    "generate_browsing_trace",
    "generate_mail_trace",
    "generate_streaming_trace",
    "list_server_videos",
    "VIDEOS_DIR",
    "_get_simulated_ip",
    "_get_http_date",
    "_send_real_smtp",
]
