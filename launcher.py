"""
啟動器 - 檢查環境並啟動主系統
"""
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("=" * 50)
print("  Stock Valuation System")
print("=" * 50)
print()

# 1. Check Python
print(f"[1/3] Python: {sys.version.split()[0]}")

# 2. Install dependencies
print("[2/3] Installing dependencies...")
result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
    capture_output=True, text=True
)
if result.returncode != 0:
    print(f"  Warning: {result.stderr.strip()[:200]}")
else:
    print("  OK")

# 3. Launch
print("[3/3] Starting system...")
print()
print("  Dashboard: http://localhost:8080")
print("  Press Ctrl+C to stop")
print("=" * 50)
print()

sys.exit(subprocess.call([sys.executable, "main.py"]))
