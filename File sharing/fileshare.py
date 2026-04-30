#!/usr/bin/env python3
"""
Cross-Platform File Sharing: Mac <-> Android
Uses HTTP server over local Wi-Fi. No USB, no cables, no apps needed.
Both devices must be on the same Wi-Fi network.
"""

import os
import re
import sys
import socket
import threading
import mimetypes
import urllib.parse
import qrcode                  # pip install qrcode[pil]
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO

# ─── Configuration ────────────────────────────────────────────────────────────
SHARE_DIR   = Path.home() / "FileShare"   # Folder to share (created if missing)
PORT        = 8080
# ──────────────────────────────────────────────────────────────────────────────


def get_local_ip() -> str:
    """Return the machine's LAN IP address."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def make_qr(url: str) -> str:
    """Return an ANSI QR code string for the terminal."""
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    f = BytesIO()
    qr.print_ascii(out=None)          # just to build matrix
    lines = []
    qr.print_ascii(tty=False, invert=False)
    # Render directly to string
    import io, sys
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    qr.print_ascii()
    sys.stdout = old_stdout
    return buf.getvalue()


HTML_STYLE = """
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root{--bg:#0f0f11;--card:#1a1a1f;--accent:#00e5a0;--text:#e8e8f0;--sub:#6b6b80}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;
       padding:1.5rem;min-height:100vh}
  h1{font-size:1.4rem;font-weight:700;color:var(--accent);margin-bottom:.3rem}
  p.sub{color:var(--sub);font-size:.85rem;margin-bottom:1.5rem}
  .card{background:var(--card);border-radius:12px;padding:1.2rem;margin-bottom:1rem}
  table{width:100%;border-collapse:collapse}
  td,th{padding:.55rem .7rem;text-align:left;font-size:.9rem}
  th{color:var(--sub);font-weight:600;border-bottom:1px solid #2a2a35}
  tr:hover td{background:#202028}
  a{color:var(--accent);text-decoration:none}
  a:hover{text-decoration:underline}
  .size{color:var(--sub);font-size:.8rem}
  form{display:flex;flex-direction:column;gap:.7rem}
  label{color:var(--sub);font-size:.85rem}
  input[type=file]{background:#0f0f11;color:var(--text);border:1px solid #2a2a35;
                   border-radius:8px;padding:.5rem;width:100%}
  button{background:var(--accent);color:#000;border:none;border-radius:8px;
         padding:.65rem 1.5rem;font-weight:700;cursor:pointer;font-size:.95rem;
         align-self:flex-start}
  button:hover{opacity:.85}
  .msg{padding:.6rem 1rem;border-radius:8px;font-size:.9rem;margin-bottom:1rem}
  .ok{background:#0a2e20;color:var(--accent);border:1px solid #00e5a040}
  .err{background:#2e0a0a;color:#ff6b6b;border:1px solid #ff6b6b40}
  .empty{color:var(--sub);font-size:.9rem;padding:.5rem 0}
    .upload-hint{color:var(--sub);font-size:.8rem}

    .uploader{display:none;margin-top:.9rem;padding:.85rem;border:1px solid #2a2a35;
                        border-radius:10px;background:#121218}
    .uploader.active{display:block}
    .upload-top{display:flex;align-items:center;gap:.6rem;margin-bottom:.5rem}
    .spinner{width:16px;height:16px;border-radius:50%;border:2px solid #2f3a34;
                     border-top-color:var(--accent);animation:spin .9s linear infinite}
    .upload-text{font-size:.85rem;color:#cdd1df}
    .progress-wrap{height:10px;border-radius:999px;background:#23232d;overflow:hidden}
    .progress-bar{height:100%;width:4%;background:linear-gradient(90deg,#00e5a0,#76f7d0);
                                border-radius:999px;position:relative;transition:width .2s ease}
    .progress-bar::after{content:"";position:absolute;inset:0;
                                             background:linear-gradient(120deg,transparent 0%,#ffffff44 40%,transparent 80%);
                                             transform:translateX(-100%);animation:shimmer 1.2s linear infinite}
    .percent{margin-top:.45rem;font-size:.8rem;color:var(--sub)}

    @keyframes spin{to{transform:rotate(360deg)}}
    @keyframes shimmer{to{transform:translateX(220%)}}
</style>
"""


class FileShareHandler(BaseHTTPRequestHandler):
    """Handles file listing, downloading, and uploading."""

    def log_message(self, fmt, *args):
        print(f"  [{self.address_string()}] {fmt % args}")

    # ── Routing ──────────────────────────────────────────────────────────────

    def do_GET(self):
        path = urllib.parse.unquote(self.path.split("?")[0])
        if path == "/" or path == "":
            self._serve_index()
        elif path.startswith("/download/"):
            filename = path[len("/download/"):]
            self._serve_file(filename)
        elif path == "/favicon.ico":
            self.send_response(204); self.end_headers()
        else:
            self._send_404()

    def do_POST(self):
        if self.path == "/upload":
            self._handle_upload()
        else:
            self._send_404()

    # ── Pages ─────────────────────────────────────────────────────────────────

    def _serve_index(self, message="", msg_type=""):
        files = sorted(SHARE_DIR.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True) \
                if SHARE_DIR.exists() else []

        rows = ""
        if files:
            for f in files:
                if f.is_file():
                    name_enc = urllib.parse.quote(f.name)
                    rows += (
                        f"<tr><td><a href='/download/{name_enc}'>{f.name}</a></td>"
                        f"<td class='size'>{human_size(f.stat().st_size)}</td></tr>"
                    )
        else:
            rows = "<tr><td colspan=2 class='empty'>No files yet — upload something!</td></tr>"

        msg_html = f"<div class='msg {msg_type}'>{message}</div>" if message else ""

        html = f"""<!DOCTYPE html><html><head><title>FileShare</title>{HTML_STYLE}</head><body>
<h1>📡 FileShare</h1>
<p class="sub">Mac ↔ Android file transfer over Wi-Fi</p>
{msg_html}
<div class="card">
  <p style="font-weight:600;margin-bottom:.9rem">Upload a file</p>
    <form id="uploadForm" method="POST" action="/upload" enctype="multipart/form-data">
    <label>Choose file (photo, video, audio, document…)</label>
    <input type="file" name="file" required>
        <p class="upload-hint">No file size limit. Large uploads can take time.</p>
    <button type="submit">Upload ↑</button>
  </form>
    <div id="uploader" class="uploader" aria-live="polite">
        <div class="upload-top">
            <div class="spinner"></div>
            <div class="upload-text" id="uploadText">Uploading file...</div>
        </div>
        <div class="progress-wrap"><div id="progressBar" class="progress-bar"></div></div>
        <p class="percent" id="uploadPercent">Starting...</p>
    </div>
</div>
<div class="card">
  <p style="font-weight:600;margin-bottom:.9rem">Shared files</p>
  <table>
    <tr><th>File</th><th>Size</th></tr>
    {rows}
  </table>
</div>
<script>
    const form = document.getElementById('uploadForm');
    const uploader = document.getElementById('uploader');
    const progressBar = document.getElementById('progressBar');
    const uploadText = document.getElementById('uploadText');
    const uploadPercent = document.getElementById('uploadPercent');

    if (form) {{
        form.addEventListener('submit', function (e) {{
            e.preventDefault();
            const data = new FormData(form);
            const fileInput = form.querySelector('input[type="file"]');
            const selectedName = fileInput && fileInput.files && fileInput.files[0] ? fileInput.files[0].name : 'file';

            uploader.classList.add('active');
            uploadText.textContent = 'Uploading ' + selectedName + '...';
            uploadPercent.textContent = 'Preparing upload...';
            progressBar.style.width = '4%';

            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/upload', true);

            xhr.upload.onprogress = function (event) {{
                if (event.lengthComputable) {{
                    const percent = Math.max(4, Math.round((event.loaded / event.total) * 100));
                    progressBar.style.width = percent + '%';
                    uploadPercent.textContent = percent + '% uploaded';
                }} else {{
                    uploadPercent.textContent = 'Uploading...';
                }}
            }};

            xhr.onload = function () {{
                if (xhr.status >= 200 && xhr.status < 300) {{
                    progressBar.style.width = '100%';
                    uploadPercent.textContent = 'Upload complete';
                    document.open();
                    document.write(xhr.responseText);
                    document.close();
                }} else {{
                    uploadText.textContent = 'Upload failed';
                    uploadPercent.textContent = 'Server error. Try again.';
                }}
            }};

            xhr.onerror = function () {{
                uploadText.textContent = 'Upload failed';
                uploadPercent.textContent = 'Network error. Check connection and retry.';
            }};

            xhr.send(data);
        }});
    }}
</script>
</body></html>"""

        self._send_html(html)

    def _serve_file(self, filename: str):
        target = SHARE_DIR / filename
        if not target.exists() or not target.is_file():
            self._send_404(); return

        mime, _ = mimetypes.guess_type(str(target))
        mime = mime or "application/octet-stream"
        size = target.stat().st_size

        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()

        with open(target, "rb") as fh:
            while chunk := fh.read(65536):
                self.wfile.write(chunk)
        print(f"  ↓ Downloaded: {filename} ({human_size(size)})")

    # ── Upload handler ────────────────────────────────────────────────────────

    def _handle_upload(self):
        content_type = self.headers.get("Content-Type", "")
        if "boundary=" not in content_type:
            self._serve_index("Invalid upload request.", "err"); return

        boundary = content_type.split("boundary=")[1].strip().encode()
        length = int(self.headers.get("Content-Length", 0))

        if length <= 0:
            self._serve_index("Empty upload request.", "err"); return

        parsed = self._stream_multipart_to_file(boundary, length)
        if not parsed:
            self._serve_index("Could not parse upload.", "err"); return

        dest, written = parsed
        print(f"  ↑ Uploaded: {dest.name} ({human_size(written)})")
        self._serve_index(f"✓ '{dest.name}' uploaded successfully!", "ok")

    def _stream_multipart_to_file(self, boundary: bytes, total_length: int):
        """Stream a multipart upload directly to disk to support very large files."""
        SHARE_DIR.mkdir(parents=True, exist_ok=True)

        boundary_line = b"--" + boundary
        header = self.rfile.readline()
        if not header.startswith(boundary_line):
            return None

        content_disposition = ""
        while True:
            line = self.rfile.readline()
            if line in (b"\r\n", b"\n", b""):
                break
            text = line.decode("utf-8", errors="ignore").strip()
            if text.lower().startswith("content-disposition:"):
                content_disposition = text

        match = re.search(r'filename="([^\"]*)"', content_disposition)
        if not match:
            return None

        filename = Path(match.group(1)).name
        if not filename:
            return None

        dest = SHARE_DIR / filename
        bytes_written = 0
        prev = self.rfile.readline()
        with open(dest, "wb") as fh:
            while True:
                line = self.rfile.readline()
                if line.startswith(boundary_line):
                    if prev.endswith(b"\r\n"):
                        prev = prev[:-2]
                    elif prev.endswith(b"\n"):
                        prev = prev[:-1]
                    if prev:
                        fh.write(prev)
                        bytes_written += len(prev)
                    break

                fh.write(prev)
                bytes_written += len(prev)
                prev = line

        return dest, bytes_written

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _send_html(self, html: str):
        encoded = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_404(self):
        self.send_response(404); self.end_headers()


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    SHARE_DIR.mkdir(parents=True, exist_ok=True)
    ip  = get_local_ip()
    url = f"http://{ip}:{PORT}"

    print("\n" + "═" * 54)
    print("  📡  FileShare — Mac ↔ Android over Wi-Fi")
    print("═" * 54)
    print(f"  Local URL   : {url}")
    print(f"  Share folder: {SHARE_DIR}")
    print("─" * 54)
    print("  HOW TO USE:")
    print("  1. Make sure Mac + Android are on the SAME Wi-Fi")
    print(f"  2. On Android, open browser → {url}")
    print("     OR scan the QR code below ↓")
    print("  3. Upload / Download any file type")
    print("─" * 54)

    # Print QR code
    try:
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii()
    except ImportError:
        print(f"  Install qrcode for QR: pip install qrcode[pil]")

    print("─" * 54)
    print("  Press Ctrl+C to stop the server")
    print("═" * 54 + "\n")

    server = HTTPServer(("0.0.0.0", PORT), FileShareHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n  Server stopped. Goodbye!\n")
        server.server_close()


if __name__ == "__main__":
    main()