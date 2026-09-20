"""Orchestrator script to run both FastAPI backend and Streamlit frontend concurrently.

Optimized for both local development and cloud production deployment
(Docker, Render, Hugging Face Spaces, Fly.io, AWS, Heroku, Railway).
"""

import os
import sys
import time
import signal
import subprocess
import urllib.request


# ==============================================================================
# CONFIGURATION & ENVIRONMENT DETECTION
# ==============================================================================
API_PORT = int(os.environ.get("API_PORT", 8000))
# Cloud platforms (Render, Heroku, Cloud Run) set the PORT env variable for the public web app
STREAMLIT_PORT = int(os.environ.get("PORT", os.environ.get("STREAMLIT_PORT", 8501)))

# Bind address: 0.0.0.0 in Docker/cloud containers, 127.0.0.1 for local dev
HOST = os.environ.get("HOST", "0.0.0.0" if os.environ.get("DOCKER_CONTAINER") or os.environ.get("PORT") else "127.0.0.1")
API_HOST = os.environ.get("API_HOST", "127.0.0.1" if HOST == "127.0.0.1" else "0.0.0.0")

# Headless / browser automation
IS_HEADLESS = (
    os.environ.get("HEADLESS", "").lower() in ("true", "1")
    or os.environ.get("NO_BROWSER", "").lower() in ("true", "1")
    or os.environ.get("DOCKER_CONTAINER") is not None
    or os.environ.get("PORT") is not None
)


def wait_for_api(timeout: float = 12.0) -> bool:
    """Poll the backend healthcheck endpoint until it is ready."""
    check_host = "127.0.0.1" if API_HOST in ("0.0.0.0", "127.0.0.1") else API_HOST
    url = f"http://{check_host}:{API_PORT}/api/health"
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.4)
    return False


def main():
    print("=" * 64)
    print("  Dual-Panel Protocol Simulator (FastAPI + Streamlit)")
    print("=" * 64)
    print(f"[*] API Target:       http://{API_HOST}:{API_PORT}")
    print(f"[*] Streamlit Target: http://{HOST}:{STREAMLIT_PORT}")
    print(f"[*] Mode:             {'Headless / Production' if IS_HEADLESS else 'Interactive Local'}")
    print("=" * 64)

    # Launch FastAPI backend
    fastapi_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        API_HOST,
        "--port",
        str(API_PORT),
        "--log-level",
        os.environ.get("LOG_LEVEL", "info"),
    ]
    print(f"[*] Launching FastAPI backend on port {API_PORT} ...")
    backend_proc = subprocess.Popen(fastapi_cmd)

    # Wait for backend readiness
    if wait_for_api(12):
        print(f"[OK] FastAPI backend is ONLINE at http://{API_HOST}:{API_PORT}/api/health")
    else:
        print("[!] Backend startup took longer than expected; proceeding with frontend...")

    # Pass API URL to Streamlit frontend
    streamlit_env = os.environ.copy()
    if "API_BASE_URL" not in streamlit_env:
        streamlit_env["API_BASE_URL"] = f"http://127.0.0.1:{API_PORT}"

    # Launch Streamlit frontend
    streamlit_cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "frontend/app.py",
        "--server.address",
        HOST,
        "--server.port",
        str(STREAMLIT_PORT),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    print(f"[*] Launching Streamlit frontend on port {STREAMLIT_PORT} ...")
    frontend_proc = subprocess.Popen(streamlit_cmd, env=streamlit_env)

    print("\n" + "=" * 64)
    print("  SERVICES RUNNING:")
    print(f"  -> UI Dashboard:   http://localhost:{STREAMLIT_PORT}")
    print(f"  -> OpenAPI Docs:   http://localhost:{API_PORT}/docs")
    print("=" * 64)
    print("Press Ctrl+C to stop all services.\n")

    # Automatically open browser if running locally in interactive mode
    if not IS_HEADLESS:
        try:
            import webbrowser
            time.sleep(1.5)
            webbrowser.open(f"http://localhost:{STREAMLIT_PORT}")
        except Exception:
            pass

    def shutdown(sig=None, frame=None):
        print("\n[*] Stopping all services...")
        for proc in [frontend_proc, backend_proc]:
            try:
                proc.terminate()
            except Exception:
                pass
        for proc in [frontend_proc, backend_proc]:
            try:
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        print("[OK] All services stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Monitor processes: if either dies, gracefully terminate the other
    try:
        while True:
            frontend_ret = frontend_proc.poll()
            backend_ret = backend_proc.poll()

            if frontend_ret is not None:
                print(f"[!] Frontend process exited with code {frontend_ret}")
                shutdown()
            if backend_ret is not None:
                print(f"[!] Backend process exited with code {backend_ret}")
                shutdown()

            time.sleep(1.0)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
