"""API endpoint tests using FastAPI TestClient."""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_api_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"
    print("  [OK] /api/health passed")


def test_api_browse():
    payload = {"url": "https://example.com/about"}
    resp = client.post("/api/browse", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "browsing"
    assert data["total_steps"] == 4
    assert len(data["steps"]) == 4
    # Check DNS then HTTP
    assert data["steps"][0]["protocol"] == "DNS"
    assert data["steps"][1]["protocol"] == "DNS"
    assert data["steps"][2]["protocol"] == "HTTP/1.1"
    assert data["steps"][3]["protocol"] == "HTTP/1.1"
    print("  [OK] /api/browse passed")


def test_api_mail():
    payload = {
        "to": "client@acme.org",
        "subject": "Deploy Update",
        "body": "System ready.",
        "sender": "ci@antigravity.net",
    }
    resp = client.post("/api/mail", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "mail"
    assert data["total_steps"] == 13
    assert data["steps"][0]["command"].startswith("220")
    assert data["steps"][-1]["command"].startswith("221")
    print("  [OK] /api/mail passed")


def test_api_stream():
    # Test server video file stream play action
    payload_file = {
        "source_type": "server_file",
        "video_file": "sample_stream.mp4",
        "action": "play",
        "segment_index": 1,
    }
    resp_file = client.post("/api/stream", json=payload_file)
    assert resp_file.status_code == 200
    data_file = resp_file.json()
    assert data_file["mode"] == "streaming"
    assert data_file["total_steps"] == 6
    assert any("206 Partial Content" in s["command"] for s in data_file["steps"])
    print("  [OK] /api/stream (server video file stream) passed")

    # Test pause action
    payload_pause = {"source_type": "server_file", "action": "pause", "video_file": "sample_stream.mp4", "segment_index": 1}
    resp_pause = client.post("/api/stream", json=payload_pause)
    assert resp_pause.status_code == 200
    data_pause = resp_pause.json()
    assert data_pause["mode"] == "streaming"
    assert any("Window Update" in s["command"] or "ACK" in s["command"] for s in data_pause["steps"])
    print("  [OK] /api/stream (pause) passed")


if __name__ == "__main__":
    print("[Testing] FastAPI Endpoints...")
    test_api_health()
    test_api_browse()
    test_api_mail()
    test_api_stream()
    print("\nALL API ENDPOINTS TESTED AND VERIFIED!")


