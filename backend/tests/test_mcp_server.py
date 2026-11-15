"""
Automated Tests for APEX Quant Lab MCP Server Bridge (OpenMausBot Integration)
"""

import pytest
import json

from backend.app.mcp.apex_mcp_server import process_request, TOOLS


def test_mcp_server_initialize():
    req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    res = json.loads(process_request(req))
    assert res["id"] == 1
    assert res["result"]["serverInfo"]["name"] == "apex-quant-lab-mcp"
    assert "capabilities" in res["result"]


def test_mcp_server_tools_list():
    req = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    res = json.loads(process_request(req))
    assert res["id"] == 2
    tools = res["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "get_nifty_market_status" in tool_names
    assert "get_bot_telemetry" in tool_names
    assert "trigger_bot_scan" in tool_names
    assert "toggle_auto_trade" in tool_names
    assert "synthesize_trading_rules" in tool_names
    assert "get_option_chain" in tool_names
    assert "execute_paper_order" in tool_names


def test_mcp_server_method_not_found():
    req = json.dumps({"jsonrpc": "2.0", "id": 3, "method": "unknown/method"})
    res = json.loads(process_request(req))
    assert res["id"] == 3
    assert "error" in res
    assert res["error"]["code"] == -32601
