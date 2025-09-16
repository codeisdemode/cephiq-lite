from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib import request, error
from urllib.parse import urlparse


@dataclass
class LocalMCPServer:
    # Use the FastAPI-based legacy app that exposes /sse/ and /tools/*
    # This works with uvicorn and the "direct" HTTP client.
    module: str = "combined_mcp_server_old:app"
    host: str = "127.0.0.1"
    port: int = 8000
    cwd: Optional[Path] = None

    _proc: Optional[subprocess.Popen] = None

    def start(self, wait_seconds: float = 15.0) -> None:
        if self._proc and self._proc.poll() is None:
            return
        # Launch FastAPI app via uvicorn (module:app)
        cmd = [sys.executable, "-m", "uvicorn", self.module, "--host", self.host, "--port", str(self.port)]
        self._proc = subprocess.Popen(cmd, cwd=str(self.cwd or Path.cwd()))
        # Wait for readiness on /sse/
        deadline = time.time() + wait_seconds
        url = f"http://{self.host}:{self.port}/sse/"
        while time.time() < deadline:
            try:
                req = request.Request(url, method="GET")
                with request.urlopen(req, timeout=1.5) as resp:
                    if resp.status == 200:
                        return
            except Exception:
                time.sleep(0.3)
        raise RuntimeError(f"Local MCP server failed to become ready at {url}")

    def stop(self, wait_seconds: float = 5.0) -> None:
        if not self._proc:
            return
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=wait_seconds)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=wait_seconds)
        self._proc = None


def url_is_local(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.hostname in {"127.0.0.1", "localhost"}
    except Exception:
        return False


def url_reachable(url: str, timeout: float = 1.5) -> bool:
    try:
        req = request.Request(url, method="GET")
        with request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False
