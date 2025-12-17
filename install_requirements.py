import subprocess
import sys
import os
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

REQ_FILES = [
    "requirements.txt",
    "requirements_rag.txt",
    "requirements_ai.txt",
    "requirements_dev.txt",  # optional
]

# ================== UTILS ==================

def run(cmd):
    print(f"🔹 Running: {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print("❌ Command failed")
        sys.exit(result.returncode)

def pip(cmd):
    run(f'"{sys.executable}" -m pip {cmd}')

def exists(path):
    return os.path.exists(os.path.join(BASE_DIR, path))

# ================== SYSTEM CHECK ==================

def ensure_pip_health():
    print("🛠️ Ensuring pip / setuptools / wheel are healthy...")
    pip("install --upgrade pip setuptools wheel")

def has_cuda():
    if shutil.which("nvidia-smi") is None:
        return False
    try:
        out = subprocess.check_output("nvidia-smi", shell=True, text=True)
        return "CUDA Version" in out
    except:
        return False

# ================== INSTALLERS ==================

def install_requirements():
    for req in REQ_FILES:
        path = os.path.join(BASE_DIR, req)
        if not os.path.exists(path):
            print(f"⚠️ Skip {req} (not found)")
            continue

        print(f"📦 Installing from {req}")
        pip(
            f'install -r "{path}" '
            "--upgrade "
            "--upgrade-strategy only-if-needed"
        )

def install_pytorch():
    if has_cuda():
        print("⚡ CUDA detected → Installing PyTorch (cu128)")
        pip(
            "install torch torchvision torchaudio "
            "--index-url https://download.pytorch.org/whl/cu128 "
            "--upgrade --upgrade-strategy only-if-needed"
        )
    else:
        print("🖥️ No CUDA → Installing CPU PyTorch")
        pip(
            "install torch torchvision torchaudio "
            "--upgrade --upgrade-strategy only-if-needed"
        )

# ================== MAIN ==================

def main():
    print("🚀 INSTALLER START")
    print(f"🐍 Python: {sys.version.split()[0]}")

    ensure_pip_health()
    install_requirements()
    install_pytorch()

    print("🎉 INSTALL COMPLETE – System Ready")

if __name__ == "__main__":
    main()
