import os
import subprocess
import logging
import re
import sys
import urllib.request
from dotenv import load_dotenv

# ================== PATH SETUP ==================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
CLOUDFLARED_EXE = os.path.join(TOOLS_DIR, "cloudflared.exe")

os.makedirs(TOOLS_DIR, exist_ok=True)

load_dotenv(os.path.join(BACKEND_DIR, ".env"))

from backend.app.config import PORT

# ================== LOGGING ==================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ================== CLOUDLFARED HELPERS ==================

CLOUDFLARED_DOWNLOAD_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/"
    "download/cloudflared-windows-amd64.exe"
)

def download_cloudflared():
    logging.info("⬇️  cloudflared not found, downloading automatically...")
    try:
        urllib.request.urlretrieve(CLOUDFLARED_DOWNLOAD_URL, CLOUDFLARED_EXE)
        logging.info("✅ cloudflared downloaded successfully")
    except Exception as e:
        raise RuntimeError(f"Failed to download cloudflared: {e}")

def get_cloudflared_path():
    """
    Priority:
    1. Local tools/cloudflared.exe
    2. cloudflared from PATH
    """
    if os.path.exists(CLOUDFLARED_EXE):
        return CLOUDFLARED_EXE

    from shutil import which
    path = which("cloudflared")
    if path:
        return path

    download_cloudflared()
    return CLOUDFLARED_EXE

# ================== MAIN LOGIC ==================

def start_tunnel():
    use_quick = os.getenv("USE_QUICK_TUNNEL", "false").lower() == "true"

    cloudflared = get_cloudflared_path()

    # sanity check
    subprocess.run(
        [cloudflared, "--version"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if use_quick:
        logging.info("⚡ Starting Quick Tunnel (TryCloudflare)")

        process = subprocess.Popen(
            [cloudflared, "tunnel", "--url", f"http://localhost:{PORT}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        for line in process.stdout:
            if ".trycloudflare.com" in line:
                match = re.search(
                    r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line
                )
                if match:
                    url = match.group(0)
                    print("\n" + "=" * 60)
                    print(f"🔗 Webhook URL: {url}/webhook")
                    print(f"🔑 Verify Token: {os.getenv('FB_VERIFY_TOKEN')}")
                    print("=" * 60 + "\n")
                    break
    else:
        tunnel_name = os.getenv("CLOUDFLARE_TUNNEL_NAME")
        if not tunnel_name:
            raise RuntimeError("CLOUDFLARE_TUNNEL_NAME not set")

        logging.info(f"🌐 Starting Named Tunnel: {tunnel_name}")
        subprocess.run(
            [cloudflared, "tunnel", "run", tunnel_name],
            check=True,
        )

# ================== ENTRY ==================

if __name__ == "__main__":
    try:
        start_tunnel()
    except Exception as e:
        logging.error(str(e))
        sys.exit(1) 