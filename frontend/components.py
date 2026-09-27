"""Streamlit UI components for the Dual-Panel Protocol Dashboard."""

import html
import streamlit as st
from typing import List, Dict, Any, Optional


def is_status_error(status: Any) -> bool:
    """Return True if status code indicates an error/failure, correctly distinguishing NOERROR."""
    if not status:
        return False
    s = str(status).upper()
    if any(k in s for k in ["NOERROR", "OK", "SYN-ACK", "ESTABLISHED", "FIN-ACK", "CLOSED", "INGESTED", "STREAMING"]) or s.startswith(("200", "206", "220", "221", "235", "250", "354")):
        return False
    return any(err in s for err in ["NXDOMAIN", "FAIL", "ERROR", "SERVFAIL", "REFUSED"]) or s.startswith(("4", "5"))


def render_header():
    """Render top application banner with clean minimal style."""
    st.markdown(
        """
        <div class="header-simple">
            <div class="header-simple-title">Protocol Simulators</div>
            <div class="header-simple-badge">
                <span class="status-dot"></span>
                <span>Online</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sequence_ladder(steps: List[Dict[str, Any]], current_step_index: int):
    """
    Render visual packet sequence ladder showing Client <---> Server exchange.
    Features a live animated packet flight HUD and active step highlights.
    """
    if not steps:
        st.info("No protocol trace available. Initiate an action on the left panel to begin.")
        return

    # Extract current active step info for flight HUD
    safe_current_idx = max(0, min(current_step_index, len(steps) - 1))
    active_step = steps[safe_current_idx]
    active_dir = active_step.get("direction", "c2s")
    active_src = active_step.get("source_node", "Client")
    active_dst = active_step.get("dest_node", "Server")
    active_cmd = active_step.get("command", "")
    active_proto = active_step.get("protocol", "TCP")
    active_dur = active_step.get("duration_ms", 10.0)

    # Clean short labels for HUD
    short_src = active_src.split("(")[0].strip() if "(" in active_src else active_src
    short_dst = active_dst.split("(")[0].strip() if "(" in active_dst else active_dst
    short_cmd = active_cmd if len(active_cmd) <= 38 else (active_cmd[:35] + "...")

    # 1. LIVE WIRE PACKET FLIGHT HUD (Minimalist Light)
    hud_html = f"""
    <div class="wire-flight-hud">
        <div class="wire-flight-header">
            <div style="display: flex; align-items: center; gap: 6px;">
                <span class="status-dot"></span>
                <span style="font-weight: 700; color: #0f172a;">WIRE TRANSMISSION</span>
            </div>
            <div>
                <span style="color: #64748b;">LATENCY:</span> <b style="color: #2563eb;">+{active_dur}ms</b> | 
                <span style="color: #64748b;">STATUS:</span> <b style="color: #16a34a;">ACTIVE</b>
            </div>
        </div>
        <div class="wire-flight-track">
            <div class="wire-physical-cable"></div>
            <div class="wire-node-box">
                <span>💻</span>
                <span>{html.escape(short_src)}</span>
            </div>
            <div class="packet-capsule {active_dir}">
                ⚡ {html.escape(short_cmd)}
            </div>
            <div class="wire-node-box">
                <span>🖥️</span>
                <span>{html.escape(short_dst)}</span>
            </div>
        </div>
    </div>
    """

    # 2. SEQUENCE LADDER
    ladder_html = [hud_html, '<div class="ladder-container">']
    
    for idx, step in enumerate(steps):
        is_active = (idx == current_step_index)
        is_passed = (idx < current_step_index)
        
        state_class = "active" if is_active else ("passed" if is_passed else "")
        proto = step.get("protocol", "TCP")
        
        # Color mapping for protocol tags
        proto_lower = proto.lower()
        if "dns" in proto_lower:
            badge_class = "badge-dns"
        elif "http" in proto_lower:
            badge_class = "badge-http"
        elif "smtp" in proto_lower:
            badge_class = "badge-smtp"
        elif "tcp" in proto_lower:
            badge_class = "badge-tcp"
        elif "udp" in proto_lower:
            badge_class = "badge-udp"
        else:
            badge_class = "badge-stream"

        direction = step.get("direction", "c2s")
        if direction == "c2s":
            arrow_icon = "──▶" if not is_active else "⚡──▶"
            dir_class = "arrow-c2s"
        else:
            arrow_icon = "◀──" if not is_active else "◀──⚡"
            dir_class = "arrow-s2c"

        cmd_safe = html.escape(step.get("command", ""))
        summary_safe = html.escape(step.get("summary", ""))
        step_num = step.get("step_number", idx + 1)
        dur = step.get("duration_ms", 10.0)

        active_marker = ' <span style="background: #2563eb; color: #ffffff; font-size: 0.65rem; font-weight: 700; padding: 1px 6px; border-radius: 3px; letter-spacing: 0.5px;">IN TRANSIT</span>' if is_active else ""
        
        status_val = step.get("status_code")
        status_pill = ""
        if status_val:
            sc_str = str(status_val).upper()
            if is_status_error(status_val):
                status_pill = f'<span style="background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; padding: 1px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; margin-left: 6px;">FAILED ({html.escape(str(status_val))})</span>'
            elif "NOERROR" in sc_str or sc_str.startswith("200") or "206" in sc_str or "OK" in sc_str:
                status_pill = f'<span style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; padding: 1px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; margin-left: 6px;">{html.escape(str(status_val))}</span>'
            else:
                status_pill = f'<span style="background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; padding: 1px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; margin-left: 6px;">{html.escape(str(status_val))}</span>'

        arrow_rendered = f'<span class="beaming-arrow">{arrow_icon}</span>' if is_active else arrow_icon

        ladder_html.append(f"""
        <div class="ladder-item {state_class}">
            <div style="min-width: 28px; font-weight: 700; color: {'#2563eb' if is_active else '#64748b'}; font-size: 0.85rem;">
                #{step_num:02d}
            </div>
            <div>
                <span class="step-badge {badge_class}">{proto}</span>
            </div>
            <div class="{dir_class}" style="min-width: 48px; text-align: center;">
                {arrow_rendered}
            </div>
            <div style="flex-grow: 1;">
                <div style="font-weight: 600; font-size: 0.88rem; color: {'#1d4ed8' if is_active else '#0f172a'}; font-family: 'Fira Code', monospace;">
                    {cmd_safe}{status_pill}{active_marker}
                </div>
                <div style="font-size: 0.78rem; color: #64748b; margin-top: 2px;">
                    {summary_safe}
                </div>
            </div>
            <div style="font-size: 0.75rem; color: #64748b; font-family: 'Fira Code', monospace; white-space: nowrap;">
                +{dur}ms
            </div>
        </div>
        """)
        
    ladder_html.append('</div>')
    st.markdown("".join(ladder_html), unsafe_allow_html=True)


def render_packet_inspector(step: Dict[str, Any]):
    """
    Render deep packet inspection tabs:
    - Overview (Layer breakdown, Node endpoints, latency)
    - Decoded Headers & Fields
    - Raw Wire Format
    """
    if not step:
        st.warning("Select a step to inspect packet contents.")
        return

    proto = step.get("protocol", "PROTOCOL")
    layer = step.get("layer", "Application")
    src = step.get("source_node", "Client")
    dst = step.get("dest_node", "Server")
    cmd = step.get("command", "")
    summary = step.get("summary", "")
    status = step.get("status_code", "None")
    details = step.get("details", {})
    raw_wire = step.get("raw_wire", "")
    duration = step.get("duration_ms", 0.0)
    timestamp = step.get("timestamp_ms", 0.0)

    tab_overview, tab_fields, tab_raw = st.tabs([
        "🔍 Packet Overview", 
        "📑 Decoded Fields", 
        "💻 Raw Wire Format"
    ])

    with tab_overview:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Protocol & Layer", proto, delta=layer, delta_color="off")
        is_error_status = is_status_error(status)
        with col2:
            st.metric(
                "Status / Return",
                str(status) if status else "N/A",
                delta="Failed / Error" if is_error_status else "Delivered",
                delta_color="inverse" if is_error_status else "normal",
            )
        with col3:
            st.metric("Transmission Latency", f"{duration:.1f} ms", delta=f"T+ {timestamp:.1f}ms", delta_color="off")

        st.markdown(
            f"""
            <div style="background: #f8fafc; padding: 12px 16px; border-radius: 6px; border: 1px solid #e2e8f0; margin-top: 10px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 0.82rem;">
                    <span style="color: #64748b;">Source Endpoint:</span>
                    <span style="color: #2563eb; font-family: monospace; font-weight: 600;">{html.escape(src)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 0.82rem;">
                    <span style="color: #64748b;">Destination Endpoint:</span>
                    <span style="color: #7c3aed; font-family: monospace; font-weight: 600;">{html.escape(dst)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.82rem;">
                    <span style="color: #64748b;">Summary:</span>
                    <span style="color: #1e293b;">{html.escape(summary)}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with tab_fields:
        if details:
            field_rows = []
            for k, v in details.items():
                if isinstance(v, list):
                    v_display = ", ".join(map(str, v))
                else:
                    v_display = str(v)
                field_rows.append(
                    f"<tr>"
                    f"<td style='padding: 8px 12px; color: #2563eb; font-family: monospace; font-weight: 600; width: 35%; border-bottom: 1px solid #f1f5f9;'>{html.escape(k)}</td>"
                    f"<td style='padding: 8px 12px; color: #0f172a; font-family: monospace; border-bottom: 1px solid #f1f5f9;'>{html.escape(v_display)}</td>"
                    f"</tr>"
                )
            table_html = f"""
            <table style='width: 100%; border-collapse: collapse; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; overflow: hidden;'>
                <thead>
                    <tr style='background: #f8fafc; text-align: left; border-bottom: 1px solid #e2e8f0;'>
                        <th style='padding: 8px 12px; color: #475569; font-size: 0.76rem; text-transform: uppercase;'>Header / Parameter</th>
                        <th style='padding: 8px 12px; color: #475569; font-size: 0.76rem; text-transform: uppercase;'>Value</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(field_rows)}
                </tbody>
            </table>
            """
            st.markdown(table_html, unsafe_allow_html=True)
        else:
            st.info("No parsed structured fields available for this frame.")

    with tab_raw:
        st.markdown(
            f'<div class="wire-console">{html.escape(raw_wire)}</div>',
            unsafe_allow_html=True,
        )


def render_server_video_card(
    video_source: str,
    filename: str,
    is_playing: bool = False,
    filesize_str: Optional[str] = None,
    range_str: Optional[str] = None,
    chunk_index: Optional[int] = None,
):
    """
    Render a real HTML5 video player card with live stream status.
    """
    play_state_label = "STREAMING ACTIVE" if is_playing else "PAUSED"
    play_state_color = "#16a34a" if is_playing else "#d97706"
    badge_bg = "#f0fdf4" if is_playing else "#fffbeb"
    badge_border = "#bbf7d0" if is_playing else "#fde68a"

    st.markdown(
        f"""
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin: 10px 0;">
            <div style="padding: 8px 14px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e2e8f0; background: #ffffff;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="width: 8px; height: 8px; border-radius: 50%; background: {play_state_color};"></div>
                    <span style="font-size: 0.75rem; font-weight: 700; color: {play_state_color}; letter-spacing: 0.5px;">{play_state_label}</span>
                    <span style="color: #cbd5e1; font-size: 0.75rem;">•</span>
                    <span style="font-size: 0.75rem; color: #334155; font-family: monospace; font-weight: 600;">{html.escape(filename)}</span>
                </div>
                <div style="display: flex; gap: 8px; font-size: 0.75rem; font-family: monospace;">
                    <span style="background: {badge_bg}; color: {play_state_color}; border: 1px solid {badge_border}; padding: 2px 8px; border-radius: 4px; font-weight: 600;">HTTP 206 Stream</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Render actual video player
    if video_source:
        st.video(video_source, autoplay=is_playing)


def render_browser_viewer(html_content: str, url: str, status_code: Any = 200, is_live: bool = False):
    """
    Render an interactive browser viewport with Chrome/Edge-style address bar and live rendered HTML.
    """
    import streamlit.components.v1 as components_v1

    status_str = str(status_code)
    is_error = is_status_error(status_code)
    if status_str.startswith("2"):
        status_badge_color = "#16a34a"
        status_bg = "#f0fdf4"
        lock_icon = "🔒"
    elif is_error:
        status_badge_color = "#dc2626"
        status_bg = "#fef2f2"
        lock_icon = "⚠️"
    else:
        status_badge_color = "#d97706"
        status_bg = "#fffbeb"
        lock_icon = "🔒"

    live_label = "LIVE NETWORK FETCH" if is_live else ("DNS FAILED" if is_error else "RENDERED PREVIEW")

    st.markdown(
        f"""
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-top: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
            <!-- Browser Chrome Header -->
            <div style="background: #f8fafc; padding: 8px 12px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e2e8f0;">
                <div style="display: flex; align-items: center; gap: 6px;">
                    <div style="width: 9px; height: 9px; border-radius: 50%; background: #ef4444;"></div>
                    <div style="width: 9px; height: 9px; border-radius: 50%; background: #f59e0b;"></div>
                    <div style="width: 9px; height: 9px; border-radius: 50%; background: #10b981;"></div>
                </div>
                <div style="flex-grow: 1; max-width: 60%; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 10px; display: flex; align-items: center; gap: 6px; font-family: monospace; font-size: 0.76rem; color: #0f172a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    <span>{lock_icon}</span>
                    <span>{html.escape(url)}</span>
                </div>
                <div style="display: flex; gap: 6px;">
                    <span style="font-size: 0.68rem; font-weight: 600; background: {'#fef2f2' if is_error else '#eff6ff'}; color: {'#dc2626' if is_error else '#2563eb'}; padding: 2px 7px; border-radius: 4px;">{live_label}</span>
                    <span style="font-size: 0.68rem; font-weight: 600; background: {status_bg}; color: {status_badge_color}; padding: 2px 7px; border-radius: 4px;">{status_code}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    v_tab1, v_tab2 = st.tabs(["🌐 Rendered Page", "💻 HTML Source"])
    with v_tab1:
        if html_content:
            if hasattr(st, "iframe"):
                st.iframe(html_content, height=360)
            else:
                components_v1.html(html_content, height=360, scrolling=True)
        else:
            st.info("No HTML content received.")
    with v_tab2:
        if html_content:
            # Scrollable HTML Source Box to prevent stretching page
            st.markdown(
                f'<div class="scrollable-code-box">{html.escape(html_content)}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("No HTML source available.")


def render_pipeline_chunks(steps: List[Dict[str, Any]], current_step_index: int):
    """
    Render protocol pipeline steps where each step is shown in its own clean card container.
    """
    if not steps:
        st.info("No steps available to display.")
        return

    for idx, step in enumerate(steps):
        if hasattr(step, "model_dump"):
            step = step.model_dump()
        elif not isinstance(step, dict):
            step = dict(step) if step else {}

        is_active = (idx == current_step_index)
        is_passed = (idx < current_step_index)
        step_num = idx + 1

        proto = step.get("protocol", "TCP")
        proto_lower = proto.lower()
        if "dns" in proto_lower:
            badge_bg = "#f0fdfa"
            badge_color = "#0f766e"
            badge_border = "#99f6e4"
        elif "http" in proto_lower:
            badge_bg = "#eff6ff"
            badge_color = "#1d4ed8"
            badge_border = "#bfdbfe"
        elif "smtp" in proto_lower:
            badge_bg = "#fffbeb"
            badge_color = "#b45309"
            badge_border = "#fde68a"
        elif "tcp" in proto_lower:
            badge_bg = "#f5f3ff"
            badge_color = "#6d28d9"
            badge_border = "#ddd6fe"
        elif "udp" in proto_lower:
            badge_bg = "#fff7ed"
            badge_color = "#c2410c"
            badge_border = "#ffedd5"
        else:
            badge_bg = "#f0fdf4"
            badge_color = "#15803d"
            badge_border = "#bbf7d0"

        direction = step.get("direction", "c2s")
        if direction == "c2s":
            dir_text = "Client ➔ Server"
            dir_color = "#2563eb"
        else:
            dir_text = "Server ➔ Client"
            dir_color = "#7c3aed"

        cmd = step.get("command", "")
        summary = step.get("summary", "")
        status_val = step.get("status_code")
        layer_name = step.get("layer", "")

        # Render each step inside its own native card container
        with st.container(border=True):
            col_left, col_right = st.columns([3.8, 1.2])
            with col_left:
                status_html = ""
                if status_val:
                    sc_str = str(status_val).upper()
                    if is_status_error(status_val):
                        status_html = f'<span style="background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; padding: 1px 7px; border-radius: 4px; font-size: 0.72rem; font-weight: 600; margin-left: 6px;">FAILED ({html.escape(str(status_val))})</span>'
                    elif "NOERROR" in sc_str or sc_str.startswith("200") or "206" in sc_str or "OK" in sc_str:
                        status_html = f'<span style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; padding: 1px 7px; border-radius: 4px; font-size: 0.72rem; font-weight: 600; margin-left: 6px;">{html.escape(str(status_val))}</span>'
                    else:
                        status_html = f'<span style="background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; padding: 1px 7px; border-radius: 4px; font-size: 0.72rem; font-weight: 600; margin-left: 6px;">{html.escape(str(status_val))}</span>'

                layer_badge = ""
                if layer_name:
                    layer_badge = f'<span style="background: #f8fafc; color: #475569; border: 1px solid #e2e8f0; font-size: 0.67rem; font-weight: 600; padding: 2px 7px; border-radius: 4px; font-family: monospace;">{html.escape(layer_name)}</span>'

                header_html = (
                    f'<div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">'
                    f'<span style="font-weight: 700; font-size: 0.82rem; color: #0f172a; font-family: monospace;">Step {step_num:02d}</span>'
                    f'<span style="background: {badge_bg}; color: {badge_color}; border: 1px solid {badge_border}; font-size: 0.68rem; font-weight: 700; padding: 2px 7px; border-radius: 4px; text-transform: uppercase;">{html.escape(proto)}</span>'
                    f'<span style="font-size: 0.74rem; font-weight: 600; color: {dir_color}; font-family: monospace;">{dir_text}</span>'
                    f'{layer_badge}'
                    f'{status_html}'
                    f'</div>'
                )
                st.markdown(header_html, unsafe_allow_html=True)

            with col_right:
                if is_active:
                    st.markdown(
                        '<div style="text-align: right;"><span style="background: #2563eb; color: #ffffff; font-size: 0.68rem; font-weight: 700; padding: 2px 8px; border-radius: 9999px; letter-spacing: 0.5px;">● ACTIVE</span></div>',
                        unsafe_allow_html=True,
                    )
                elif is_passed:
                    st.markdown(
                        '<div style="text-align: right;"><span style="background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; font-size: 0.68rem; font-weight: 700; padding: 2px 8px; border-radius: 9999px;">✓ DONE</span></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<div style="text-align: right;"><span style="color: #94a3b8; font-size: 0.68rem; font-weight: 600;">PENDING</span></div>',
                        unsafe_allow_html=True,
                    )

            # Monospace command
            st.markdown(
                f'<div style="font-size: 0.86rem; font-weight: 600; color: {"#1d4ed8" if is_active else "#0f172a"}; font-family: \'Fira Code\', monospace; margin: 6px 0 4px 0; word-break: break-all;">'
                f'{html.escape(cmd)}'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Description
            if summary:
                st.markdown(
                    f'<div style="font-size: 0.78rem; color: #64748b; line-height: 1.45;">'
                    f'{html.escape(summary)}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

