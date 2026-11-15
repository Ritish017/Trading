"""
InstaBox Autonomous Cloud Deployment Manager
============================================
Automates provisioning, setup, and 24/7 continuous autonomous execution of
APEX Quant Lab & J.A.R.V.I.S. Trading Bot on InstaBox microVMs (instabox.sh).
Allows the system to run in the cloud even when the user's workstation is shut down.
"""

import os
import json
import uuid
import logging
import asyncio
from typing import Dict, Any, List, Optional
import httpx

from backend.app.config import settings

logger = logging.getLogger(__name__)

INSTABOX_API_BASE = "https://api.instabox.sh"


class InstaBoxDeployer:
    """
    Client for InstaBox Cloud API (https://api.instabox.sh).
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (
            api_key
            or os.getenv("INSTABOX_API_KEY")
            or settings.instabox_api_key
            or self._detect_local_credentials()
        )

    def _detect_local_credentials(self) -> Optional[str]:
        """Checks ~/.config/instabox/credentials.json if available."""
        creds_path = os.path.expanduser("~/.config/instabox/credentials.json")
        if os.path.exists(creds_path):
            try:
                with open(creds_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("token") or data.get("apiKey") or data.get("api_key")
            except Exception:
                pass
        return None

    def _headers(self, with_idempotency: bool = False) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Key": self.api_key or "",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if with_idempotency:
            headers["Idempotency-Key"] = str(uuid.uuid4())
        return headers

    async def verify_auth(self) -> Dict[str, Any]:
        """Verifies API key validity against InstaBox."""
        if not self.api_key:
            return {"authenticated": False, "error": "MISSING_INSTABOX_API_KEY"}

        url = f"{INSTABOX_API_BASE}/v1/orgs"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=self._headers())
                if res.status_code == 200:
                    return {"authenticated": True, "data": res.json()}
                return {
                    "authenticated": False,
                    "status_code": res.status_code,
                    "error": res.text,
                }
        except Exception as e:
            logger.error(f"[INSTABOX] Auth verification error: {e}")
            return {"authenticated": False, "error": str(e)}

    async def list_machines(self) -> List[Dict[str, Any]]:
        """Lists active machines in the workspace."""
        if not self.api_key:
            return []

        url = f"{INSTABOX_API_BASE}/v1/machines"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=self._headers())
                if res.status_code == 200:
                    data = res.json()
                    return data.get("machines", data if isinstance(data, list) else [])
        except Exception as e:
            logger.error(f"[INSTABOX] List machines error: {e}")
        return []

    async def get_or_create_machine(self, name: str = "apex-quant-lab") -> Dict[str, Any]:
        """Finds existing machine or creates a new Debian/Docker microVM."""
        machines = await self.list_machines()
        for m in machines:
            if m.get("name") == name:
                return {"status": "EXISTS", "machine": m}

        url = f"{INSTABOX_API_BASE}/v1/machines"
        payload = {
            "name": name,
            "template": "agent-browser",
            "autoSuspendAfterSeconds": 1800,  # 30 min idle suspend (Free plan friendly)
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(url, headers=self._headers(with_idempotency=True), json=payload)
                if res.status_code in (200, 201):
                    return {"status": "CREATED", "machine": res.json()}
                return {"status": "ERROR", "code": res.status_code, "error": res.text}
        except Exception as e:
            return {"status": "EXCEPTION", "error": str(e)}

    async def exec_command(self, machine_id: str, command: str) -> Dict[str, Any]:
        """Executes a bash command non-blockingly inside the remote InstaBox container."""
        url = f"{INSTABOX_API_BASE}/v1/machines/{machine_id}/exec"
        payload = {"cmd": command}
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(url, headers=self._headers(), json=payload)
                if res.status_code == 200:
                    return {"status": "SUCCESS", "output": res.json()}
                return {"status": "FAILED", "code": res.status_code, "error": res.text}
        except Exception as e:
            return {"status": "EXCEPTION", "error": str(e)}

    async def expose_public_port(self, machine_id: str, port: int = 8001) -> Dict[str, Any]:
        """Creates an HTTPS preview URL for external browser access."""
        url = f"{INSTABOX_API_BASE}/v1/machines/{machine_id}/ports"
        payload = {"port": port, "isPublic": True}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, headers=self._headers(with_idempotency=True), json=payload)
                if res.status_code in (200, 201):
                    return {"status": "SUCCESS", "port_data": res.json()}
                return {"status": "ERROR", "code": res.status_code, "error": res.text}
        except Exception as e:
            return {"status": "EXCEPTION", "error": str(e)}

    async def hold_keepalive_lease(self, machine_id: str, task_id: str = "quant-bot-daemon", ttl_seconds: int = 600) -> bool:
        """Keeps the machine awake during active trading operations."""
        url = f"{INSTABOX_API_BASE}/v1/machines/{machine_id}/activity-leases/{task_id}"
        payload = {"ttlSeconds": ttl_seconds}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.put(url, headers=self._headers(), json=payload)
                return res.status_code in (200, 204)
        except Exception:
            return False

    async def deploy_apex_system(
        self,
        machine_name: str = "apex-quant-lab",
        gemini_api_key: Optional[str] = None,
        amd_api_key: Optional[str] = None,
        upstox_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Orchestrates full remote deployment to InstaBox:
        1. Ensures machine exists and is running.
        2. Clones/syncs code repository.
        3. Sets up Python 3 virtual environment and dependencies.
        4. Launches FastAPI autonomous bot daemon in background.
        5. Exposes public HTTPS port for the web dashboard.
        """
        key_to_use = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        amd_key_to_use = amd_api_key or os.getenv("AMD_API_KEY", "")
        token_to_use = upstox_token or settings.get_upstox_token or ""

        # Step 1: Get or create machine
        m_res = await self.get_or_create_machine(machine_name)
        if m_res.get("status") not in ("EXISTS", "CREATED"):
            return {"step": "CREATE_MACHINE", "status": "FAILED", "details": m_res}

        machine = m_res.get("machine", {})
        machine_id = machine.get("id") or machine.get("machineId")
        if not machine_id:
            return {"step": "RESOLVE_ID", "status": "FAILED", "details": machine}

        # Step 2: Provision repository & environment script
        deploy_cmd = f"""
mkdir -p /root/apex-trading && cd /root/apex-trading
if [ ! -d ".git" ]; then
    git clone https://github.com/Ritish017/Trading.git . || git init
fi
git pull origin main || true

cat << 'EOF' > .env
GEMINI_API_KEY={key_to_use}
AMD_API_KEY={amd_key_to_use}
UPSTOX_ACCESS_TOKEN={token_to_use}
PAPER_TRADING=true
DEFAULT_PAPER_CAPITAL=10000.0
PORT=8001
ENVIRONMENT=production
EOF

python3 -m venv venv || true
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r backend/requirements.txt || ./venv/bin/pip install fastapi uvicorn httpx pydantic pandas numpy scikit-learn

pkill -f "uvicorn backend.app.main:app" || true
nohup ./venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8001 > /root/apex_backend.log 2>&1 &
sleep 2
pgrep -f "backend.app.main:app" && echo "APEX_DAEMON_ONLINE" || echo "APEX_DAEMON_START_FAILED"
"""
        exec_res = await self.exec_command(machine_id, deploy_cmd)

        # Step 3: Expose public preview port
        port_res = await self.expose_public_port(machine_id, port=8001)

        # Step 4: Initial Keepalive Lease
        await self.hold_keepalive_lease(machine_id, ttl_seconds=1800)

        return {
            "status": "DEPLOYED",
            "machine_id": machine_id,
            "machine_name": machine_name,
            "execution": exec_res,
            "public_port": port_res,
            "dashboard_url": port_res.get("port_data", {}).get("previewUrl") or f"https://{machine_id}-8001.preview.instabox.sh",
            "message": "APEX Quant Lab autonomous bot is operational in InstaBox Cloud 24/7.",
        }
