# Project Documentation: Tools & Technologies

---

## 👤 Project & Author Information

- **Author:** Jonak Pratim Thakuria
- **Roll Number:** 202402021060
- **Repository:** https://github.com/Xingho1/ProtocolSim
- **Live Production URL:** https://protocolsim.onrender.com/

---

## 🤖 AI Platforms Used

- **ChatGPT** (OpenAI) – Architecture design, concept ideation, and initial prototyping.
- **Antigravity** (Google DeepMind) – Full-stack agentic development, debugging, iterative refactoring, UI overhaul, deployment readiness, and protocol packet simulation.

---

## 🛠️ Technologies & Stack

### 1. Backend Core & API Architecture
- **Python 3.10+**: Core programming language powering both backend network engines and frontend visualization.
- **FastAPI**: Modern, high-performance web framework for building REST APIs and asynchronous endpoints.
- **Uvicorn**: Lightning-fast ASGI web server implementation used for hosting FastAPI services.
- **Pydantic (v2)**: Data validation, settings management, and structured request/response serialization.
- **Asyncio**: Python standard library for cooperative multitasking, asynchronous network operations, and concurrent requests.

### 2. Networking & Protocol Simulation Engine
- **Scapy**: Comprehensive packet manipulation, protocol header dissection, and packet layer analysis (DNS, TCP, HTTP, UDP, ICMP).
- **dnspython (dns.resolver, dns.message, dns.query)**: Complete DNS protocol inspection, wire-format query generation, RRsets, TTL parsing, and response code validation (NOERROR, NXDOMAIN, etc.).
- **Socket Programming (socket)**: Low-level UDP and TCP socket manipulation for simulating chunk-based, real-time packet transmission and latency emulation.
- **smtplib & ssl**: Standard SMTP protocol client simulating email transactions with STARTTLS encryption negotiation and MIME message handling.
- **Requests / HTTPX**: HTTP client libraries used for HTTP/1.1 and HTTP/2 request lifecycle tracing, header exchanges, status code validation, and content retrieval.

### 3. Media Processing & Video Streaming
- **OpenCV (cv2)**: Computer vision library for extracting video metadata (FPS, frame count, resolution), frame-by-frame decoding, JPEG compression, and chunked byte generation.
- **Custom UDP Video Streamer**: Protocol simulation engine breaking video assets into timestamped, sequence-numbered UDP packet payloads to demonstrate real-time packet loss, throughput, and jitter.

### 4. Frontend & User Interface
- **Streamlit**: Modern Python UI framework delivering interactive, reactive web dashboards.
- **Custom Modern CSS / Styling**: Handcrafted minimalistic light-mode theme featuring:
  - High-contrast, clean typography
  - Elevated status pill badges (SUCCESS, PENDING, FAILED)
  - Modular protocol pipeline cards
  - Responsive dual-pane layout (Simulation Controls & Execution vs. Protocol Inspection Pipeline)
- **HTML5 & CSS Components**: Embedded custom renderers for HTML source previews and secure sandboxed iframes.

### 5. DevOps, Containerization & Deployment
- **Docker**: Containerization platform providing deterministic builds across all host operating systems.
- **Docker Compose**: Multi-container service definition and orchestration (backend FastAPI service + frontend Streamlit dashboard).
- **Procfile**: Process manager configuration for containerless cloud platforms (Heroku, Render, Railway).
- **Git & GitHub**: Distributed version control, collaborative branch management, and repository hosting.

---

## 📂 Project Architecture Overview

```text
Assignment/
├── backend/
│   ├── app.py                     # FastAPI REST API & simulation endpoints
│   ├── protocol_engine/           # Modularized networking & protocol simulation
│   │   ├── browsing.py            # DNS resolution + TCP Handshake + HTTP/HTTPS fetch
│   │   ├── mail.py                # SMTP connection, STARTTLS handshake, MIME dispatch
│   │   ├── streaming.py           # UDP chunking, video frame pipeline, packet tracer
│   │   └── utils.py               # Packet dissection, header extraction, timing utilities
│   └── videos/                    # Local video repository for UDP streaming testbench
├── frontend/
│   ├── app.py                     # Main Streamlit dashboard UI
│   ├── components.py              # Visual UI widgets, status cards, protocol inspection cards
│   └── styles.py                  # Custom light-mode CSS design system
├── run.py                         # Single-command unified dual-process orchestrator
├── Dockerfile                     # Production multi-stage Docker build specification
├── docker-compose.yml             # Orchestration file for local & cloud containers
├── Procfile                       # Heroku / Render deployment process file
├── requirements.txt               # Pinned Python package dependencies
└── README.md                      # Setup and execution guide
```

---

## 🚀 Key Features Implemented

1. **Browsing Simulation (DNS + TCP + HTTP)**:
   - Real-world DNS lookups with complete header and RRset decomposition.
   - 3-Way TCP Handshake simulation (SYN, SYN-ACK, ACK).
   - HTTP/HTTPS request and response negotiation with source rendering.

2. **Email Simulation (SMTP + TLS)**:
   - End-to-end SMTP mail transaction tracing (EHLO, STARTTLS, AUTH, MAIL FROM, RCPT TO, DATA, QUIT).
   - Mock mode for offline demonstrations and live relay mode for real SMTP server testing.

3. **UDP Video Streaming Simulation**:
   - Server-side video chunking and frame packetization.
   - Simulation of realistic packet flow, sequence numbers, jitter, and packet delivery.

4. **Dual-Pane Interactive Pipeline**:
   - Left panel: Configuration, input parameters, and protocol controls.
   - Right panel: Visual, simplified step-by-step protocol flow with clear success/failure indicators.
