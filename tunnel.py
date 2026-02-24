import logging
import os
import re
import subprocess

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")

load_dotenv(os.path.join(BACKEND_DIR, ".env"))

from backend.app.config import PORT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def start_tunnel() -> None:
    use_quick = os.getenv("USE_QUICK_TUNNEL", "false").lower() == "true"

    subprocess.run(
        ["cloudflared", "--version"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if use_quick:
        logging.info("Starting Quick Tunnel (TryCloudflare)")
        process = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://localhost:{PORT}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        for line in process.stdout:
            if ".trycloudflare.com" in line:
                match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if match:
                    url = match.group(0)
                    print("\n" + "=" * 60)
                    print(f"Webhook URL: {url}/webhook")
                    print(f"Verify Token: {os.getenv('FB_VERIFY_TOKEN', '')}")
                    print("=" * 60 + "\n")
                    break
    else:
        tunnel_name = os.getenv("CLOUDFLARE_TUNNEL_NAME")
        if not tunnel_name:
            raise RuntimeError("CLOUDFLARE_TUNNEL_NAME not set")

        logging.info("Starting Named Tunnel: %s", tunnel_name)
        subprocess.run(["cloudflared", "tunnel", "run", tunnel_name], check=True)


if __name__ == "__main__":
    start_tunnel()
