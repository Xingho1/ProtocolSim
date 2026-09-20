"""Mail protocol simulation (RFC 5321 ESMTP) and real SMTP execution engine."""

import time
import socket
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional

from backend.models import (
    MailRequest,
    ProtocolStep,
    ProtocolTraceResponse,
)
from backend.protocol_engine.utils import _get_http_date


def _make_step(
    step_number: int,
    timestamp_ms: float,
    direction: str,
    src: str,
    dst: str,
    command: str,
    summary: str,
    raw_wire: str,
    status_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    duration_ms: float = 12.0,
) -> ProtocolStep:
    """Helper to construct a ProtocolStep."""
    return ProtocolStep(
        step_number=step_number,
        timestamp_ms=round(timestamp_ms, 1),
        protocol="SMTP",
        layer="Application (L7)",
        direction=direction,
        source_node=src,
        dest_node=dst,
        command=command,
        status_code=status_code,
        summary=summary,
        details=details or {},
        raw_wire=raw_wire,
        duration_ms=duration_ms,
    )


def _send_real_smtp(req: MailRequest) -> ProtocolTraceResponse:
    """Execute live SMTP delivery and trace each protocol command.
    
    Raises RuntimeError or ValueError if the email cannot be sent.
    """
    host = (req.smtp_host or "").strip()
    port = req.smtp_port or 587
    user = (req.smtp_user or "").strip()
    password = (req.smtp_password or "").strip()
    recipient = (req.to or "").strip()
    sender = (req.sender or "").strip() or user
    subject = (req.subject or "").strip() or "Notification"
    body = (req.body or "").strip() or "Email body"

    # Validate required parameters for real SMTP delivery
    if not host:
        raise ValueError("SMTP host is required for real mail delivery.")
    if not user or not password:
        raise ValueError("SMTP username and password are required for real mail delivery.")
    if not recipient:
        raise ValueError("Recipient address ('to') is required for real mail delivery.")

    # Prepare MIME payload
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg["Date"] = _get_http_date()
    msg.attach(MIMEText(body, "plain"))
    raw_email_str = msg.as_string()

    client_node = f"Client MUA ({socket.gethostname()})"
    server_node = f"SMTP Relay ({host}:{port})"
    steps: List[ProtocolStep] = []
    t = 0.0

    try:
        # 1. Connect
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)

        steps.append(_make_step(
            step_number=len(steps) + 1,
            timestamp_ms=t,
            direction="s2c",
            src=server_node,
            dst=client_node,
            command=f"220 {host} ESMTP Service Ready",
            status_code="220",
            summary=f"Connected to live SMTP server at {host}:{port}",
            details={"Command": "CONNECT", "Host": host, "Port": port},
            raw_wire=f"220 {host} ESMTP Service Ready\r\n",
            duration_ms=18.0,
        ))
        t += 18.0

        # 2. EHLO
        client_fqdn = socket.gethostname()
        steps.append(_make_step(
            step_number=len(steps) + 1,
            timestamp_ms=t,
            direction="c2s",
            src=client_node,
            dst=server_node,
            command=f"EHLO {client_fqdn}",
            summary="Client announces identity via EHLO command",
            details={"Command": "EHLO", "Client FQDN": client_fqdn},
            raw_wire=f"EHLO {client_fqdn}\r\n",
            duration_ms=12.0,
        ))
        t += 12.0

        ehlo_code, ehlo_resp = server.ehlo()
        ehlo_text = ehlo_resp.decode("utf-8", errors="ignore") if isinstance(ehlo_resp, bytes) else str(ehlo_resp)
        steps.append(_make_step(
            step_number=len(steps) + 1,
            timestamp_ms=t,
            direction="s2c",
            src=server_node,
            dst=client_node,
            command=f"{ehlo_code} Extended Capabilities Advertised",
            status_code=str(ehlo_code),
            summary="Server advertises supported ESMTP extensions",
            details={"Command": "EHLO Response", "Capabilities": ehlo_text[:120]},
            raw_wire=f"{ehlo_code} {ehlo_text}\r\n",
            duration_ms=15.0,
        ))
        t += 15.0

        # 3. STARTTLS if enabled
        if req.use_tls and port != 465:
            steps.append(_make_step(
                step_number=len(steps) + 1,
                timestamp_ms=t,
                direction="c2s",
                src=client_node,
                dst=server_node,
                command="STARTTLS",
                summary="Client initiates TLS encryption upgrade",
                details={"Command": "STARTTLS"},
                raw_wire="STARTTLS\r\n",
                duration_ms=10.0,
            ))
            t += 10.0

            tls_code, tls_resp = server.starttls()
            tls_text = tls_resp.decode("utf-8", errors="ignore") if isinstance(tls_resp, bytes) else str(tls_resp)
            steps.append(_make_step(
                step_number=len(steps) + 1,
                timestamp_ms=t,
                direction="s2c",
                src=server_node,
                dst=client_node,
                command=f"{tls_code} Ready to start TLS",
                status_code=str(tls_code),
                summary="Session upgraded to secure TLS socket",
                details={"Command": "STARTTLS Response", "Status": "Encrypted"},
                raw_wire=f"{tls_code} {tls_text}\r\n",
                duration_ms=25.0,
            ))
            t += 25.0
            server.ehlo()

        # 4. AUTH LOGIN
        steps.append(_make_step(
            step_number=len(steps) + 1,
            timestamp_ms=t,
            direction="c2s",
            src=client_node,
            dst=server_node,
            command=f"AUTH LOGIN (user: {user})",
            summary=f"Client authenticates with credentials for user {user}",
            details={"Command": "AUTH", "User": user},
            raw_wire=f"AUTH LOGIN (user: {user})\r\n",
            duration_ms=15.0,
        ))
        t += 15.0

        auth_code, auth_resp = server.login(user, password)
        auth_text = auth_resp.decode("utf-8", errors="ignore") if isinstance(auth_resp, bytes) else str(auth_resp)
        steps.append(_make_step(
            step_number=len(steps) + 1,
            timestamp_ms=t,
            direction="s2c",
            src=server_node,
            dst=client_node,
            command=f"{auth_code} Authentication Succeeded",
            status_code=str(auth_code),
            summary=f"User {user} successfully authenticated",
            details={"Command": "AUTH Response", "User": user, "Result": "Accepted"},
            raw_wire=f"{auth_code} {auth_text}\r\n",
            duration_ms=20.0,
        ))
        t += 20.0

        # 5. MAIL FROM
        steps.append(_make_step(
            step_number=len(steps) + 1,
            timestamp_ms=t,
            direction="c2s",
            src=client_node,
            dst=server_node,
            command=f"MAIL FROM:<{sender}>",
            summary=f"Client specifies envelope sender <{sender}>",
            details={"Command": "MAIL FROM", "Sender": sender},
            raw_wire=f"MAIL FROM:<{sender}>\r\n",
            duration_ms=12.0,
        ))
        t += 12.0

        mail_code, mail_resp = server.mail(sender)
        mail_text = mail_resp.decode("utf-8", errors="ignore") if isinstance(mail_resp, bytes) else str(mail_resp)
        if mail_code not in (250, 200):
            raise smtplib.SMTPResponseException(mail_code, mail_resp)
        steps.append(_make_step(
            step_number=len(steps) + 1,
            timestamp_ms=t,
            direction="s2c",
            src=server_node,
            dst=client_node,
            command=f"{mail_code} Sender OK",
            status_code=str(mail_code),
            summary=f"Server accepted sender <{sender}>",
            details={"Command": "MAIL FROM Response", "Sender": sender},
            raw_wire=f"{mail_code} {mail_text}\r\n",
            duration_ms=10.0,
        ))
        t += 10.0

        # 6. RCPT TO
        steps.append(_make_step(
            step_number=len(steps) + 1,
            timestamp_ms=t,
            direction="c2s",
            src=client_node,
            dst=server_node,
            command=f"RCPT TO:<{recipient}>",
            summary=f"Client specifies recipient <{recipient}>",
            details={"Command": "RCPT TO", "Recipient": recipient},
            raw_wire=f"RCPT TO:<{recipient}>\r\n",
            duration_ms=12.0,
        ))
        t += 12.0

        rcpt_code, rcpt_resp = server.rcpt(recipient)
        rcpt_text = rcpt_resp.decode("utf-8", errors="ignore") if isinstance(rcpt_resp, bytes) else str(rcpt_resp)
        if rcpt_code not in (250, 251):
            raise smtplib.SMTPResponseException(rcpt_code, rcpt_resp)
        steps.append(_make_step(
            step_number=len(steps) + 1,
            timestamp_ms=t,
            direction="s2c",
            src=server_node,
            dst=client_node,
            command=f"{rcpt_code} Recipient OK",
            status_code=str(rcpt_code),
            summary=f"Server accepted recipient <{recipient}>",
            details={"Command": "RCPT TO Response", "Recipient": recipient},
            raw_wire=f"{rcpt_code} {rcpt_text}\r\n",
            duration_ms=10.0,
        ))
        t += 10.0

        # 7. DATA
        steps.append(_make_step(
            step_number=len(steps) + 1,
            timestamp_ms=t,
            direction="c2s",
            src=client_node,
            dst=server_node,
            command="DATA",
            summary="Client requests to send email message body",
            details={"Command": "DATA"},
            raw_wire="DATA\r\n",
            duration_ms=10.0,
        ))
        t += 10.0

        data_code, data_resp = server.data(raw_email_str)
        data_text = data_resp.decode("utf-8", errors="ignore") if isinstance(data_resp, bytes) else str(data_resp)
        if data_code not in (250, 200):
            raise smtplib.SMTPResponseException(data_code, data_resp)
        steps.append(_make_step(
            step_number=len(steps) + 1,
            timestamp_ms=t,
            direction="s2c",
            src=server_node,
            dst=client_node,
            command=f"{data_code} Message Delivered to <{recipient}>",
            status_code=str(data_code),
            summary=f"Email message accepted and queued for delivery to {recipient}",
            details={"Command": "DATA Response", "Delivered": True, "Recipient": recipient},
            raw_wire=f"{data_code} {data_text}\r\n",
            duration_ms=25.0,
        ))
        t += 25.0

        # 8. QUIT
        steps.append(_make_step(
            step_number=len(steps) + 1,
            timestamp_ms=t,
            direction="c2s",
            src=client_node,
            dst=server_node,
            command="QUIT",
            summary="Client requests to close the SMTP session",
            details={"Command": "QUIT"},
            raw_wire="QUIT\r\n",
            duration_ms=8.0,
        ))
        t += 8.0

        try:
            quit_code, quit_resp = server.quit()
            quit_text = quit_resp.decode("utf-8", errors="ignore") if isinstance(quit_resp, bytes) else str(quit_resp)
        except Exception:
            quit_code, quit_text = 221, "Bye"

        steps.append(_make_step(
            step_number=len(steps) + 1,
            timestamp_ms=t,
            direction="s2c",
            src=server_node,
            dst=client_node,
            command=f"{quit_code} Bye",
            status_code=str(quit_code),
            summary="SMTP server closed the transmission channel",
            details={"Command": "QUIT Response"},
            raw_wire=f"{quit_code} {quit_text}\r\n",
            duration_ms=8.0,
        ))

        return ProtocolTraceResponse(
            mode="mail",
            title=f"Live SMTP Delivery: {recipient}",
            summary=f"Real email delivered to {recipient} via {host}:{port}. Commands executed: EHLO, STARTTLS, AUTH, MAIL FROM, RCPT TO, DATA, QUIT.",
            total_steps=len(steps),
            steps=steps,
            metadata={
                "real_send": True,
                "host": host,
                "recipient": recipient,
                "success": True,
                "commands_used": ["EHLO", "STARTTLS", "AUTH", "MAIL FROM", "RCPT TO", "DATA", "QUIT"],
            },
        )
    except Exception as e:
        # If toggled on and the mail is not sent, raise an error!
        raise RuntimeError(f"Real mail could not be sent to {recipient}: {e}") from e


def _simulate_mail(req: MailRequest) -> ProtocolTraceResponse:
    """Generate simulated RFC 5321 SMTP conversation displaying all used commands."""
    sender = req.sender.strip() if req.sender.strip() else "user@antigravity.net"
    recipient = req.to.strip() if req.to.strip() else "recipient@domain.com"
    subject = req.subject.strip() if req.subject.strip() else "Project Notification"
    body = req.body.strip() if req.body.strip() else "Hello,\nThis is a test notification."

    client_node = "Client MUA (192.168.1.105:49812)"
    server_node = "Mail MTA (mail.isp-relay.net:25)"
    now_str = _get_http_date()
    msg_id = f"{int(time.time())}.{hashlib.md5(subject.encode()).hexdigest()[:8]}@antigravity.net"
    queue_id = f"4X9k{hashlib.md5(recipient.encode()).hexdigest()[:7].upper()}"

    raw_rfc5322_email = (
        f"From: <{sender}>\r\n"
        f"To: <{recipient}>\r\n"
        f"Date: {now_str}\r\n"
        f"Subject: {subject}\r\n"
        f"Message-ID: <{msg_id}>\r\n"
        f"MIME-Version: 1.0\r\n"
        f"Content-Type: text/plain; charset=UTF-8\r\n\r\n"
        f"{body}\r\n"
        f".\r\n"
    )

    # All 13 RFC 5321 steps clearly showing the commands used
    steps_data = [
        # (direction, command, status_code, summary, details, raw_wire, dur)
        (
            "s2c",
            "220 mail.isp-relay.net ESMTP Postfix Service Ready",
            "220",
            "SMTP Server announces readiness after TCP 3-way handshake",
            {"Command": "CONNECT", "Service": "ESMTP Postfix", "Host": "mail.isp-relay.net", "Port": 25},
            "220 mail.isp-relay.net ESMTP ready\r\n",
            14.2,
        ),
        (
            "c2s",
            "EHLO client.internal.lan",
            None,
            "Client introduces itself using Extended HELO (EHLO)",
            {"Command": "EHLO", "Client FQDN": "client.internal.lan"},
            "EHLO client.internal.lan\r\n",
            10.5,
        ),
        (
            "s2c",
            "250-mail.isp-relay.net [Capabilities: 8BITMIME, SIZE, STARTTLS, PIPELINING]",
            "250 OK",
            "Server advertises supported ESMTP extensions",
            {"Command": "EHLO Response", "Extensions": ["PIPELINING", "SIZE 35882577", "8BITMIME", "STARTTLS"]},
            "250-mail.isp-relay.net Hello\r\n250-SIZE 35882577\r\n250-STARTTLS\r\n250 OK\r\n",
            11.8,
        ),
        (
            "c2s",
            f"MAIL FROM:<{sender}>",
            None,
            f"Client initiates envelope transaction specifying sender '{sender}'",
            {"Command": "MAIL FROM", "Sender": sender},
            f"MAIL FROM:<{sender}>\r\n",
            12.0,
        ),
        (
            "s2c",
            "250 2.1.0 Ok",
            "250",
            f"Server verifies and accepts sender address <{sender}>",
            {"Command": "MAIL FROM Response", "Reply Code": "250", "Enhanced Status": "2.1.0 (Sender OK)"},
            f"250 2.1.0 Ok: Sender <{sender}> accepted\r\n",
            9.4,
        ),
        (
            "c2s",
            f"RCPT TO:<{recipient}>",
            None,
            f"Client specifies target recipient '{recipient}'",
            {"Command": "RCPT TO", "Recipient": recipient},
            f"RCPT TO:<{recipient}>\r\n",
            10.2,
        ),
        (
            "s2c",
            "250 2.1.5 Ok",
            "250",
            f"Server verifies recipient destination <{recipient}> is deliverable",
            {"Command": "RCPT TO Response", "Reply Code": "250", "Enhanced Status": "2.1.5 (Recipient OK)"},
            f"250 2.1.5 Ok: Recipient <{recipient}> verified\r\n",
            11.1,
        ),
        (
            "c2s",
            "DATA",
            None,
            "Client requests permission to transmit the mail message payload",
            {"Command": "DATA"},
            "DATA\r\n",
            8.6,
        ),
        (
            "s2c",
            "354 Start mail input; end with <CRLF>.<CRLF>",
            "354",
            "Server grants permission to stream RFC 5322 header and body content",
            {"Command": "DATA Response", "Reply Code": "354"},
            "354 End data with <CR><LF>.<CR><LF>\r\n",
            9.1,
        ),
        (
            "c2s",
            f"MIME Body Stream ({len(raw_rfc5322_email)} bytes) ending in <CRLF>.<CRLF>",
            None,
            "Client transmits email headers, Subject, MIME body, and terminates with '.'",
            {"Command": "PAYLOAD", "Subject": subject, "From": sender, "To": recipient, "Bytes": len(raw_rfc5322_email)},
            raw_rfc5322_email,
            25.4,
        ),
        (
            "s2c",
            f"250 2.0.0 Ok: queued as {queue_id}",
            "250",
            f"Server successfully commits message to mail spool with ID {queue_id}",
            {"Command": "DATA Complete", "Reply Code": "250", "Queue ID": queue_id},
            f"250 2.0.0 Ok: queued as {queue_id}\r\n",
            18.5,
        ),
        (
            "c2s",
            "QUIT",
            None,
            "Client gracefully closes the SMTP session",
            {"Command": "QUIT"},
            "QUIT\r\n",
            7.3,
        ),
        (
            "s2c",
            "221 2.0.0 Bye",
            "221",
            "Server acknowledges teardown and closes TCP transmission channel",
            {"Command": "QUIT Response", "Reply Code": "221"},
            "221 2.0.0 mail.isp-relay.net Service closing channel\r\n",
            8.0,
        ),
    ]

    current_time = 0.0
    steps: List[ProtocolStep] = []
    for step_num, (direction, cmd, st_code, summary, details, raw, dur) in enumerate(steps_data, start=1):
        src = client_node if direction == "c2s" else server_node
        dst = server_node if direction == "c2s" else client_node
        steps.append(
            _make_step(
                step_number=step_num,
                timestamp_ms=current_time,
                direction=direction,
                src=src,
                dst=dst,
                command=cmd,
                status_code=st_code,
                summary=summary,
                details=details,
                raw_wire=raw,
                duration_ms=dur,
            )
        )
        current_time += dur

    return ProtocolTraceResponse(
        mode="mail",
        title=f"SMTP Mail Conversation: {recipient}",
        summary=f"Simulated RFC 5321 SMTP dialogue demonstrating commands: EHLO, MAIL FROM, RCPT TO, DATA, and QUIT (Queue ID: {queue_id}).",
        total_steps=len(steps),
        steps=steps,
        metadata={
            "sender": sender,
            "recipient": recipient,
            "subject": subject,
            "queue_id": queue_id,
            "real_send": False,
            "commands_used": ["EHLO", "MAIL FROM", "RCPT TO", "DATA", "QUIT"],
        },
    )


def generate_mail_trace(req: MailRequest) -> ProtocolTraceResponse:
    """Generate mail protocol trace.

    If toggle `real_send` is on, executes real SMTP transmission and raises an error if sending fails.
    If toggle is off, simulates RFC 5321 SMTP mailing showing all protocol commands used.
    """
    if req.real_send:
        return _send_real_smtp(req)
    return _simulate_mail(req)
