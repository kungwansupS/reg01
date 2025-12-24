import subprocess
import sys
import os
import pkg_resources
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REQUIREMENTS = os.path.join(BASE_DIR, "requirements.txt")

def run_command(cmd, shell=False):
    print(f"🔹 Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(cmd, shell=shell)
    if result.returncode != 0:
        print(f"❌ Error running command: {cmd}")
        sys.exit(1)

def get_installed_packages():
    return {pkg.key: pkg.version for pkg in pkg_resources.working_set}

def parse_requirements():
    reqs = {}
    with open(REQUIREMENTS, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "==" in line:
                pkg, ver = line.split("==")
                reqs[pkg.lower()] = ("==", ver)
            else:
                reqs[line.lower()] = (None, None)
    return reqs

def get_latest_version(package):
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
    except:
        return None

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
    except:
        return False

def torch_is_cpu_only():
    """ตรวจว่า torch ที่ติดตั้งเป็น CPU หรือไม่"""
    try:
        import torch
        return not torch.cuda.is_available()
    except:
        return False

def uninstall_torch():
    print("🧹 Removing existing PyTorch (CPU)")
    run_command([
        sys.executable, "-m", "pip", "uninstall", "-y",
        "torch", "torchvision", "torchaudio"
    ])

def install_pytorch():
    cuda = has_cuda_support()

    if cuda:
        print("⚡ พบ CUDA")
        if torch_is_cpu_only():
            uninstall_torch()

        print("🚀 Installing PyTorch with CUDA 12.8")
        run_command([
            sys.executable, "-m", "pip", "install",
            "torch", "torchvision", "torchaudio",
            "--index-url", "https://download.pytorch.org/whl/cu128"
        ])
    else:
        print("🖥️ ไม่พบ CUDA → ใช้ PyTorch แบบ CPU")
        run_command([
            sys.executable, "-m", "pip", "install",
            "torch", "torchvision", "torchaudio"
        ])

# =================== MAIN PROCESS ===================

installed = get_installed_packages()
required = parse_requirements()

to_uninstall = []
to_install = []

print("🔍 Checking only required packages...")

for pkg, (op, ver) in required.items():
    current_ver = installed.get(pkg)

    if op == "==":
        if current_ver != ver:
            to_uninstall.append(pkg)
            to_install.append(f"{pkg}=={ver}")
    else:
        latest_ver = get_latest_version(pkg)
        if current_ver is None or (latest_ver and current_ver != latest_ver):
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
