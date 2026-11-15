import httpx

API_KEY = "ibk_ylvk6pdsynfihu54cbuffnfmmpnlfwn7nbkysxlw44f2waf7clda"
MACHINE_ID = "m_agq54qfr6xew7zxz3munricwcy"
BASE_URL = "https://api.instabox.sh/v1"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

keepalive_script = f"""#!/bin/bash
while true; do
  curl -s -X PUT "{BASE_URL}/machines/{MACHINE_ID}/activity-leases/apex-quant-daemon" \\
    -H "Authorization: Bearer {API_KEY}" \\
    -H "Content-Type: application/json" \\
    -d '{{"ttlSeconds": 3600}}' > /dev/null 2>&1
  sleep 300
done
"""

cmd = f"""
cat << 'EOF' > /data/workspace/keepalive.sh
{keepalive_script}
EOF
chmod +x /data/workspace/keepalive.sh
pkill -f "keepalive.sh" || true
nohup /data/workspace/keepalive.sh > /dev/null 2>&1 &
sleep 2
pgrep -f "keepalive.sh" && echo "KEEPALIVE_ONLINE" || echo "KEEPALIVE_FAILED"
"""

res = httpx.post(f"{BASE_URL}/machines/{MACHINE_ID}/exec", headers=headers, json={"cmd": cmd}, timeout=20.0)
print(res.json())
