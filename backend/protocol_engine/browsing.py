"""Browsing protocol simulation and real-execution engine (DNS + HTTP/1.1)."""

import socket
import hashlib
import urllib.parse
from typing import Dict, List, Optional
import requests

from backend.models import (
    BrowseRequest,
    ProtocolStep,
    ProtocolTraceResponse,
)
from backend.protocol_engine.utils import _get_simulated_ip, _get_http_date


def generate_browsing_trace(req: BrowseRequest) -> ProtocolTraceResponse:
    """
    Generate complete Browsing protocol trace with real HTTP/DNS resolution:
    1. DNS Query (UDP 53)
    2. DNS Response (A record IP resolution)
    3. HTTP Request (GET / Host / User-Agent)
    4. HTTP Response (Status + headers + HTML payload)
    """
    raw_url = req.url.strip()
    if not raw_url.startswith(("http://", "https://")):
        raw_url = "https://" + raw_url

    parsed = urllib.parse.urlparse(raw_url)
    domain = parsed.hostname or parsed.netloc or "example.com"
    path = parsed.path if parsed.path else "/"
    if parsed.query:
        path += f"?{parsed.query}"

    # Try real DNS resolution first
    dns_failed = False
    dns_error_msg = ""
    resolved_ip = None

    try:
        resolved_ip = socket.gethostbyname(domain)
        dns_source = "Public DNS Resolver (System / 8.8.8.8:53)"
    except Exception as exc:
        dns_failed = True
        dns_error_msg = str(exc)
        dns_source = "Public DNS Resolver (System / 8.8.8.8:53)"

    tx_id = f"0x{int(hashlib.md5(domain.encode()).hexdigest()[:4], 16):04x}"
    client_endpoint = "Client (192.168.1.105:54192)"
    dns_endpoint = dns_source

    if dns_failed:
        t = 0.0
        # Step 1: TCP SYN for DNS
        step1 = ProtocolStep(
            step_number=1,
            timestamp_ms=t,
            protocol="TCP",
            layer="Transport (L4 TCP 3-Way Handshake)",
            direction="c2s",
            source_node=client_endpoint,
            dest_node=dns_endpoint,
            command=f"TCP [SYN] Seq=0 Win=65535 MSS=1460 (Port 53/DNS)",
            status_code=None,
            summary=f"Client initiates reliable L4 TCP handshake with DNS resolver at port 53 (RFC 7766 DNS-over-TCP)",
            details={
                "Transport": "TCP port 53",
                "Flags": "[SYN]",
                "Mode": "RFC 7766 DNS over TCP",
                "Source Port": 54192,
                "Dest Port": 53,
                "Win": 65535,
                "MSS": 1460,
            },
            raw_wire=f"TCP SYN: Sport=54192 Dport=53 Seq=0 Ack=0 Flags=[SYN] Win=65535 MSS=1460\r\n",
            duration_ms=10.0,
        )
        t += 10.0

        # Step 2: TCP SYN-ACK for DNS
        step2 = ProtocolStep(
            step_number=2,
            timestamp_ms=t,
            protocol="TCP",
            layer="Transport (L4 TCP 3-Way Handshake)",
            direction="s2c",
            source_node=dns_endpoint,
            dest_node=client_endpoint,
            command="TCP [SYN, ACK] Seq=0 Ack=1 Win=65535",
            status_code="SYN-ACK",
            summary="DNS resolver accepts and acknowledges TCP connection for reliable query transport",
            details={
                "Transport": "TCP port 53",
                "Flags": "[SYN, ACK]",
                "Status": "SYN_RECEIVED",
                "Source Port": 53,
                "Dest Port": 54192,
                "Seq": 0,
                "Ack": 1,
            },
            raw_wire="TCP SYN-ACK: Sport=53 Dport=54192 Seq=0 Ack=1 Flags=[SYN, ACK] Win=65535\r\n",
            duration_ms=9.5,
        )
        t += 9.5

        # Step 3: TCP ACK for DNS
        step3 = ProtocolStep(
            step_number=3,
            timestamp_ms=t,
            protocol="TCP",
            layer="Transport (L4 TCP Handshake Established)",
            direction="c2s",
            source_node=client_endpoint,
            dest_node=dns_endpoint,
            command="TCP [ACK] Seq=1 Ack=1 (Connection ESTABLISHED)",
            status_code="ESTABLISHED",
            summary="TCP 3-way handshake established with DNS resolver on port 53",
            details={
                "Transport": "TCP port 53",
                "Flags": "[ACK]",
                "Status": "ESTABLISHED",
                "Source Port": 54192,
                "Dest Port": 53,
            },
            raw_wire="TCP ACK: Sport=54192 Dport=53 Seq=1 Ack=1 Flags=[ACK]\r\n",
            duration_ms=6.0,
        )
        t += 6.0

        # Step 4: DNS Query (over TCP)
        raw_dns_query = (
            f";; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: {tx_id}\n"
            f";; flags: rd; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 0\n"
            f";; QUESTION SECTION:\n"
            f";{domain}.                    IN      A"
        )
        step4 = ProtocolStep(
            step_number=4,
            timestamp_ms=t,
            protocol="DNS",
            layer="Application (L7) over TCP (L4)",
            direction="c2s",
            source_node=client_endpoint,
            dest_node=dns_endpoint,
            command=f"Standard query {tx_id} A {domain} (over TCP)",
            status_code=None,
            summary=f"Client sends DNS query for IPv4 address of '{domain}' over established L4 TCP connection",
            details={
                "Transaction ID": tx_id,
                "Query Type": "A (IPv4)",
                "Class": "IN (Internet)",
                "Domain": domain,
                "Recursion Desired": True,
                "Transport": "TCP port 53 (RFC 7766)",
            },
            raw_wire=raw_dns_query,
            duration_ms=18.4,
        )
        t += 18.4

        # Step 5: DNS Response with Failure (NXDOMAIN)
        raw_dns_resp = (
            f";; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: {tx_id}\n"
            f";; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 0\n"
            f";; QUESTION SECTION:\n"
            f";{domain}.                    IN      A\n\n"
            f";; ERROR / DIAGNOSTIC SECTION:\n"
            f";; RCODE: 3 (NXDOMAIN / Non-Existent Domain)\n"
            f";; Error: {dns_error_msg}"
        )
        step5 = ProtocolStep(
            step_number=5,
            timestamp_ms=t,
            protocol="DNS",
            layer="Application (L7) over TCP (L4)",
            direction="s2c",
            source_node=dns_endpoint,
            dest_node=client_endpoint,
            command=f"Standard query response {tx_id} NXDOMAIN - Host not found: {domain}",
            status_code="NXDOMAIN",
            summary=f"DNS resolver failed to resolve '{domain}': {dns_error_msg}. Address does not exist or lookup failed.",
            details={
                "Transaction ID": tx_id,
                "Status": "NXDOMAIN (RCODE: 3 - Name Error)",
                "Error": dns_error_msg,
                "Domain": domain,
                "Resolution Result": "FAILED (Address does not exist or lookup failed)",
                "Resolved IP": None,
                "Transport": "TCP port 53",
            },
            raw_wire=raw_dns_resp,
            duration_ms=16.5,
        )
        t += 16.5

        # Step 6: TCP FIN-ACK for DNS
        step6 = ProtocolStep(
            step_number=6,
            timestamp_ms=t,
            protocol="TCP",
            layer="Transport (L4 TCP Connection Teardown)",
            direction="c2s",
            source_node=client_endpoint,
            dest_node=dns_endpoint,
            command="TCP [FIN, ACK] DNS Query Complete, Closing Socket",
            status_code="FIN-ACK",
            summary="Client gracefully closes TCP connection to DNS resolver",
            details={"Transport": "TCP port 53", "Flags": "[FIN, ACK]", "Status": "FIN_WAIT_1"},
            raw_wire="TCP FIN-ACK: Sport=54192 Dport=53 Flags=[FIN, ACK]\r\n",
            duration_ms=6.0,
        )
        t += 6.0

        # Step 7: TCP ACK for DNS
        step7 = ProtocolStep(
            step_number=7,
            timestamp_ms=t,
            protocol="TCP",
            layer="Transport (L4 TCP Connection Teardown)",
            direction="s2c",
            source_node=dns_endpoint,
            dest_node=client_endpoint,
            command="TCP [ACK] DNS Socket Closed",
            status_code="CLOSED",
            summary="DNS resolver acknowledges socket teardown and closes transmission channel",
            details={"Transport": "TCP port 53", "Flags": "[ACK]", "Status": "CLOSED"},
            raw_wire="TCP ACK: Sport=53 Dport=54192 Flags=[ACK]\r\n",
            duration_ms=5.5,
        )

        error_html = (
            f"<!DOCTYPE html>\n"
            f"<html>\n"
            f"<head>\n"
            f"  <title>Site cannot be reached - {domain}</title>\n"
            f"  <meta charset=\"UTF-8\" />\n"
            f"  <style>\n"
            f"    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 36px 20px; color: #f1f5f9; background: #0b1120; display: flex; justify-content: center; align-items: center; min-height: 80vh; margin: 0; }}\n"
            f"    .card {{ background: #1e293b; border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 12px; max-width: 540px; width: 100%; padding: 28px; box-shadow: 0 12px 30px rgba(0,0,0,0.5); }}\n"
            f"    .badge {{ display: inline-block; background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; margin-bottom: 12px; }}\n"
            f"    h1 {{ color: #f87171; font-size: 1.35rem; margin: 0 0 10px 0; display: flex; align-items: center; gap: 8px; }}\n"
            f"    p {{ color: #94a3b8; font-size: 0.9rem; line-height: 1.5; margin: 8px 0; }}\n"
            f"    .error-box {{ background: rgba(15, 23, 42, 0.8); border-left: 4px solid #ef4444; border-radius: 4px; padding: 10px 14px; margin: 16px 0; font-family: monospace; font-size: 0.82rem; color: #fca5a5; word-break: break-all; }}\n"
            f"    .steps {{ margin-top: 18px; padding-top: 14px; border-top: 1px solid rgba(255, 255, 255, 0.08); font-size: 0.82rem; color: #64748b; }}\n"
            f"    ul {{ padding-left: 20px; margin: 6px 0; }}\n"
            f"  </style>\n"
            f"</head>\n"
            f"<body>\n"
            f"  <div class=\"card\">\n"
            f"    <span class=\"badge\">DNS Resolution Failed</span>\n"
            f"    <h1>⚠️ This site can’t be reached</h1>\n"
            f"    <p>The server IP address for <strong>{domain}</strong> could not be found because DNS resolution failed.</p>\n"
            f"    <div class=\"error-box\">\n"
            f"      <strong>DNS Error:</strong> {dns_error_msg}<br/>\n"
            f"      <strong>Status:</strong> NXDOMAIN / ERR_NAME_NOT_RESOLVED\n"
            f"    </div>\n"
            f"    <div class=\"steps\">\n"
            f"      Possible causes:\n"
            f"      <ul>\n"
            f"        <li>The domain name does not exist or has expired</li>\n"
            f"        <li>Typo in the web address: <code>{domain}</code></li>\n"
            f"        <li>Authoritative nameservers are unreachable or down</li>\n"
            f"      </ul>\n"
            f"    </div>\n"
            f"  </div>\n"
            f"</body>\n"
            f"</html>"
        )

        return ProtocolTraceResponse(
            mode="browsing",
            title=f"Web Browsing Trace: {domain} (DNS Resolution Failed)",
            summary=f"DNS lookup over L4 TCP failed for '{domain}': {dns_error_msg}. The address does not exist or DNS resolver failed. HTTP request aborted.",
            total_steps=7,
            steps=[step1, step2, step3, step4, step5, step6, step7],
            html_content=error_html,
            metadata={
                "domain": domain,
                "resolved_ip": None,
                "url": raw_url,
                "status_code": "DNS_PROBE_FINISHED_NXDOMAIN",
                "is_live_fetch": req.fetch_real,
                "failed": True,
                "transport": "TCP",
                "error": dns_error_msg,
                "error_type": "DNS_NXDOMAIN",
            },
        )

    server_endpoint = f"Web Server ({resolved_ip}:80)"

    # Attempt real HTTP fetch if requested
    real_html: Optional[str] = None
    real_status_code = 200
    real_status_text = "OK"
    real_headers: Dict[str, str] = {}
    is_live_fetch = False

    if req.fetch_real:
        try:
            fetch_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            resp = requests.get(raw_url, headers=fetch_headers, timeout=3.5, allow_redirects=True)
            real_html = resp.text
            real_status_code = resp.status_code
            real_status_text = resp.reason or "OK"
            real_headers = dict(resp.headers)
            is_live_fetch = True
        except Exception:
            pass

    # Default preview if live fetch failed or wasn't used
    if not real_html:
        real_html = (
            f"<!DOCTYPE html>\n"
            f"<html>\n"
            f"<head>\n"
            f"  <title>Welcome to {domain}</title>\n"
            f"  <meta charset=\"UTF-8\" />\n"
            f"  <style>\n"
            f"    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 24px; color: #1e293b; background: #f8fafc; }}\n"
            f"    h1 {{ color: #0284c7; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }}\n"
            f"    .badge {{ display: inline-block; background: #e0f2fe; color: #0369a1; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 0.85rem; }}\n"
            f"  </style>\n"
            f"</head>\n"
            f"<body>\n"
            f"  <h1>{domain}</h1>\n"
            f"  <p><span class=\"badge\">HTTP/1.1 200 OK</span></p>\n"
            f"  <p>Resource path <code>{path}</code> rendered successfully.</p>\n"
            f"  <p>This page was loaded through the interactive protocol visualizer.</p>\n"
            f"</body>\n"
            f"</html>"
        )

    content_length = len(real_html.encode("utf-8"))
    server_banner = real_headers.get("Server", "nginx/1.24.0 (Live Edge)")
    content_type = real_headers.get("Content-Type", "text/html; charset=UTF-8")

    steps: List[ProtocolStep] = []
    t = 0.0

    # Step 1: TCP SYN for DNS Resolver
    steps.append(
        ProtocolStep(
            step_number=1,
            timestamp_ms=round(t, 1),
            protocol="TCP",
            layer="Transport (L4 TCP 3-Way Handshake)",
            direction="c2s",
            source_node=client_endpoint,
            dest_node=dns_endpoint,
            command="TCP [SYN] Seq=0 Win=65535 MSS=1460 (Port 53/DNS)",
            status_code=None,
            summary=f"Client initiates reliable L4 TCP handshake with DNS resolver ({resolved_ip or '8.8.8.8'}:53) via DNS-over-TCP (RFC 7766)",
            details={
                "Transport": "TCP port 53",
                "Flags": "[SYN]",
                "Mode": "RFC 7766 DNS over TCP",
                "Source Port": 54192,
                "Dest Port": 53,
                "Win": 65535,
                "MSS": 1460,
            },
            raw_wire="TCP SYN: Sport=54192 Dport=53 Seq=0 Ack=0 Flags=[SYN] Win=65535 MSS=1460\r\n",
            duration_ms=10.0,
        )
    )
    t += 10.0

    # Step 2: TCP SYN-ACK for DNS Resolver
    steps.append(
        ProtocolStep(
            step_number=2,
            timestamp_ms=round(t, 1),
            protocol="TCP",
            layer="Transport (L4 TCP 3-Way Handshake)",
            direction="s2c",
            source_node=dns_endpoint,
            dest_node=client_endpoint,
            command="TCP [SYN, ACK] Seq=0 Ack=1 Win=65535",
            status_code="SYN-ACK",
            summary="DNS resolver accepts and acknowledges TCP connection for reliable query transport",
            details={
                "Transport": "TCP port 53",
                "Flags": "[SYN, ACK]",
                "Status": "SYN_RECEIVED",
                "Source Port": 53,
                "Dest Port": 54192,
                "Seq": 0,
                "Ack": 1,
            },
            raw_wire="TCP SYN-ACK: Sport=53 Dport=54192 Seq=0 Ack=1 Flags=[SYN, ACK] Win=65535\r\n",
            duration_ms=9.5,
        )
    )
    t += 9.5

    # Step 3: TCP ACK for DNS Resolver
    steps.append(
        ProtocolStep(
            step_number=3,
            timestamp_ms=round(t, 1),
            protocol="TCP",
            layer="Transport (L4 TCP Handshake Established)",
            direction="c2s",
            source_node=client_endpoint,
            dest_node=dns_endpoint,
            command="TCP [ACK] Seq=1 Ack=1 (Connection ESTABLISHED)",
            status_code="ESTABLISHED",
            summary="TCP 3-way handshake established with DNS resolver on port 53",
            details={
                "Transport": "TCP port 53",
                "Flags": "[ACK]",
                "Status": "ESTABLISHED",
                "Source Port": 54192,
                "Dest Port": 53,
            },
            raw_wire="TCP ACK: Sport=54192 Dport=53 Seq=1 Ack=1 Flags=[ACK]\r\n",
            duration_ms=6.0,
        )
    )
    t += 6.0

    # Step 4: DNS Query (over TCP)
    raw_dns_query = (
        f";; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: {tx_id}\n"
        f";; flags: rd; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 0\n"
        f";; QUESTION SECTION:\n"
        f";{domain}.                    IN      A"
    )
    steps.append(
        ProtocolStep(
            step_number=4,
            timestamp_ms=round(t, 1),
            protocol="DNS",
            layer="Application (L7) over TCP (L4)",
            direction="c2s",
            source_node=client_endpoint,
            dest_node=dns_endpoint,
            command=f"Standard query {tx_id} A {domain} (over TCP)",
            status_code=None,
            summary=f"Client sends DNS query for IPv4 address of '{domain}' over established L4 TCP connection",
            details={
                "Transaction ID": tx_id,
                "Query Type": "A (IPv4)",
                "Class": "IN (Internet)",
                "Domain": domain,
                "Recursion Desired": True,
                "Transport": "TCP port 53 (RFC 7766)",
            },
            raw_wire=raw_dns_query,
            duration_ms=18.4,
        )
    )
    t += 18.4

    # Step 5: DNS Response (over TCP)
    raw_dns_resp = (
        f";; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: {tx_id}\n"
        f";; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0\n"
        f";; QUESTION SECTION:\n"
        f";{domain}.                    IN      A\n\n"
        f";; ANSWER SECTION:\n"
        f"{domain}.             300     IN      A       {resolved_ip}"
    )
    steps.append(
        ProtocolStep(
            step_number=5,
            timestamp_ms=round(t, 1),
            protocol="DNS",
            layer="Application (L7) over TCP (L4)",
            direction="s2c",
            source_node=dns_endpoint,
            dest_node=client_endpoint,
            command=f"Standard query response {tx_id} A {domain} -> {resolved_ip}",
            status_code="NOERROR",
            summary=f"DNS resolver returns A record resolving '{domain}' to {resolved_ip} (TTL: 300s)",
            details={
                "Transaction ID": tx_id,
                "Status": "NOERROR (0)",
                "Resolved IP": resolved_ip,
                "TTL": "300 seconds",
                "Resolution Mode": "Live Socket" if is_live_fetch else "Simulated",
                "Transport": "TCP port 53",
            },
            raw_wire=raw_dns_resp,
            duration_ms=12.2,
        )
    )
    t += 12.2

    # Step 6: TCP FIN-ACK for DNS Resolver
    steps.append(
        ProtocolStep(
            step_number=6,
            timestamp_ms=round(t, 1),
            protocol="TCP",
            layer="Transport (L4 TCP Connection Teardown)",
            direction="c2s",
            source_node=client_endpoint,
            dest_node=dns_endpoint,
            command="TCP [FIN, ACK] DNS Query Complete, Closing Socket",
            status_code="FIN-ACK",
            summary="Client gracefully closes TCP connection to DNS resolver",
            details={"Transport": "TCP port 53", "Flags": "[FIN, ACK]", "Status": "FIN_WAIT_1"},
            raw_wire="TCP FIN-ACK: Sport=54192 Dport=53 Flags=[FIN, ACK]\r\n",
            duration_ms=6.0,
        )
    )
    t += 6.0

    # Step 7: TCP ACK for DNS Resolver
    steps.append(
        ProtocolStep(
            step_number=7,
            timestamp_ms=round(t, 1),
            protocol="TCP",
            layer="Transport (L4 TCP Connection Teardown)",
            direction="s2c",
            source_node=dns_endpoint,
            dest_node=client_endpoint,
            command="TCP [ACK] DNS Socket Closed",
            status_code="CLOSED",
            summary="DNS resolver acknowledges socket teardown and closes transmission channel",
            details={"Transport": "TCP port 53", "Flags": "[ACK]", "Status": "CLOSED"},
            raw_wire="TCP ACK: Sport=53 Dport=54192 Flags=[ACK]\r\n",
            duration_ms=5.5,
        )
    )
    t += 5.5

    # Step 8: TCP SYN for Web Server
    steps.append(
        ProtocolStep(
            step_number=8,
            timestamp_ms=round(t, 1),
            protocol="TCP",
            layer="Transport (L4 TCP 3-Way Handshake)",
            direction="c2s",
            source_node=client_endpoint,
            dest_node=server_endpoint,
            command=f"TCP [SYN] Seq=0 Win=65535 MSS=1460 (Port 80/HTTP)",
            status_code=None,
            summary=f"Client initiates reliable L4 TCP handshake with Web Server ({resolved_ip}:80)",
            details={
                "Transport": "TCP port 80",
                "Flags": "[SYN]",
                "Source Port": 54192,
                "Dest Port": 80,
                "Win": 65535,
                "MSS": 1460,
            },
            raw_wire=f"TCP SYN: Sport=54192 Dport=80 Seq=0 Ack=0 Flags=[SYN] Win=65535 MSS=1460\r\n",
            duration_ms=10.0,
        )
    )
    t += 10.0

    # Step 9: TCP SYN-ACK for Web Server
    steps.append(
        ProtocolStep(
            step_number=9,
            timestamp_ms=round(t, 1),
            protocol="TCP",
            layer="Transport (L4 TCP 3-Way Handshake)",
            direction="s2c",
            source_node=server_endpoint,
            dest_node=client_endpoint,
            command="TCP [SYN, ACK] Seq=0 Ack=1 Win=65535",
            status_code="SYN-ACK",
            summary=f"Web server accepts and acknowledges TCP connection on port 80",
            details={
                "Transport": "TCP port 80",
                "Flags": "[SYN, ACK]",
                "Status": "SYN_RECEIVED",
                "Source Port": 80,
                "Dest Port": 54192,
                "Seq": 0,
                "Ack": 1,
            },
            raw_wire="TCP SYN-ACK: Sport=80 Dport=54192 Seq=0 Ack=1 Flags=[SYN, ACK] Win=65535\r\n",
            duration_ms=9.5,
        )
    )
    t += 9.5

    # Step 10: TCP ACK for Web Server
    steps.append(
        ProtocolStep(
            step_number=10,
            timestamp_ms=round(t, 1),
            protocol="TCP",
            layer="Transport (L4 TCP Handshake Established)",
            direction="c2s",
            source_node=client_endpoint,
            dest_node=server_endpoint,
            command="TCP [ACK] Seq=1 Ack=1 (Connection ESTABLISHED)",
            status_code="ESTABLISHED",
            summary=f"TCP 3-way handshake established with Web Server at {resolved_ip}:80",
            details={
                "Transport": "TCP port 80",
                "Flags": "[ACK]",
                "Status": "ESTABLISHED",
                "Source Port": 54192,
                "Dest Port": 80,
            },
            raw_wire="TCP ACK: Sport=54192 Dport=80 Seq=1 Ack=1 Flags=[ACK]\r\n",
            duration_ms=6.0,
        )
    )
    t += 6.0

    # Step 11: HTTP Request
    raw_http_req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {domain}\r\n"
        f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0\r\n"
        f"Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n"
        f"Accept-Language: en-US,en;q=0.9\r\n"
        f"Connection: keep-alive\r\n"
        f"\r\n"
    )
    steps.append(
        ProtocolStep(
            step_number=11,
            timestamp_ms=round(t, 1),
            protocol="HTTP/1.1",
            layer="Application (L7) over TCP (L4)",
            direction="c2s",
            source_node=client_endpoint,
            dest_node=server_endpoint,
            command=f"GET {path} HTTP/1.1",
            status_code=None,
            summary=f"Client sends HTTP/1.1 GET request to {domain} ({resolved_ip}:80)",
            details={
                "Method": "GET",
                "Path": path,
                "Host": domain,
                "Connection": "keep-alive",
                "Transport": "TCP port 80",
            },
            raw_wire=raw_http_req,
            duration_ms=24.6,
        )
    )
    t += 24.6

    # Step 12: HTTP Response
    http_date = real_headers.get("Date", _get_http_date())
    header_lines = [f"{k}: {v}" for k, v in list(real_headers.items())[:6]]
    headers_str = "\r\n".join(header_lines) if header_lines else f"Server: {server_banner}\r\nContent-Type: {content_type}\r\nContent-Length: {content_length}"

    raw_http_resp = (
        f"HTTP/1.1 {real_status_code} {real_status_text}\r\n"
        f"Date: {http_date}\r\n"
        f"{headers_str}\r\n"
        f"\r\n"
        f"{real_html[:500]}...\n[Truncated {content_length} total bytes]"
    )

    steps.append(
        ProtocolStep(
            step_number=12,
            timestamp_ms=round(t, 1),
            protocol="HTTP/1.1",
            layer="Application (L7) over TCP (L4)",
            direction="s2c",
            source_node=server_endpoint,
            dest_node=client_endpoint,
            command=f"HTTP/1.1 {real_status_code} {real_status_text}",
            status_code=f"{real_status_code} {real_status_text}",
            summary=f"Web server replies with HTTP {real_status_code} {real_status_text} and HTML payload ({content_length} bytes)",
            details={
                "Status Code": real_status_code,
                "Status Text": real_status_text,
                "Server": server_banner,
                "Content-Type": content_type,
                "Payload Size": f"{content_length} bytes",
                "Fetch Mode": "Live Network Request" if is_live_fetch else "Simulated Template",
                "Transport": "TCP port 80",
            },
            raw_wire=raw_http_resp,
            duration_ms=22.1,
        )
    )
    t += 22.1

    # Step 13: TCP FIN-ACK for Web Server
    steps.append(
        ProtocolStep(
            step_number=13,
            timestamp_ms=round(t, 1),
            protocol="TCP",
            layer="Transport (L4 TCP Connection Teardown)",
            direction="c2s",
            source_node=client_endpoint,
            dest_node=server_endpoint,
            command="TCP [FIN, ACK] HTTP Exchange Complete, Closing Socket",
            status_code="FIN-ACK",
            summary="Client initiates TCP channel teardown after completing HTTP request",
            details={"Transport": "TCP port 80", "Flags": "[FIN, ACK]", "Status": "FIN_WAIT_1"},
            raw_wire="TCP FIN-ACK: Sport=54192 Dport=80 Flags=[FIN, ACK]\r\n",
            duration_ms=6.0,
        )
    )
    t += 6.0

    # Step 14: TCP ACK for Web Server
    steps.append(
        ProtocolStep(
            step_number=14,
            timestamp_ms=round(t, 1),
            protocol="TCP",
            layer="Transport (L4 TCP Connection Teardown)",
            direction="s2c",
            source_node=server_endpoint,
            dest_node=client_endpoint,
            command="TCP [ACK] Web Socket Closed",
            status_code="CLOSED",
            summary="Web server acknowledges socket closure and terminates TCP channel",
            details={"Transport": "TCP port 80", "Flags": "[ACK]", "Status": "CLOSED"},
            raw_wire="TCP ACK: Sport=80 Dport=54192 Flags=[ACK]\r\n",
            duration_ms=5.5,
        )
    )

    return ProtocolTraceResponse(
        mode="browsing",
        title=f"Web Browsing Trace: {domain}",
        summary=f"DNS lookup resolved {domain} to {resolved_ip} over L4 TCP (RFC 7766) followed by HTTP GET request over L4 TCP returning {real_status_code} {real_status_text}.",
        total_steps=len(steps),
        steps=steps,
        html_content=real_html,
        metadata={
            "domain": domain,
            "resolved_ip": resolved_ip,
            "url": raw_url,
            "status_code": real_status_code,
            "is_live_fetch": is_live_fetch,
            "transport": "TCP",
            "failed": False,
        },
    )
