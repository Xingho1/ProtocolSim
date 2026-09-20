# ⚡ Dual-Panel Protocol Dashboard (FastAPI + Streamlit)

An interactive, high-fidelity network protocol simulation and inspection dashboard built with **FastAPI** and **Streamlit**.

The application features a synchronized dual-panel layout:
- **Left Panel (Activity Selector)**: Interactive user activity controller with three operational modes:
  - 🌐 **Browsing**: Target URL input, quick presets, and live visit trigger.
  - ✉️ **Mail**: Email composition form (`To`, `Subject`, `Body`, `Sender`) with realistic SMTP dispatch.
  - 🎬 **Streaming**: Video player simulator with `Play` / `Pause` toggle, quality selector (`480p`, `720p`, `1080p`, `4K`), buffer health meter, and segment fetcher.
- **Right Panel (Live Protocol Visualizer)**: Parallel, real-time packet inspector synchronized with user actions:
  - **Browsing Flow**: Complete DNS Query/Response (UDP 53, A-record resolution) followed by full HTTP/1.1 GET Request/Response cycle.
  - **Mail Flow**: Complete RFC 5321 SMTP conversation (`220` Greeting, `EHLO`, `250` Capabilities, `MAIL FROM`, `RCPT TO`, `DATA`, `354`, MIME Payload, `250 OK: queued`, `QUIT`, `221 Bye`).
  - **Streaming Flow**: DNS resolution for CDN, HLS Master Playlist request (`master.m3u8`), variant media playlist request (`index.m3u8`), and video segment streaming chunks (`seg_XXX.ts`) with adaptive bitrate.
  - **Playback Controls**: Step-by-step navigation (`⏮ Prev`, `⏯ Auto-Step Play/Pause`, `Next ⏭`, `🔄 Replay`, speed selector `0.5s` - `2.0s`, and progress scrub slider).
  - **Deep Packet Inspector**: Overview metrics, decoded protocol fields, and raw Wireshark-style wire protocol dumps.

---

## Architecture

```
f:/Assignment/
├── backend/
│   ├── __init__.py
│   ├── main.py              # FastAPI application exposing REST endpoints
│   ├── models.py            # Pydantic data models for traces and steps
│   ├── videos/              # Server storage for streaming video files (.mp4, .webm)
│   └── protocol_engine/     # Modular RFC-compliant protocol simulation engine
│       ├── __init__.py      # Package facade & re-exports
│       ├── utils.py         # Simulated IP & HTTP date utilities
│       ├── browsing.py      # DNS query/response + HTTP/1.1 GET engine
│       ├── mail.py          # RFC 5321 ESMTP dialogue & live SMTP engine
│       └── streaming.py     # Real server video streaming & HTTP 206 Range engine
├── frontend/
│   ├── __init__.py
│   ├── app.py               # Streamlit dual-panel web dashboard
│   ├── components.py        # Sequence ladder, packet inspector, video card
│   └── style.css            # Modern dark-mode high-tech design tokens
├── tests/
│   └── test_engine.py       # Automated test suite
├── run.py                   # One-click runner for FastAPI + Streamlit
├── requirements.txt         # Project dependencies
└── README.md                # Project documentation
```

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Application
Launch both the FastAPI backend and Streamlit dashboard with one command:
```bash
python run.py
```

- **Streamlit Web UI**: [http://localhost:8501](http://localhost:8501)
- **FastAPI OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

Alternatively, run them separately:
```bash
# Terminal 1 - Backend
uvicorn backend.main:app --port 8000 --reload

# Terminal 2 - Frontend
streamlit run frontend/app.py --server.port 8501
```

---

## Running Tests
```bash
python tests/test_engine.py
```
