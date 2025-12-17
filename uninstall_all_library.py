import subprocess
import sys

# ==================================================
# CONFIG
# ==================================================

EXCLUDE = {
    "pip",
    "setuptools",
    "wheel"
}

BATCH_SIZE = 20  # ปลอดภัย ไม่ยาวเกินไป

# ==================================================
# UTILS
# ==================================================

def run(cmd):
    print(f"🔹 Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("❌ Command failed")
        sys.exit(1)

def get_installed_packages():
    """
    ใช้ pip freeze (เชื่อถือได้ที่สุด)
    คืนค่าเป็น list[str] ของชื่อ package
    """
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        stdout=subprocess.PIPE,
        text=True
    )

    packages = []

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # format: name==version
        if "==" in line:
            name = line.split("==", 1)[0].lower()
        else:
            name = line.lower()

        # safety filter
        if name.startswith("-"):
            continue
        if name in EXCLUDE:
            continue

        packages.append(name)

    return sorted(set(packages))

# ==================================================
# MAIN
# ==================================================

def main():
    print("⚠️ WARNING: This will UNINSTALL ALL pip packages in this environment!")
    print("📌 Recommended: Use inside venv / conda only\n")

    confirm = input("Type 'YES' to continue: ").strip()
    if confirm != "YES":
        print("❌ Aborted.")
        return

    packages = get_installed_packages()

    if not packages:
        print("✅ No packages to uninstall.")
        return

    print(f"\n🧹 Packages to uninstall ({len(packages)}):")
    print(", ".join(packages))

    # uninstall เป็น batch เพื่อความเสถียร
    for i in range(0, len(packages), BATCH_SIZE):
        batch = packages[i:i + BATCH_SIZE]
        run([sys.executable, "-m", "pip", "uninstall", "-y", *batch])

    print("\n🎉 Done. Environment is now CLEAN.")

# ==================================================
# ENTRY
# ==================================================

if __name__ == "__main__":
    main()
