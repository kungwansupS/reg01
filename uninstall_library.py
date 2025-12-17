import subprocess
import sys
import pkg_resources

# ==================================================
# CONFIG
# ==================================================

EXCLUDE_PACKAGES = {
    "pip",
    "setuptools",
    "wheel"
}

# ==================================================
# UTILS
# ==================================================

def run_command(cmd):
    print(f"🔹 Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("❌ Command failed")
        sys.exit(1)

def get_installed_packages():
    """คืนรายชื่อ package ทั้งหมดที่ติดตั้งด้วย pip"""
    return sorted({pkg.key for pkg in pkg_resources.working_set})

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

    installed_packages = get_installed_packages()
    to_remove = [pkg for pkg in installed_packages if pkg not in EXCLUDE_PACKAGES]

    if not to_remove:
        print("✅ No packages to uninstall.")
        return

    print(f"\n🧹 Packages to uninstall ({len(to_remove)}):")
    print(", ".join(to_remove))

    run_command([
        sys.executable, "-m", "pip", "uninstall", "-y", *to_remove
    ])

    print("\n🎉 Done. Environment is now clean.")

# ==================================================
# ENTRY
# ==================================================

if __name__ == "__main__":
    main()
