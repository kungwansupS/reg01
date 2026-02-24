import subprocess
import sys
import os
import pkg_resources
import shutil

# ==========================================================
# PATH
# ==========================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(SCRIPT_DIR).lower() == "install":
    BASE_DIR = os.path.dirname(SCRIPT_DIR)
else:
    BASE_DIR = SCRIPT_DIR
REQUIREMENTS = os.path.join(BASE_DIR, "requirements.txt")

# ==========================================================
# UTIL
# ==========================================================
def run_command(cmd, shell=False):
    print(f"🔹 Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(cmd, shell=shell)
    if result.returncode != 0:
        print(f"❌ Command failed: {cmd}")
        sys.exit(1)

# ==========================================================
# PYTHON CHECK
# ==========================================================
def check_python_version():
    if sys.version_info < (3, 10):
        print("❌ Python >= 3.10 is required")
        sys.exit(1)
    print(f"🐍 Python {sys.version.split()[0]} OK")

# ==========================================================
# PACKAGE MANAGEMENT
# ==========================================================
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

# ==========================================================
# CUDA CHECK
# ==========================================================
def has_cuda_support():
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

# ==========================================================
# TORCH CHECK
# ==========================================================
def torch_is_installed():
    try:
        import torch
        return True
    except ImportError:
        return False

def torch_has_cuda():
    try:
        import torch
        return torch.cuda.is_available()
    except:
        return False

def uninstall_torch():
    print("🧹 Removing existing PyTorch")
    run_command([
        sys.executable, "-m", "pip", "uninstall", "-y",
        "torch", "torchvision", "torchaudio"
    ])

def install_pytorch():
    cuda_available = has_cuda_support()
    torch_installed = torch_is_installed()
    torch_cuda = torch_has_cuda()

    # -----------------------------------------
    # CASE 1: CUDA OK + Torch CUDA OK
    # -----------------------------------------
    if cuda_available and torch_installed and torch_cuda:
        print("✅ PyTorch CUDA already installed → skip")
        return

    # -----------------------------------------
    # CASE 2: CUDA OK but Torch CPU
    # -----------------------------------------
    if cuda_available:
        print("⚡ CUDA detected")

        if torch_installed and not torch_cuda:
            print("⚠️ Torch is CPU-only → upgrading to CUDA")
            uninstall_torch()

        print("🚀 Installing PyTorch CUDA (cu128)")
        run_command([
            sys.executable, "-m", "pip", "install",
            "torch", "torchvision", "torchaudio",
            "--index-url", "https://download.pytorch.org/whl/cu128"
        ])
        return

    # -----------------------------------------
    # CASE 3: No CUDA
    # -----------------------------------------
    print("🖥️ No CUDA detected")

    if torch_installed:
        print("✅ CPU PyTorch already installed → skip")
        return

    print("📦 Installing CPU-only PyTorch")
    run_command([
        sys.executable, "-m", "pip", "install",
        "torch", "torchvision", "torchaudio"
    ])

# ==========================================================
# MAIN
# ==========================================================
def main():
    print("=" * 60)
    print("🚀 REG-01 Production Installer")
    print("=" * 60)

    check_python_version()

    installed = get_installed_packages()
    required = parse_requirements()

    to_uninstall = []
    to_install = []

    print("🔍 Checking requirements...")

    for pkg, (op, ver) in required.items():
        current_ver = installed.get(pkg)

        if op == "==":
            if current_ver != ver:
                to_uninstall.append(pkg)
                to_install.append(f"{pkg}=={ver}")
        else:
            if current_ver is None:
                to_install.append(pkg)

    if to_uninstall:
        print(f"🧹 Uninstalling: {', '.join(to_uninstall)}")
        run_command([sys.executable, "-m", "pip", "uninstall", "-y"] + to_uninstall)

    if to_install:
        print(f"📥 Installing: {', '.join(to_install)}")
        run_command([sys.executable, "-m", "pip", "install"] + to_install)
    else:
        print("✅ Requirements OK")

    install_pytorch()

    print("=" * 60)
    print("🎉 Installation completed successfully")
    print("=" * 60)

# ==========================================================
if __name__ == "__main__":
    main()
