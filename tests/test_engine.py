"""Automated tests for the protocol engine logic across all three modes."""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.models import BrowseRequest, MailRequest, StreamRequest
from backend.protocol_engine import (
    generate_browsing_trace,
    generate_mail_trace,
    generate_streaming_trace,
)


def test_browsing_protocol():
    print("[Testing] Browsing Protocol Trace (TCP Handshakes for DNS & HTTP)...")
    req = BrowseRequest(url="https://python.org/downloads")
    trace = generate_browsing_trace(req)

    assert trace.mode == "browsing", f"Expected mode 'browsing', got {trace.mode}"
    assert trace.total_steps == 14, f"Expected 14 steps (TCP DNS Handshake/Query/Resp/Teardown + TCP HTTP Handshake/Req/Resp/Teardown), got {trace.total_steps}"

    commands = [s.command for s in trace.steps]
    protocols = [s.protocol for s in trace.steps]

    # Verify TCP steps for DNS
    assert any("TCP [SYN]" in c and "DNS" in c for c in commands), "Missing TCP SYN for DNS"
    assert any("TCP [SYN, ACK]" in c for c in commands), "Missing TCP SYN-ACK"
    assert any("TCP [ACK]" in c for c in commands), "Missing TCP ACK"
    assert "DNS" in protocols, "Missing DNS protocol steps"
    assert "TCP" in protocols, "Missing TCP protocol steps"

    # Verify DNS query and response
    dns_query_step = next(s for s in trace.steps if s.protocol == "DNS" and s.direction == "c2s")
    assert "python.org" in dns_query_step.command

    dns_resp_step = next(s for s in trace.steps if s.protocol == "DNS" and s.direction == "s2c")
    assert dns_resp_step.status_code == "NOERROR"
    assert "Resolved IP" in dns_resp_step.details

    # Verify TCP steps for Web server & HTTP
    assert any("TCP [SYN]" in c and "HTTP" in c for c in commands), "Missing TCP SYN for HTTP"
    assert any("GET /downloads HTTP/1.1" in s.raw_wire for s in trace.steps if s.protocol == "HTTP/1.1")
    assert any("200 OK" in s.command or "200" in (s.status_code or "") for s in trace.steps if s.protocol == "HTTP/1.1")
    assert trace.html_content is not None, "Expected html_content in browsing trace response"

    print("  [OK] Browsing protocol trace passed!")


def test_browsing_dns_failure():
    print("[Testing] Browsing DNS Failure / Non-Existent Domain Trace (with TCP transport)...")
    req = BrowseRequest(url="https://nonexistent-fake-domain-12345.xyz")
    trace = generate_browsing_trace(req)

    assert trace.mode == "browsing", f"Expected mode 'browsing', got {trace.mode}"
    assert trace.total_steps == 7, f"Expected 7 steps on DNS failure (TCP handshake, DNS Q/R, TCP teardown), got {trace.total_steps}"
    assert trace.metadata.get("failed") is True, "Expected metadata['failed'] to be True"
    assert trace.metadata.get("status_code") == "DNS_PROBE_FINISHED_NXDOMAIN"

    commands = [s.command for s in trace.steps]
    assert any("TCP [SYN]" in c for c in commands), "Missing TCP SYN handshake step"
    assert any("NXDOMAIN" in c for c in commands), "Missing NXDOMAIN response step"
    assert any("TCP [FIN, ACK]" in c for c in commands), "Missing TCP teardown step"

    assert trace.html_content is not None
    assert "This site can’t be reached" in trace.html_content
    print("  [OK] Browsing DNS failure trace passed!")


def test_mail_protocol():
    print("[Testing] Mail (SMTP) Protocol Trace (with L4 TCP Handshake & Teardown)...")
    req = MailRequest(
        to="security@corp.net",
        subject="Audit Complete",
        body="All checks passed.",
        sender="auditor@antigravity.net",
    )
    trace = generate_mail_trace(req)

    assert trace.mode == "mail", f"Expected mode 'mail', got {trace.mode}"
    assert trace.total_steps == 18, f"Expected 18 steps (3 TCP Handshake + 13 SMTP + 2 TCP Teardown), got {trace.total_steps}"

    commands = [s.command for s in trace.steps]
    protocols = [s.protocol for s in trace.steps]

    # Verify TCP Transport layer steps
    assert "TCP" in protocols, "Missing TCP protocol steps in mail trace"
    assert any("TCP [SYN]" in c for c in commands), "Missing TCP SYN handshake step"
    assert any("TCP [SYN, ACK]" in c for c in commands), "Missing TCP SYN-ACK handshake step"
    assert any("TCP [ACK] Seq=1 Ack=1" in c for c in commands), "Missing TCP ACK established step"
    assert any("TCP [FIN, ACK]" in c for c in commands), "Missing TCP FIN-ACK teardown step"

    # Verify key SMTP commands and codes
    assert any("220" in c for c in commands), "Missing 220 greeting"
    assert any("EHLO" in c for c in commands), "Missing EHLO"
    assert any("MAIL FROM" in c for c in commands), "Missing MAIL FROM"
    assert any("RCPT TO" in c for c in commands), "Missing RCPT TO"
    assert any("DATA" in c for c in commands), "Missing DATA"
    assert any("354" in c for c in commands), "Missing 354 Start Mail Input"
    assert any("QUIT" in c for c in commands), "Missing QUIT"

    # Verify commands_used metadata
    assert "commands_used" in trace.metadata, "Missing commands_used metadata"
    assert trace.metadata["commands_used"] == ["EHLO", "MAIL FROM", "RCPT TO", "DATA", "QUIT"]
    assert trace.metadata.get("transport") == "TCP"

    print("  [OK] Mail SMTP protocol trace passed!")


def test_mail_real_send_failure():
    print("[Testing] Mail Real Send Failure raises error...")
    # Missing credentials should raise ValueError
    req_missing = MailRequest(
        to="test@example.com",
        real_send=True,
        smtp_host="smtp.gmail.com",
    )
    try:
        generate_mail_trace(req_missing)
        assert False, "Should have raised ValueError on missing credentials"
    except (ValueError, RuntimeError) as e:
        assert "required" in str(e).lower()

    # Invalid connection should raise RuntimeError
    req_invalid = MailRequest(
        to="test@example.com",
        real_send=True,
        smtp_host="invalid-smtp-relay-domain.fake",
        smtp_port=587,
        smtp_user="user@example.com",
        smtp_password="password123",
    )
    try:
        generate_mail_trace(req_invalid)
        assert False, "Should have raised RuntimeError on connection failure"
    except RuntimeError as e:
        assert "could not be sent" in str(e).lower()

    print("  [OK] Mail real send failure properly raised errors!")





def test_modular_imports():
    print("[Testing] Modular Submodule Imports...")
    from backend.protocol_engine.browsing import generate_browsing_trace as mod_browse
    from backend.protocol_engine.mail import generate_mail_trace as mod_mail
    from backend.protocol_engine.streaming import generate_streaming_trace as mod_stream
    from backend.protocol_engine.utils import _get_simulated_ip, _get_http_date

    assert callable(mod_browse)
    assert callable(mod_mail)
    assert callable(mod_stream)
    assert callable(_get_simulated_ip)
    assert callable(_get_http_date)

    # Test that modular calls produce identical types
    b_trace = mod_browse(BrowseRequest(url="https://example.com"))
    assert b_trace.mode == "browsing"

    m_trace = mod_mail(MailRequest(to="test@example.com", subject="Test", body="Hi"))
    assert m_trace.mode == "mail"

    s_trace = mod_stream(StreamRequest(source_type="server_file", action="play"))
    assert s_trace.mode == "streaming"
    print("  [OK] Modular submodule imports passed!")


def test_server_video_streaming():
    print("[Testing] Server Video Streaming Engine (L4 UDP Transport)...")
    from backend.protocol_engine.streaming import list_server_videos

    videos = list_server_videos()
    assert len(videos) > 0, "Expected at least 1 video in videos/ directory"
    sample = videos[0]
    assert sample.filename.endswith((".mp4", ".webm", ".mov"))
    assert sample.size_bytes > 0

    req = StreamRequest(source_type="server_file", video_file=sample.filename, segment_index=1, action="play")
    trace = generate_streaming_trace(req)

    assert trace.mode == "streaming"
    assert trace.total_steps == 4
    assert trace.metadata.get("source_type") == "server_file"
    assert trace.metadata.get("video_file") == sample.filename
    assert trace.metadata.get("transport") == "UDP"

    commands = [s.command for s in trace.steps]
    protocols = [s.protocol for s in trace.steps]

    assert all(p == "UDP" for p in protocols), f"Expected all steps to be UDP, got {protocols}"
    assert any("UDP Datagram: Stream Request" in c for c in commands), "Missing UDP Datagram Request step"
    assert any("UDP Packet Header" in c for c in commands), "Missing UDP Packet Header step"
    assert any("UDP Media Burst" in c for c in commands), "Missing UDP Media Burst step"
    assert any("UDP Telemetry" in c for c in commands), "Missing UDP Telemetry step"

    # Test FastAPI Range Request handling
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app)

    # 1. GET /api/videos
    r_list = client.get("/api/videos")
    assert r_list.status_code == 200
    assert any(v["filename"] == sample.filename for v in r_list.json())

    # 2. GET /api/stream/video/{filename} with Range header
    r_stream = client.get(f"/api/stream/video/{sample.filename}", headers={"Range": "bytes=0-1023"})
    assert r_stream.status_code == 206
    assert "Content-Range" in r_stream.headers
    assert r_stream.headers["Content-Range"].startswith("bytes 0-1023/")
    assert len(r_stream.content) == 1024

    print("  [OK] Server video streaming and UDP transport steps passed!")


if __name__ == "__main__":
    test_modular_imports()
    test_browsing_protocol()
    test_browsing_dns_failure()
    test_mail_protocol()
    test_mail_real_send_failure()
    test_server_video_streaming()
    print("\nALL PROTOCOL TESTS PASSED SUCCESSFULLY!")
