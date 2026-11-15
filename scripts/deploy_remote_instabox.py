import os
import sys
import time
import httpx
from backend.app.config import settings

API_KEY = os.getenv("INSTABOX_API_KEY", "ibk_ylvk6pdsynfihu54cbuffnfmmpnlfwn7nbkysxlw44f2waf7clda")
MACHINE_ID = "m_agq54qfr6xew7zxz3munricwcy"
BASE_URL = "https://api.instabox.sh/v1"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

def exec_cmd(cmd: str, timeout: float = 120.0):
    url = f"{BASE_URL}/machines/{MACHINE_ID}/exec"
    payload = {"cmd": cmd}
    res = httpx.post(url, headers=headers, json=payload, timeout=timeout)
    data = res.json()
    stdout = data.get("stdout", "")
    stderr = data.get("stderr", "")
    code = data.get("exitCode", -1)
    return code, stdout, stderr

print("[1/5] Checking machine status...")
m_res = httpx.get(f"{BASE_URL}/machines/{MACHINE_ID}", headers=headers, timeout=15.0)
m_data = m_res.json()
print("Machine State:", m_data.get("state"), "| Desired:", m_data.get("desiredState"))

print("[2/5] Syncing Git repository...")
clone_cmd = """
mkdir -p /data/workspace
cd /data/workspace
if [ ! -d "apex-trading" ]; then
    git clone https://github.com/Ritish017/Trading.git apex-trading
else
    cd apex-trading && git fetch origin && git reset --hard origin/main
fi
"""
code, out, err = exec_cmd(clone_cmd, timeout=60.0)
print(f"Git Sync exited with {code}: {out} {err}")

gemini_key = os.getenv("GEMINI_API_KEY", "")
amd_key = os.getenv("AMD_API_KEY", "")
upstox_token = settings.get_upstox_token or ""

print("[3/5] Provisioning .env configuration...")
env_content = f"""ENVIRONMENT=production
PORT=8001
GEMINI_API_KEY={gemini_key}
AMD_API_KEY={amd_key}
UPSTOX_ACCESS_TOKEN={upstox_token}
PAPER_TRADING=true
DEFAULT_PAPER_CAPITAL=10000.0
ACTIVE_BROKER_PROVIDER=UPSTOX
UPSTOX_ENABLED=true
UPSTOX_WS_ENABLED=true
"""

write_env_cmd = f"""
cat << 'EOF' > /data/workspace/apex-trading/.env
{env_content}
EOF
cat /data/workspace/apex-trading/.env | head -n 8
"""
code, out, err = exec_cmd(write_env_cmd, timeout=20.0)
print(f"Configured .env: {out}")

print("[4/5] Setting up Python virtual environment and dependencies...")
setup_python_cmd = """
cd /data/workspace
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r apex-trading/backend/requirements.txt || ./venv/bin/pip install fastapi "uvicorn[standard]" httpx pydantic pydantic-settings pandas numpy scikit-learn websockets scipy
"""
code, out, err = exec_cmd(setup_python_cmd, timeout=180.0)
print(f"Dependencies installed with code {code}.")

print("[5/5] Launching APEX Quant Lab & J.A.R.V.I.S. daemon on port 8001...")
launch_cmd = """
cd /data/workspace/apex-trading
pkill -f "uvicorn backend.app.main:app" || true
nohup /data/workspace/venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8001 > /data/workspace/apex_backend.log 2>&1 &
sleep 3
pgrep -f "backend.app.main:app" && echo "APEX_DAEMON_ONLINE" || echo "APEX_DAEMON_FAILED"
"""
code, out, err = exec_cmd(launch_cmd, timeout=30.0)
print(f"Daemon startup output: {out} {err}")

# Holding keepalive lease
print("Renewing 24/7 keepalive lease...")
lease_res = httpx.put(
    f"{BASE_URL}/machines/{MACHINE_ID}/activity-leases/apex-quant-daemon",
    headers=headers,
    json={"ttlSeconds": 86400},  # 24 hours
    timeout=15.0,
)
print("Lease renewal response:", lease_res.json())

print("ALL DEPLOYMENT STEPS COMPLETED!")
