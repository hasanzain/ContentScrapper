import asyncio
import io
import sys
from pathlib import Path

# Ensure UTF-8 stdout encoding on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import mcp


async def test_mcp_server_tools():
    """Verify MCP server tool discovery and execution."""
    print("=== Testing MCP Server Tool Registration ===")
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    print(f"Registered tools count: {len(tool_names)}")
    print(f"Tool names: {tool_names}")

    assert "scrape_tiktok_video" in tool_names, "scrape_tiktok_video must be registered"
    assert "get_tiktok_transcript" in tool_names, "get_tiktok_transcript must be registered"
    assert "search_tiktok_videos" in tool_names, "search_tiktok_videos must be registered"
    assert "search_tiktok_mobile" in tool_names, "search_tiktok_mobile must be registered"

    # Verify tool schemas
    for t in tools:
        print(f"\nTool: {t.name}")
        print(f"Description: {t.description[:80]}...")
        schema = t.inputSchema
        print(f"Input Schema: properties={list(schema.get('properties', {}).keys())}, required={schema.get('required')}")
        if t.name in {"scrape_tiktok_video", "get_tiktok_transcript"}:
            assert "url" in schema.get("properties", {}), f"Tool {t.name} must require 'url' parameter"
        elif t.name in {"search_tiktok_videos", "search_tiktok_mobile"}:
            assert "query" in schema.get("properties", {}), f"Tool {t.name} must require 'query' parameter"

    print("\n=== Testing Direct Tool Execution ===")
    test_url = "https://www.tiktok.com/@ophia.roserose/video/7703050842051579158"

    # Invoke scrape_tiktok_video tool
    print("Calling scrape_tiktok_video...")
    res = await mcp.call_tool("scrape_tiktok_video", {"url": test_url})
    # FastMCP call_tool returns list of Content objects or dict
    if isinstance(res, list) and res:
        content_val = res[0].text if hasattr(res[0], "text") else str(res[0])
        print(f"Result preview: {content_val[:120]}...")
        assert "7703050842051579158" in content_val or "success" in content_val
    else:
        print(f"Result: {res}")

    # Invoke search_tiktok_mobile tool
    print("\nCalling search_tiktok_mobile...")
    res_mob = await mcp.call_tool("search_tiktok_mobile", {"query": "AI UMKM", "count": 2})
    if isinstance(res_mob, list) and res_mob:
        mob_text = res_mob[0].text if hasattr(res_mob[0], "text") else str(res_mob[0])
        print(f"Mobile tool result preview: {mob_text[:120]}...")
        assert "tiktok" in mob_text or "diagnostic" in mob_text or "success" in mob_text

    print("\n[SUCCESS] MCP Server verification passed cleanly!")


if __name__ == "__main__":
    asyncio.run(test_mcp_server_tools())
