"""
MCP Client Integration for Flow-Based Agent

Provides MCP (Model Context Protocol) client capabilities to integrate with
external MCP servers for enhanced tool functionality.
"""

import json
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from rich.console import Console

console = Console()

class MCPClient:
    """MCP Client for connecting to external MCP servers"""
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.session = None
        self.connected = False
        self.available_tools = {}
        self.available_resources = {}
    
    async def connect(self):
        """Connect to the MCP server"""
        try:
            self.session = aiohttp.ClientSession()
            
            # Test connection
            async with self.session.get(f"{self.server_url}/health") as response:
                if response.status == 200:
                    self.connected = True
                    console.print(f"[green]Connected to MCP server: {self.server_url}[/green]")
                    
                    # Discover available tools and resources
                    await self.discover_capabilities()
                    return True
            
            console.print(f"[yellow]MCP server not responding at {self.server_url}[/yellow]")
            return False
            
        except Exception as e:
            console.print(f"[red]Failed to connect to MCP server: {str(e)}[/red]")
            return False
    
    async def discover_capabilities(self):
        """Discover available tools and resources from MCP server"""
        try:
            # Get tools list
            async with self.session.get(f"{self.server_url}/tools") as response:
                if response.status == 200:
                    tools_data = await response.json()
                    self.available_tools = {tool['name']: tool for tool in tools_data.get('tools', [])}
                    console.print(f"[green]Discovered {len(self.available_tools)} tools[/green]")
            
            # Get resources list
            async with self.session.get(f"{self.server_url}/resources") as response:
                if response.status == 200:
                    resources_data = await response.json()
                    self.available_resources = {res['name']: res for res in resources_data.get('resources', [])}
                    console.print(f"[green]Discovered {len(self.available_resources)} resources[/green]")
                    
        except Exception as e:
            console.print(f"[red]Failed to discover MCP capabilities: {str(e)}[/red]")
    
    async def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool"""
        if not self.connected:
            return {"error": "Not connected to MCP server", "success": False}
        
        if tool_name not in self.available_tools:
            return {"error": f"Tool not found: {tool_name}", "success": False}
        
        try:
            async with self.session.post(
                f"{self.server_url}/tools/{tool_name}",
                json=parameters,
                timeout=30
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {"success": True, "result": result}
                else:
                    error_text = await response.text()
                    return {"error": f"HTTP {response.status}: {error_text}", "success": False}
                    
        except asyncio.TimeoutError:
            return {"error": "Tool call timed out", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}
    
    async def get_resource(self, resource_name: str) -> Dict[str, Any]:
        """Get an MCP resource"""
        if not self.connected:
            return {"error": "Not connected to MCP server", "success": False}
        
        if resource_name not in self.available_resources:
            return {"error": f"Resource not found: {resource_name}", "success": False}
        
        try:
            async with self.session.get(
                f"{self.server_url}/resources/{resource_name}",
                timeout=30
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return {"success": True, "result": result}
                else:
                    error_text = await response.text()
                    return {"error": f"HTTP {response.status}: {error_text}", "success": False}
                    
        except asyncio.TimeoutError:
            return {"error": "Resource fetch timed out", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}
    
    async def close(self):
        """Close the MCP connection"""
        if self.session:
            await self.session.close()
            self.connected = False
            console.print("[blue]MCP connection closed[/blue]")

# Example MCP tool integrations
class MCPToolIntegrations:
    """Pre-configured MCP tool integrations for common use cases"""
    
    def __init__(self, mcp_client: MCPClient):
        self.client = mcp_client
    
    async def excel_operations(self, operation: str, file_path: str, **kwargs) -> Dict[str, Any]:
        """Perform Excel operations via MCP"""
        params = {
            "operation": operation,
            "file_path": file_path,
            **kwargs
        }
        return await self.client.call_tool("excel_operation", params)
    
    async def word_operations(self, operation: str, file_path: str, **kwargs) -> Dict[str, Any]:
        """Perform Word document operations via MCP"""
        params = {
            "operation": operation,
            "file_path": file_path,
            **kwargs
        }
        return await self.client.call_tool("word_operation", params)
    
    async def system_info(self) -> Dict[str, Any]:
        """Get system information via MCP"""
        return await self.client.call_tool("system_info", {})
    
    async def network_scan(self, target: str) -> Dict[str, Any]:
        """Perform network scan via MCP"""
        return await self.client.call_tool("network_scan", {"target": target})
    
    async def file_analysis(self, file_path: str) -> Dict[str, Any]:
        """Analyze file via MCP"""
        return await self.client.call_tool("file_analysis", {"file_path": file_path})

# Singleton MCP client instance
_mcp_client_instance = None

async def get_mcp_client(server_url: str = "http://localhost:8000") -> MCPClient:
    """Get or create MCP client instance"""
    global _mcp_client_instance
    
    if _mcp_client_instance is None:
        _mcp_client_instance = MCPClient(server_url)
        await _mcp_client_instance.connect()
    
    return _mcp_client_instance

async def close_mcp_client():
    """Close MCP client connection"""
    global _mcp_client_instance
    
    if _mcp_client_instance:
        await _mcp_client_instance.close()
        _mcp_client_instance = None
