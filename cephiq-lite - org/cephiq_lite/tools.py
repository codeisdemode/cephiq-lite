"""
Tool Execution for Cephiq Lite

Supports:
- Built-in tools (file operations)
- MCP STDIO tools
- Parallel multi-tool execution
"""
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


class ToolExecutor:
    """Execute tools via built-in handlers or MCP"""

    def __init__(self, mcp_server_path: Optional[str] = None, timeout: int = 30):
        self.mcp_server_path = mcp_server_path
        self.timeout = timeout
        self.use_builtin = mcp_server_path == "builtin" or mcp_server_path is None

    def execute_single(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single tool

        Returns:
            {
                "success": bool,
                "tool": str,
                "result": Any,
                "error": Optional[str],
                "duration_ms": float
            }
        """
        start_time = time.perf_counter()

        try:
            # Normalize common aliases/synonyms
            tool = self._normalize_tool(tool)
            if self.use_builtin:
                result = self._execute_builtin(tool, arguments)
            else:
                result = self._execute_mcp(tool, arguments)

            duration = (time.perf_counter() - start_time) * 1000

            return {
                "success": result.get("success", True),
                "tool": tool,
                "result": result,
                "error": result.get("error"),
                "duration_ms": round(duration, 1)
            }

        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return {
                "success": False,
                "tool": tool,
                "result": None,
                "error": str(e),
                "duration_ms": round(duration, 1)
            }

    def execute_batch(
        self,
        tools: List[Dict[str, Any]],
        parallel: bool = True
    ) -> Dict[str, Any]:
        """
        Execute multiple tools (parallel or sequential)

        Args:
            tools: List of {"tool_id": str, "tool": str, "arguments": dict}
            parallel: Execute in parallel (True) or sequential (False)

        Returns:
            {
                "_multi_tool": True,
                "count": int,
                "all_success": bool,
                "results": {tool_id: result_dict}
            }
        """
        results = {}

        if parallel:
            # Parallel execution with ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_tool_id = {
                    executor.submit(
                        self.execute_single,
                        tool_item["tool"],
                        tool_item["arguments"]
                    ): tool_item["tool_id"]
                    for tool_item in tools
                }

                for future in as_completed(future_to_tool_id):
                    tool_id = future_to_tool_id[future]
                    results[tool_id] = future.result()
        else:
            # Sequential execution
            for tool_item in tools:
                tool_id = tool_item["tool_id"]
                result = self.execute_single(tool_item["tool"], tool_item["arguments"])
                results[tool_id] = result

        return {
            "_multi_tool": True,
            "count": len(results),
            "all_success": all(r["success"] for r in results.values()),
            "results": results
        }

    def _execute_builtin(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute built-in tool"""

        # File operations
        if tool == "create_file":
            return self._builtin_create_file(arguments)
        elif tool == "read_file":
            return self._builtin_read_file(arguments)
        elif tool == "edit_file":
            return self._builtin_edit_file(arguments)
        elif tool == "delete_file":
            return self._builtin_delete_file(arguments)
        elif tool == "list_files":
            return self._builtin_list_files(arguments)
        elif tool == "create_directory":
            return self._builtin_create_directory(arguments)
        elif tool == "directory_tree":
            # Use corrected implementation
            return self._builtin_directory_tree2(arguments)
        elif tool == "get_cwd":
            return self._builtin_get_cwd(arguments)
        else:
            return {"success": False, "error": f"Unknown built-in tool: {tool}"}

    def _normalize_tool(self, tool: str) -> str:
        """Map common aliases to supported built-ins."""
        aliases = {
            "pwd": "get_cwd",
            "cwd": "get_cwd",
            "get_working_directory": "get_cwd",
            "current_working_directory": "get_cwd",
            "working_directory": "get_cwd",
        }
        return aliases.get(tool, tool)

    def _builtin_get_cwd(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Return current working directory"""
        try:
            return {"success": True, "cwd": str(Path.cwd())}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _builtin_directory_tree2(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Show directory tree (clean output)"""
        path = Path(args.get("path", "."))
        try:
            max_depth = int(args.get("max_depth", 3))
        except Exception:
            max_depth = 3

        def build_tree(p: Path, depth: int = 0) -> List[str]:
            if depth > max_depth:
                return []

            lines: List[str] = []
            try:
                items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                for item in items:
                    indent = "  " * depth
                    prefix = "[D] " if item.is_dir() else "[F] "
                    lines.append(f"{indent}{prefix}{item.name}")
                    if item.is_dir():
                        lines.extend(build_tree(item, depth + 1))
            except PermissionError:
                pass
            return lines

        try:
            header = f"{(path.name or str(path))}"
            tree_lines = [header] + build_tree(path)
            tree = "\n".join(tree_lines)
            return {"success": True, "path": str(path), "tree": tree}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_mcp(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool via MCP STDIO"""

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool,
                "arguments": arguments
            }
        }

        try:
            result = subprocess.run(
                [self.mcp_server_path],
                input=json.dumps(request),
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"MCP server error: {result.stderr}"
                }

            response = json.loads(result.stdout)

            if "error" in response:
                return {
                    "success": False,
                    "error": response["error"].get("message", "Unknown MCP error")
                }

            return {
                "success": True,
                **response.get("result", {})
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Tool execution timeout ({self.timeout}s)"}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid MCP response: {e}"}
        except Exception as e:
            return {"success": False, "error": f"MCP execution failed: {e}"}

    # Built-in tool implementations

    def _builtin_create_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a file"""
        path = Path(args.get("path", ""))
        content = args.get("content", "")

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

            return {
                "success": True,
                "path": str(path),
                "size": len(content),
                "message": f"Created {path} ({len(content)} bytes)"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _builtin_read_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Read a file"""
        path = Path(args.get("path", ""))

        try:
            content = path.read_text(encoding="utf-8")

            return {
                "success": True,
                "path": str(path),
                "content": content,
                "size": len(content)
            }
        except FileNotFoundError:
            return {"success": False, "error": f"File not found: {path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _builtin_edit_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Edit file by replacing text"""
        path = Path(args.get("path", ""))
        old_string = args.get("old_string", "")
        new_string = args.get("new_string", "")

        try:
            content = path.read_text(encoding="utf-8")

            if old_string not in content:
                return {
                    "success": False,
                    "error": f"String not found: {old_string[:50]}..."
                }

            new_content = content.replace(old_string, new_string)
            replacements = content.count(old_string)

            path.write_text(new_content, encoding="utf-8")

            return {
                "success": True,
                "path": str(path),
                "replacements": replacements,
                "message": f"Replaced {replacements} occurrence(s)"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _builtin_delete_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a file"""
        path = Path(args.get("path", ""))

        try:
            path.unlink()
            return {
                "success": True,
                "path": str(path),
                "message": f"Deleted {path}"
            }
        except FileNotFoundError:
            return {"success": False, "error": f"File not found: {path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _builtin_list_files(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List files in directory"""
        path = Path(args.get("path", "."))

        try:
            files = [str(f.relative_to(path)) for f in path.iterdir()]

            return {
                "success": True,
                "path": str(path),
                "files": files,
                "count": len(files)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _builtin_create_directory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create directory"""
        path = Path(args.get("path", ""))

        try:
            path.mkdir(parents=True, exist_ok=True)
            return {
                "success": True,
                "path": str(path),
                "message": f"Created directory {path}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _builtin_directory_tree(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Show directory tree"""
        path = Path(args.get("path", "."))
        max_depth = args.get("max_depth", 3)

        def build_tree(p: Path, depth: int = 0) -> List[str]:
            if depth > max_depth:
                return []

            lines = []
            try:
                items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name))

                for item in items:
                    indent = "  " * depth
                    prefix = "📁 " if item.is_dir() else "📄 "
                    lines.append(f"{indent}{prefix}{item.name}")

                    if item.is_dir():
                        lines.extend(build_tree(item, depth + 1))
            except PermissionError:
                pass

            return lines

        try:
            tree_lines = [f"📁 {path.name or path}"] + build_tree(path)
            tree = "\n".join(tree_lines)

            return {
                "success": True,
                "path": str(path),
                "tree": tree
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # Self-test
    executor = ToolExecutor(mcp_server_path="builtin")

    # Test single tool
    print("Test 1: Create file")
    result = executor.execute_single("create_file", {
        "path": "test_cephiq.txt",
        "content": "Hello from Cephiq Lite!"
    })
    print(f"  Success: {result['success']}")
    print(f"  Result: {result['result']}")

    # Test multi-tool (parallel)
    print("\nTest 2: Multi-tool (parallel)")
    result = executor.execute_batch([
        {"tool_id": "file1", "tool": "create_file", "arguments": {"path": "a.txt", "content": "File A"}},
        {"tool_id": "file2", "tool": "create_file", "arguments": {"path": "b.txt", "content": "File B"}},
        {"tool_id": "file3", "tool": "create_file", "arguments": {"path": "c.txt", "content": "File C"}}
    ])
    print(f"  All success: {result['all_success']}")
    print(f"  Count: {result['count']}")
    for tool_id, res in result['results'].items():
        print(f"    {tool_id}: {res['success']} ({res['duration_ms']}ms)")

    # Cleanup
    Path("test_cephiq.txt").unlink(missing_ok=True)
    Path("a.txt").unlink(missing_ok=True)
    Path("b.txt").unlink(missing_ok=True)
    Path("c.txt").unlink(missing_ok=True)

    print("\nTests complete!")
