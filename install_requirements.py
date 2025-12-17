import subprocess
import sys
import os
import pkg_resources
import shutil

# ==================================================
# CONFIG
# ==================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REQUIREMENTS = os.path.join(BASE_DIR, "requirements.txt")

# ==================================================
# UTILS
# ==================================================

def run_command(cmd, shell=False):
    cmd_display = " ".join(cmd) if isinstance(cmd, list) else cmd
    print(f"🔹 Running: {cmd_display}")
    result = subprocess.run(cmd, shell=shell)
    if result.returncode != 0:
        print(f"❌ Error running command: {cmd_display}")
        sys.exit(1)

def get_installed_packages():
    """คืน dict ของ package ที่ติดตั้งแล้ว {name: version}"""
    return {pkg.key: pkg.version for pkg in pkg_resources.working_set}

# ==================================================
# REQUIREMENTS PARSER (FIXED ENCODING)
# ==================================================

def parse_requirements():
    """
    อ่าน requirements.txt
    - รองรับ UTF-8 / UTF-8 BOM / Windows ภาษาไทย
    - รองรับ:
        pkg
        pkg==1.2.3
        pkg>=1.0.0
    """
    reqs = {}

    try:
        f = open(REQUIREMENTS, "r", encoding="utf-8-sig")
    except UnicodeDecodeError:
        f = open(REQUIREMENTS, "r", encoding="cp874")

    with f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            if "==" in line:
                pkg, ver = line.split("==", 1)
                reqs[pkg.lower()] = ("==", ver)

            elif ">=" in line:
                pkg, ver = line.split(">=", 1)
                reqs[pkg.lower()] = (">=", ver)

            else:
                reqs[line.lower()] = (None, None)

    return reqs

# ==================================================
# PIP HELPERS
# ==================================================

def get_latest_version(package):
    """ดึงเวอร์ชันล่าสุดจาก pip index (ถ้าได้)"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "index", "versions", package],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True
        )
        for line in result.stdout.splitlines():
            if "Available versions:" in line:
                return line.split(":")[1].split(",")[0].strip()
    except Exception:
        pass
    return None

# ==================================================
# CUDA / PYTORCH
# ==================================================

def has_cuda_support():
    """ตรวจสอบว่าเครื่องมี NVIDIA GPU + CUDA"""
    if shutil.which("nvidia-smi") is None:
        return False
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True
        )
        return "CUDA Version" in result.stdout
    except Exception:
        return False

def install_pytorch():
    """ติดตั้ง PyTorch ตามสภาพเครื่อง"""
    if has_cuda_support():
        print("⚡ พบ CUDA → ติดตั้ง PyTorch (CUDA 12.8)")
        run_command([
            sys.executable, "-m", "pip", "install",
            "torch", "torchvision", "torchaudio",
            "--index-url", "https://download.pytorch.org/whl/cu128"
        ])
    else:
        print("🖥️ ไม่พบ CUDA → ติดตั้ง PyTorch (CPU)")
        run_command([
            sys.executable, "-m", "pip", "install",
            "torch", "torchvision", "torchaudio"
        ])

# ==================================================
# MAIN PROCESS
# ==================================================

def main():
    installed = get_installed_packages()
    required = parse_requirements()

    to_uninstall = []
    to_install = []

    print("🔍 Checking required packages...")

    for pkg, (op, ver) in required.items():
        current_ver = installed.get(pkg)

        if op == "==":
            if current_ver != ver:
                if current_ver:
                    to_uninstall.append(pkg)
                to_install.append(f"{pkg}=={ver}")

        elif op == ">=":
            if current_ver is None:
                to_install.append(f"{pkg}>={ver}")

        else:
            latest_ver = get_latest_version(pkg)
            if current_ver is None or (latest_ver and current_ver != latest_ver):
                if current_ver:
                    to_uninstall.append(pkg)
                to_install.append(pkg)

    if to_uninstall:
        print(f"🧹 Uninstalling: {', '.join(to_uninstall)}")
        run_command([sys.executable, "-m", "pip", "uninstall", "-y"] + to_uninstall)

    if to_install:
        print(f"📥 Installing: {', '.join(to_install)}")
        run_command([sys.executable, "-m", "pip", "install"] + to_install)
    else:
        print("✅ All required packages are up to date.")

    install_pytorch()

    print("🎉 Done.")

# ==================================================
# ENTRY
# ==================================================

if __name__ == "__main__":
    main()
