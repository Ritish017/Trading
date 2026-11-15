"""
APEX Quant Lab MCP Server Bridge
================================
Implements Model Context Protocol (MCP) JSON-RPC over stdin/stdout.
Allows OpenMausBot (milind-soni/OpenMausBot), Claude Code, Cursor, and mobile
agents to natively query market data, control the NIFTY autonomous bot, and
execute paper orders directly through conversational chat.
"""

import sys
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
import httpx

logging.basicConfig(level=logging.ERROR, stream=sys.stderr)
logger = logging.getLogger("apex_mcp_server")

BACKEND_URL = "http://127.0.0.1:8001"

TOOLS = [
    {
        "name": "get_nifty_market_status",
        "description": "Fetches real-time NIFTY 50 spot price, futures basis, basis velocity, PCR, IV percentile, and news sentiment score.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_bot_telemetry",
        "description": "Retrieves autonomous NIFTY bot state, daily PnL, circuit breaker status, active positions, and active evolving rules.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "trigger_bot_scan",
        "description": "Triggers an on-demand quantitative scan across spot, futures, and Greeks, returning the formulated strategy signal and execution rationale.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "force_scan": {
                    "type": "boolean",
                    "description": "Whether to force evaluation regardless of market hours gate.",
                    "default": True,
                }
            },
        },
    },
    {
        "name": "toggle_auto_trade",
        "description": "Arms or disarms autonomous order placement for the NIFTY bot.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "description": "True to arm autonomous trading, False to disarm.",
                }
            },
            "required": ["enabled"],
        },
    },
    {
        "name": "synthesize_trading_rules",
        "description": "Triggers J.A.R.V.I.S. reflection via Gemini Pro to analyze recent paper trade outcomes and synthesize new adaptive rules.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_option_chain",
        "description": "Retrieves the live institutional option chain strike ladder with live LTP, Bid/Ask, and Greeks for a given symbol (e.g. 'NIFTY 50' or 'RELIANCE.NS').",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Underlying symbol, e.g. 'NIFTY 50' or 'RELIANCE.NS'.",
                    "default": "NIFTY 50",
                }
            },
        },
    },
    {
        "name": "execute_paper_order",
        "description": "Places an authoritative paper order within the ₹10,000 risk ledger.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading symbol (e.g. 'NIFTY24500CE')"},
                "side": {"type": "string", "enum": ["BUY", "SELL"], "description": "Order side"},
                "quantity": {"type": "integer", "description": "Quantity in lots/shares (standard NIFTY lot is 25)"},
                "price": {"type": "number", "description": "Limit or market execution price in INR"},
                "productType": {"type": "string", "enum": ["CNC", "MIS"], "default": "CNC"},
            },
            "required": ["symbol", "side", "quantity", "price"],
        },
    },
]


async def handle_tool_call(name: str, args: Dict[str, Any]) -> Any:
    async with httpx.AsyncClient(timeout=25.0) as client:
        if name == "get_nifty_market_status":
            res = await client.get(f"{BACKEND_URL}/api/nifty-bot/status")
            news_res = await client.get(f"{BACKEND_URL}/api/news/sentiment")
            return {
                "bot_status": res.json() if res.status_code == 200 else {},
                "news_sentiment": news_res.json() if news_res.status_code == 200 else {},
            }

        elif name == "get_bot_telemetry":
            res = await client.get(f"{BACKEND_URL}/api/nifty-bot/status")
            rules_res = await client.get(f"{BACKEND_URL}/api/nifty-bot/rules")
            return {
                "telemetry": res.json() if res.status_code == 200 else {},
                "rules": rules_res.json() if rules_res.status_code == 200 else {},
            }

        elif name == "trigger_bot_scan":
            force = args.get("force_scan", True)
            res = await client.post(f"{BACKEND_URL}/api/nifty-bot/scan?force_scan={str(force).lower()}")
            return res.json() if res.status_code == 200 else {"error": res.text}

        elif name == "toggle_auto_trade":
            enabled = args.get("enabled", False)
            res = await client.post(f"{BACKEND_URL}/api/nifty-bot/toggle", json={"enabled": enabled})
            return res.json() if res.status_code == 200 else {"error": res.text}

        elif name == "synthesize_trading_rules":
            res = await client.post(f"{BACKEND_URL}/api/nifty-bot/rules/evolve")
            return res.json() if res.status_code == 200 else {"error": res.text}

        elif name == "get_option_chain":
            sym = args.get("symbol", "NIFTY 50")
            res = await client.get(f"{BACKEND_URL}/api/market/option-chain/{sym}")
            return res.json() if res.status_code == 200 else {"error": res.text}

        elif name == "execute_paper_order":
            res = await client.post(f"{BACKEND_URL}/api/paper/orders", json=args)
            return res.json() if res.status_code in (200, 201) else {"error": res.text}

        raise ValueError(f"Unknown tool: {name}")


def process_request(line: str) -> Optional[str]:
    try:
        req = json.loads(line.strip())
        req_id = req.get("id")
        method = req.get("method")

        if method == "initialize":
            return json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "apex-quant-lab-mcp", "version": "1.0.0"},
                },
            })
        elif method == "tools/list":
            return json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS},
            })
        elif method == "tools/call":
            params = req.get("params", {})
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            try:
                result_data = asyncio.run(handle_tool_call(tool_name, tool_args))
                return json.dumps({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(result_data, indent=2)}]
                    },
                })
            except Exception as e:
                return json.dumps({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Error executing {tool_name}: {e}"}],
                        "isError": True,
                    },
                })
        else:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            })
    except Exception as e:
        return json.dumps({
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32700, "message": f"Parse error: {e}"},
        })


def run_server():
    """Cross-platform line-buffered JSON-RPC runner."""
    for line in sys.stdin:
        if not line.strip():
            continue
        res_str = process_request(line)
        if res_str:
            sys.stdout.write(res_str + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_server()
