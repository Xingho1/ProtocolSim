"""Main Streamlit application for the Dual-Panel Protocol Dashboard."""

import os
import sys
import time
import requests
import streamlit as st

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.models import BrowseRequest, MailRequest, StreamRequest, VideoInfo
from backend.protocol_engine import (
    generate_browsing_trace,
    generate_mail_trace,
    generate_streaming_trace,
    list_server_videos,
    VIDEOS_DIR,
)
from frontend.components import (
    render_header,
    render_pipeline_chunks,
    render_sequence_ladder,
    render_packet_inspector,
    render_server_video_card,
    render_browser_viewer,
)

# Configuration
FASTAPI_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="Protocol Simulators",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Load CSS
css_path = os.path.join(os.path.dirname(__file__), "style.css")
if os.path.exists(css_path):
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# Helper: Fetch trace from FastAPI or direct fallback
def request_protocol_trace(endpoint: str, payload: dict) -> dict:
    """Fetch trace from FastAPI backend, with graceful fallback to protocol engine."""
    url = f"{FASTAPI_BASE_URL}/api/{endpoint}"
    timeout = 25.0 if payload.get("real_send") else 3.0
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 400:
            err_msg = resp.json().get("detail", "Error processing request")
            raise RuntimeError(err_msg)
    except requests.RequestException:
        pass

    # Direct fallback using local engine if backend isn't reachable
    if endpoint == "browse":
        trace_obj = generate_browsing_trace(BrowseRequest(**payload))
    elif endpoint == "mail":
        trace_obj = generate_mail_trace(MailRequest(**payload))
    elif endpoint == "stream":
        trace_obj = generate_streaming_trace(StreamRequest(**payload))
    else:
        raise ValueError(f"Unknown endpoint {endpoint}")
    return trace_obj.model_dump()


# Helper: Fetch video catalog from FastAPI via HTTP with fallback
def fetch_server_videos() -> list:
    """Fetch list of available streaming videos from FastAPI server via HTTP, with local fallback."""
    url = f"{FASTAPI_BASE_URL}/api/videos"
    try:
        resp = requests.get(url, timeout=2.5)
        if resp.status_code == 200:
            return [VideoInfo(**item) for item in resp.json()]
    except Exception:
        pass
    return list_server_videos()


# Session State Initialization
if "mode" not in st.session_state:
    st.session_state.mode = "Browsing"

if "trace" not in st.session_state:
    # Initialize with default browsing trace
    initial_trace = request_protocol_trace("browse", {"url": "https://example.com"})
    st.session_state.trace = initial_trace

if "current_step" not in st.session_state:
    st.session_state.current_step = 0

if "is_playing_auto" not in st.session_state:
    st.session_state.is_playing_auto = False

if "stream_is_playing" not in st.session_state:
    st.session_state.stream_is_playing = True

if "stream_quality" not in st.session_state:
    st.session_state.stream_quality = "1080p"

if "stream_segment" not in st.session_state:
    st.session_state.stream_segment = 1

if "selected_video_file" not in st.session_state:
    st.session_state.selected_video_file = "sample_stream.mp4"

if "auto_speed" not in st.session_state:
    st.session_state.auto_speed = 0.5


# Trigger synchronization helper with visual loading spinner
def trigger_action(endpoint: str, payload: dict):
    with st.spinner("⚡ Transmitting packets across the wire..."):
        new_trace = request_protocol_trace(endpoint, payload)
        st.session_state.trace = new_trace
        st.session_state.current_step = 0
        st.session_state.is_playing_auto = False


# Render Simple Minimal Header
render_header()

# Dual Panel Layout with explicit borders for both panes
left_col, right_col = st.columns([5, 7], gap="medium")

# ==============================================================================
# LEFT PANEL: Activity Selector (Browsing / Mail / Streaming)
# ==============================================================================
with left_col:
    with st.container(border=True):
        st.markdown(
            """
            <div class="panel-header">
                <span>ACTIVITY SELECTOR</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Highlighted Activity Mode Selector
        LABEL_TO_MODE = {
            "🌐 Browsing": "Browsing",
            "✉️ Mail": "Mail",
            "🎬 Streaming": "Streaming",
        }
        MODE_TO_LABEL = {v: k for k, v in LABEL_TO_MODE.items()}
        mode_options = list(LABEL_TO_MODE.keys())
        current_label = MODE_TO_LABEL.get(st.session_state.mode, "🌐 Browsing")

        selected_label = st.radio(
            "Choose Protocol Activity Mode:",
            mode_options,
            index=mode_options.index(current_label) if current_label in mode_options else 0,
            horizontal=True,
            key="activity_radio",
            label_visibility="collapsed",
        )
        selected_mode = LABEL_TO_MODE[selected_label]

        # Detect mode switch
        if selected_mode != st.session_state.mode:
            st.session_state.mode = selected_mode
            if selected_mode == "Browsing":
                trigger_action("browse", {"url": "https://example.com"})
            elif selected_mode == "Mail":
                trigger_action("mail", {
                    "to": "recipient@example.com",
                    "subject": "System Verification Update",
                    "body": "Hi there,\n\nAll protocol synchronization tests have succeeded.\n\nBest,\nAntigravity",
                    "sender": "user@antigravity.net"
                })
            elif selected_mode == "Streaming":
                trigger_action("stream", {
                    "source_type": "server_file",
                    "video_file": st.session_state.selected_video_file,
                    "action": "play" if st.session_state.stream_is_playing else "pause",
                    "segment_index": st.session_state.stream_segment,
                })
            st.rerun()

        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)

        # MODE 1: BROWSING
        if st.session_state.mode == "Browsing":
            st.markdown(
                """
                <div style="background: #f8fafc; padding: 10px 14px; border-radius: 6px; border: 1px solid #e2e8f0; margin-bottom: 12px;">
                    <div style="font-size: 0.85rem; font-weight: 700; color: #2563eb; margin-bottom: 2px;">
                        Web Browser & HTML Renderer
                    </div>
                    <div style="font-size: 0.76rem; color: #64748b;">
                        Simulates DNS resolution (UDP 53) and HTTP GET request/response with interactive visual rendering.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            url_input = st.text_input(
                "Target URL:",
                value="https://example.com",
                placeholder="https://example.com or https://python.org",
                key="browse_url_input",
            )

            preset_col1, preset_col2, preset_col3 = st.columns(3)
            with preset_col1:
                if st.button("🌐 example.com", use_container_width=True):
                    trigger_action("browse", {"url": "https://example.com", "fetch_real": True})
                    st.rerun()
            with preset_col2:
                if st.button("🐍 python.org", use_container_width=True):
                    trigger_action("browse", {"url": "https://python.org", "fetch_real": True})
                    st.rerun()
            with preset_col3:
                if st.button("📚 wikipedia.org", use_container_width=True):
                    trigger_action("browse", {"url": "https://en.wikipedia.org", "fetch_real": True})
                    st.rerun()

            col_fetch_opt, col_btn = st.columns([1.2, 1.8])
            with col_fetch_opt:
                fetch_real_live = st.checkbox("Live Web Request", value=True, help="Make actual network request to fetch real HTML")
            with col_btn:
                if st.button("🚀 Visit URL", type="primary", use_container_width=True):
                    trigger_action("browse", {"url": url_input, "fetch_real": fetch_real_live})
                    st.rerun()

            # Render HTML Browser Viewer
            active_trace = st.session_state.trace
            if active_trace and active_trace.get("mode") == "browsing":
                html_payload = active_trace.get("html_content", "")
                current_url = active_trace.get("metadata", {}).get("url", url_input)
                status_code = active_trace.get("metadata", {}).get("status_code", 200)
                is_live = active_trace.get("metadata", {}).get("is_live_fetch", False)
                render_browser_viewer(html_payload, current_url, status_code, is_live)

        # MODE 2: MAIL
        elif st.session_state.mode == "Mail":
            st.markdown(
                """
                <div style="background: #f8fafc; padding: 10px 14px; border-radius: 6px; border: 1px solid #e2e8f0; margin-bottom: 12px;">
                    <div style="font-size: 0.85rem; font-weight: 700; color: #d97706; margin-bottom: 2px;">
                        SMTP Mail Client (RFC 5321)
                    </div>
                    <div style="font-size: 0.76rem; color: #64748b;">
                        Simulates wire-level SMTP conversation (EHLO, MAIL FROM, RCPT TO, DATA, QUIT) with optional relay delivery.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown('<div class="form-section-header warning-theme">✉️ Message Envelope & Content</div>', unsafe_allow_html=True)
            mail_to = st.text_input("To (Recipient Email):", value="recipient@example.com", key="mail_to_input")
            mail_sender = st.text_input("From (Sender Email):", value="developer@antigravity.net", key="mail_sender_input")
            mail_subject = st.text_input("Subject:", value="System Verification Update", key="mail_sub_input")
            mail_body = st.text_area(
                "Body:",
                value="Hi there,\n\nThe live protocol dashboard is fully operational.\n\nAll DNS, HTTP, SMTP, and video streaming traces stream in real-time.\n\nRegards,\nAntigravity Agent",
                height=100,
                key="mail_body_input",
            )

            st.markdown('<div class="form-section-header warning-theme">⚙️ SMTP Relay & Authentication</div>', unsafe_allow_html=True)
            with st.expander("Configure Real SMTP Server (e.g. Gmail / Outlook Relay)"):
                st.info("💡 To deliver to external inboxes like Gmail, enter your SMTP server details. For Gmail, use an **App Password** from your Google Account > Security settings.")
                enable_real_smtp = st.checkbox("Deliver to real inbox via SMTP Relay", value=False, key="enable_real_smtp_box")
                c_host, c_port = st.columns([3, 1])
                with c_host:
                    smtp_server_host = st.text_input("SMTP Host", value="smtp.gmail.com")
                with c_port:
                    smtp_server_port = st.number_input("Port", value=587)
                smtp_username = st.text_input("SMTP Username / Email", placeholder="your.email@gmail.com")
                smtp_password = st.text_input("SMTP App Password", type="password", placeholder="16-character app password")

            if enable_real_smtp:
                st.caption("⚡ **Mode:** Live SMTP Relay | **Commands:** EHLO ➔ STARTTLS ➔ AUTH ➔ MAIL FROM ➔ RCPT TO ➔ DATA ➔ QUIT")
            else:
                st.caption("ℹ️ **Mode:** Simulation (RFC 5321) | **Commands:** EHLO ➔ MAIL FROM ➔ RCPT TO ➔ DATA ➔ QUIT")

            if st.button("📨 Send Email (Execute SMTP Handshake)", type="primary", use_container_width=True):
                payload = {
                    "to": mail_to,
                    "sender": mail_sender,
                    "subject": mail_subject,
                    "body": mail_body,
                    "real_send": enable_real_smtp,
                    "smtp_host": smtp_server_host if enable_real_smtp else None,
                    "smtp_port": int(smtp_server_port) if enable_real_smtp else 587,
                    "smtp_user": smtp_username if enable_real_smtp else None,
                    "smtp_password": smtp_password if enable_real_smtp else None,
                }
                try:
                    trigger_action("mail", payload)
                    st.session_state.mail_error = None
                    st.rerun()
                except Exception as e:
                    st.session_state.mail_error = str(e)
                    st.rerun()

            if st.session_state.get("mail_error"):
                st.error(f"❌ Mail Delivery Error: {st.session_state.mail_error}")

            # Status feedback if trace is mail
            active_trace = st.session_state.trace
            if active_trace and active_trace.get("mode") == "mail":
                cmd_list = active_trace.get("metadata", {}).get("commands_used", [])
                if cmd_list:
                    st.info("📡 **Commands Used:** " + " ➔ ".join(cmd_list))
                if active_trace.get("metadata", {}).get("real_send"):
                    if active_trace.get("metadata", {}).get("success"):
                        st.success(f"✅ Real email successfully sent to {mail_to}!")

        # MODE 3: STREAMING (Real Server Video Streaming Engine)
        elif st.session_state.mode == "Streaming":
            st.markdown(
                """
                <div style="background: #f8fafc; padding: 10px 14px; border-radius: 6px; border: 1px solid #e2e8f0; margin-bottom: 12px;">
                    <div style="font-size: 0.85rem; font-weight: 700; color: #16a34a; margin-bottom: 2px;">
                        Server Video Streaming
                    </div>
                    <div style="font-size: 0.76rem; color: #64748b;">
                        Stream video files from the server's <code>backend/videos/</code> directory directly via HTTP 206 Partial Content byte ranges.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Fetch available videos from server via HTTP REST API
            available_videos = fetch_server_videos()
            video_filenames = [v.filename for v in available_videos]

            # Video selector (clean full width, rescan removed)
            if video_filenames:
                if st.session_state.selected_video_file not in video_filenames:
                    st.session_state.selected_video_file = video_filenames[0]

                selected_v = st.selectbox(
                    "Select Video to Stream from Server:",
                    video_filenames,
                    index=video_filenames.index(st.session_state.selected_video_file),
                    key="server_video_select",
                )
                if selected_v != st.session_state.selected_video_file:
                    st.session_state.selected_video_file = selected_v
                    st.session_state.stream_segment = 1
                    trigger_action("stream", {
                        "source_type": "server_file",
                        "video_file": selected_v,
                        "action": "play",
                        "segment_index": 1,
                    })
                    st.rerun()

                # Video Streaming URL (HTTP 206 Partial Content byte ranges via FastAPI)
                video_stream_url = f"{FASTAPI_BASE_URL}/api/stream/video/{st.session_state.selected_video_file}"
                video_disk_path = os.path.join(VIDEOS_DIR, st.session_state.selected_video_file)

                # Streaming source: uses local disk path if present (ensures single-port cloud deployment works seamlessly)
                # or falls back to the FastAPI HTTP streaming URL
                player_source = video_disk_path if os.path.isfile(video_disk_path) else video_stream_url

                render_server_video_card(
                    video_source=player_source,
                    filename=st.session_state.selected_video_file,
                    is_playing=st.session_state.stream_is_playing,
                )

                if st.button("📡 Re-Simulate Stream Request", type="primary", use_container_width=True, help="Trigger HTTP 206 stream request simulation in Protocol Visualizer"):
                    trigger_action("stream", {
                        "source_type": "server_file",
                        "video_file": st.session_state.selected_video_file,
                        "action": "play",
                        "segment_index": 1,
                    })
                    st.session_state.current_step = 0
                    st.session_state.is_playing_auto = True
                    st.rerun()

            else:
                st.warning(f"⚠️ No video files found in server directory: `{VIDEOS_DIR}`")

            # Upload New Video Section
            with st.expander("📤 Upload New Video to Server (`backend/videos/`)"):
                st.info("Drop an `.mp4`, `.webm`, or `.mov` file to stream it immediately from your server.")
                uploaded_file = st.file_uploader(
                    "Select video file:",
                    type=["mp4", "webm", "mov", "mkv", "ts"],
                    key="video_upload_box",
                )
                if uploaded_file is not None:
                    if st.button("💾 Save to Server", type="primary", use_container_width=True):
                        dest_file_path = os.path.join(VIDEOS_DIR, uploaded_file.name)
                        with open(dest_file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        st.success(f"✅ Video '{uploaded_file.name}' saved to server folder!")
                        st.session_state.selected_video_file = uploaded_file.name
                        st.session_state.stream_segment = 1
                        trigger_action("stream", {
                            "source_type": "server_file",
                            "video_file": uploaded_file.name,
                            "action": "play",
                            "segment_index": 1,
                        })
                        st.rerun()



# ==============================================================================
# RIGHT PANEL: Protocol Visualizer (with clean pane border)
# ==============================================================================
with right_col:
    with st.container(border=True):
        st.markdown(
            """
            <div class="panel-header">
                <span>PROTOCOL PIPELINE</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Robust trace retrieval with automatic fallback
        trace = st.session_state.get("trace")
        if not trace:
            trace = request_protocol_trace("browse", {"url": "https://example.com"})
            st.session_state.trace = trace

        if hasattr(trace, "model_dump"):
            trace = trace.model_dump()
        elif not isinstance(trace, dict):
            trace = dict(trace) if trace else {}

        steps = trace.get("steps", [])
        if hasattr(steps, "values"):
            steps = list(steps.values())
        total_steps = len(steps)

        if total_steps == 0:
            st.info("No active protocol trace. Trigger an activity on the left.")
        else:
            # Clamp current step index
            if st.session_state.current_step >= total_steps:
                st.session_state.current_step = max(0, total_steps - 1)

            current_idx = st.session_state.current_step

            # Pipeline metadata banner as a native card
            with st.container(border=True):
                col_banner_text, col_banner_badge = st.columns([3.5, 1])
                with col_banner_text:
                    st.markdown(f"**{trace.get('title', 'Pipeline')}**")
                    if trace.get('summary'):
                        st.caption(trace.get('summary'))
                with col_banner_badge:
                    st.markdown(
                        f"<div style='text-align: right; font-family: monospace; font-size: 0.85rem; font-weight: 700; color: #2563eb; padding-top: 4px;'>Step {current_idx + 1} / {total_steps}</div>",
                        unsafe_allow_html=True,
                    )

            # Simplified Playback Controls
            c_prev, c_play, c_next, c_replay = st.columns([1, 1.6, 1, 1])

            with c_prev:
                if st.button("⏮ Prev", disabled=(current_idx <= 0), use_container_width=True):
                    st.session_state.current_step = max(0, current_idx - 1)
                    st.session_state.is_playing_auto = False
                    st.rerun()

            with c_play:
                play_label = "⏸ Pause" if st.session_state.is_playing_auto else "▶ Play Steps"
                if st.button(play_label, use_container_width=True):
                    st.session_state.is_playing_auto = not st.session_state.is_playing_auto
                    st.rerun()

            with c_next:
                if st.button("Next ⏭", disabled=(current_idx >= total_steps - 1), use_container_width=True):
                    st.session_state.current_step = min(total_steps - 1, current_idx + 1)
                    st.session_state.is_playing_auto = False
                    st.rerun()

            with c_replay:
                if st.button("🔄 Restart", use_container_width=True):
                    st.session_state.current_step = 0
                    st.session_state.is_playing_auto = True
                    st.rerun()

            # Clean pipeline progress bar
            st.progress(
                (current_idx + 1) / total_steps,
                text=f"Pipeline Progress: Step {current_idx + 1} of {total_steps}",
            )

            # Render simplified protocol pipeline chunks
            render_pipeline_chunks(steps, current_idx)

            # Handle Auto-Play step progression
            if st.session_state.is_playing_auto:
                if current_idx < total_steps - 1:
                    time.sleep(st.session_state.auto_speed)
                    st.session_state.current_step += 1
                    st.rerun()
                else:
                    st.session_state.is_playing_auto = False
                    st.rerun()
