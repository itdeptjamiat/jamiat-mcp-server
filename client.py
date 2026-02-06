import asyncio
from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession

async def main():
    # Connect to our local MCP server
    async with streamable_http_client("http://localhost:8000/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            # Step 1: Initialize (handshake)
            await session.initialize()
            print("Connected to MCP server!")

            # Step 2: list available tools
            result = await session.list_tools()
            print("Available tools:")
            for tool in result.tools:
                print(f"  🔧 {tool.name}: {tool.description[:60]}...")
            print()   

            # Step 3: Call a tool
            result = await session.call_tool("get_project", {"project_id": "jamiat"})
            print("Jamiat Project Status:")
            print(result.content[0].text)
            print()

            # Step 4: Call another tool
            result = await session.call_tool("list_projects", {})
            print("All Projects Summary:")
            print(result.content[0].text)

            # Step 5: Call another tool
            result = await session.call_tool("get_total_cost", {})
            print("Total Hosting Cost:")
            print(result.content[0].text)

            # Step 6: Call another tool
            result = await session.call_tool("search_by_status", {"website_status": "live", "dashboard_status": "live"})
            print("Live Projects:")
            print(result.content[0].text)

if __name__ == "__main__":
    asyncio.run(main())