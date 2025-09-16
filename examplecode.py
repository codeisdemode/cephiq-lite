#!/usr/bin/env -S uv run --script

# /// script
# dependencies = [
#   "anthropic>=0.45.2",
#   "argparse>=1.4.0",
#   "rich>=13.7.0",
#   "pydantic>=2.0.0",
#   "openai>=1.0.0",
# ]
# ///

"""
Claudio Chat Agent - Interactive Conversational File Assistant

A chat-based version of the Claudio agent that allows users to interact conversationally
with file systems, directories, and content analysis. Powered by Claude Sonnet 4 for 
enhanced natural language understanding and response quality.

Features:
- Interactive chat interface
- Natural language file operations
- Directory analysis and comparison
- Content extraction and analysis
- Real-time file monitoring
- Markdown report generation
- Shell command execution
- Memory of conversation context
- Advanced intent recognition
- Powered by Claude Sonnet 4

Usage:
    uv run claudio_chat_agent.py
    uv run claudio_chat_agent.py --enable-memory --debug
    uv run claudio_chat_agent.py --output-dir "chat_workspace" --enable-torch
"""

import os
import sys
import argparse
import json
import traceback
import uuid
import hashlib
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.prompt import Prompt
from rich.markdown import Markdown
import anthropic

# Initialize console
console = Console()

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ChatMessage(BaseModel):
    role: str  # user, assistant, system
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ChatResponse(BaseModel):
    reply: str
    intent: str = "general"  # file_check, dir_analysis, file_compare, content_analysis, file_ops, shell_cmd, general
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.8
    suggestions: List[str] = Field(default_factory=list)
    status: str = "success"  # success, error, needs_clarification

# ============================================================================
# CHAT MEMORY SYSTEM
# ============================================================================

class ChatMemory:
    """Simple memory system for chat conversations"""
    
    def __init__(self, max_messages: int = 50):
        self.messages: List[ChatMessage] = []
        self.max_messages = max_messages
        self.session_id = str(uuid.uuid4())
    
    def add_message(self, role: str, content: str, metadata: Dict[str, Any] = None):
        """Add a message to chat history"""
        message = ChatMessage(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(message)
        
        # Keep memory manageable
        if len(self.messages) > self.max_messages:
            # Keep first system message and recent messages
            system_messages = [m for m in self.messages if m.role == "system"]
            recent_messages = self.messages[-(self.max_messages - len(system_messages)):]
            self.messages = system_messages + recent_messages
    
    def get_context(self, last_n: int = 10) -> str:
        """Get recent conversation context"""
        recent = self.messages[-last_n:] if self.messages else []
        context_parts = []
        
        for msg in recent:
            if msg.role == "user":
                context_parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                context_parts.append(f"Assistant: {msg.content}")
        
        return "\n".join(context_parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        return {
            "total_messages": len(self.messages),
            "session_id": self.session_id,
            "session_start": self.messages[0].timestamp if self.messages else "None",
            "last_message": self.messages[-1].timestamp if self.messages else "None"
        }

# ============================================================================
# TOOL RUNNER (Simplified from original)
# ============================================================================

class ChatToolRunner:
    """Tool runner for chat operations"""
    
    def __init__(self, output_dir: str = "chat_output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        self.tools = {
            "check_file": self.check_file,
            "check_directory": self.check_directory,
            "analyze_content": self.analyze_content,
            "compare_files": self.compare_files,
            "compare_directories": self.compare_directories,
            "create_report": self.create_report,
            "execute_command": self.execute_command,
            "list_files": self.list_files,
            "search_content": self.search_content
        }
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return results"""
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}", "success": False}
        
        try:
            return self.tools[tool_name](parameters)
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def check_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check if a file exists and get basic info"""
        path = params.get("path", "")
        
        if not path:
            return {"error": "No path provided", "success": False}
        
        try:
            if os.path.exists(path):
                stat = os.stat(path)
                return {
                    "success": True,
                    "exists": True,
                    "is_file": os.path.isfile(path),
                    "is_directory": os.path.isdir(path),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "path": os.path.abspath(path)
                }
            else:
                return {
                    "success": True,
                    "exists": False,
                    "path": path
                }
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def check_directory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze directory contents"""
        path = params.get("path", "")
        recursive = params.get("recursive", False)
        
        if not path:
            return {"error": "No path provided", "success": False}
        
        try:
            if not os.path.exists(path):
                return {"error": f"Directory {path} does not exist", "success": False}
            
            if not os.path.isdir(path):
                return {"error": f"{path} is not a directory", "success": False}
            
            files = []
            directories = []
            total_size = 0
            
            if recursive:
                for root, dirs, filenames in os.walk(path):
                    for filename in filenames:
                        filepath = os.path.join(root, filename)
                        try:
                            stat = os.stat(filepath)
                            files.append({
                                "name": filename,
                                "path": filepath,
                                "size": stat.st_size,
                                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                            })
                            total_size += stat.st_size
                        except:
                            continue
                    
                    for dirname in dirs:
                        dirpath = os.path.join(root, dirname)
                        directories.append({
                            "name": dirname,
                            "path": dirpath
                        })
            else:
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    try:
                        stat = os.stat(item_path)
                        if os.path.isfile(item_path):
                            files.append({
                                "name": item,
                                "path": item_path,
                                "size": stat.st_size,
                                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                            })
                            total_size += stat.st_size
                        elif os.path.isdir(item_path):
                            directories.append({
                                "name": item,
                                "path": item_path
                            })
                    except:
                        continue
            
            return {
                "success": True,
                "path": os.path.abspath(path),
                "files": files,
                "directories": directories,
                "file_count": len(files),
                "directory_count": len(directories),
                "total_size": total_size,
                "recursive": recursive
            }
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def analyze_content(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze file content"""
        path = params.get("path", "")
        max_size = params.get("max_size", 100000)  # 100KB limit
        
        if not path:
            return {"error": "No path provided", "success": False}
        
        try:
            if not os.path.exists(path):
                return {"error": f"File {path} does not exist", "success": False}
            
            if not os.path.isfile(path):
                return {"error": f"{path} is not a file", "success": False}
            
            stat = os.stat(path)
            if stat.st_size > max_size:
                return {
                    "error": f"File too large ({stat.st_size} bytes), max size is {max_size} bytes",
                    "success": False
                }
            
            # Try to read as text
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                lines = content.split('\n')
                words = content.split()
                
                return {
                    "success": True,
                    "path": os.path.abspath(path),
                    "size": stat.st_size,
                    "line_count": len(lines),
                    "word_count": len(words),
                    "char_count": len(content),
                    "content": content,
                    "file_type": "text",
                    "encoding": "utf-8"
                }
            except UnicodeDecodeError:
                return {
                    "success": True,
                    "path": os.path.abspath(path),
                    "size": stat.st_size,
                    "file_type": "binary",
                    "error": "Binary file - cannot analyze text content"
                }
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def compare_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Compare two files"""
        file1 = params.get("file1", "")
        file2 = params.get("file2", "")
        
        if not file1 or not file2:
            return {"error": "Both file1 and file2 paths required", "success": False}
        
        try:
            # Get file info
            info1 = self.analyze_content({"path": file1})
            info2 = self.analyze_content({"path": file2})
            
            if not info1["success"] or not info2["success"]:
                return {"error": "Could not read one or both files", "success": False}
            
            # Basic comparison
            same_size = info1["size"] == info2["size"]
            same_content = info1.get("content") == info2.get("content")
            
            differences = []
            if not same_size:
                differences.append(f"Different sizes: {info1['size']} vs {info2['size']} bytes")
            
            if info1.get("file_type") == "text" and info2.get("file_type") == "text":
                lines1 = info1["content"].split('\n')
                lines2 = info2["content"].split('\n')
                
                if len(lines1) != len(lines2):
                    differences.append(f"Different line counts: {len(lines1)} vs {len(lines2)}")
                
                # Find different lines (simple diff)
                max_lines = min(len(lines1), len(lines2))
                diff_lines = []
                for i in range(max_lines):
                    if lines1[i] != lines2[i]:
                        diff_lines.append({
                            "line": i + 1,
                            "file1": lines1[i],
                            "file2": lines2[i]
                        })
                        if len(diff_lines) >= 10:  # Limit diff output
                            break
                
                differences.extend([f"Line {d['line']}: '{d['file1']}' vs '{d['file2']}'" for d in diff_lines])
            
            return {
                "success": True,
                "file1": os.path.abspath(file1),
                "file2": os.path.abspath(file2),
                "identical": same_content,
                "same_size": same_size,
                "differences": differences,
                "file1_info": info1,
                "file2_info": info2
            }
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def compare_directories(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Compare two directories"""
        dir1 = params.get("dir1", "")
        dir2 = params.get("dir2", "")
        
        if not dir1 or not dir2:
            return {"error": "Both dir1 and dir2 paths required", "success": False}
        
        try:
            info1 = self.check_directory({"path": dir1, "recursive": True})
            info2 = self.check_directory({"path": dir2, "recursive": True})
            
            if not info1["success"] or not info2["success"]:
                return {"error": "Could not read one or both directories", "success": False}
            
            files1 = {f["name"]: f for f in info1["files"]}
            files2 = {f["name"]: f for f in info2["files"]}
            
            only_in_dir1 = set(files1.keys()) - set(files2.keys())
            only_in_dir2 = set(files2.keys()) - set(files1.keys())
            common_files = set(files1.keys()) & set(files2.keys())
            
            different_files = []
            for filename in common_files:
                if files1[filename]["size"] != files2[filename]["size"]:
                    different_files.append({
                        "name": filename,
                        "size1": files1[filename]["size"],
                        "size2": files2[filename]["size"]
                    })
            
            return {
                "success": True,
                "dir1": os.path.abspath(dir1),
                "dir2": os.path.abspath(dir2),
                "dir1_info": info1,
                "dir2_info": info2,
                "only_in_dir1": list(only_in_dir1),
                "only_in_dir2": list(only_in_dir2),
                "common_files": list(common_files),
                "different_files": different_files,
                "identical": len(only_in_dir1) == 0 and len(only_in_dir2) == 0 and len(different_files) == 0
            }
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def create_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a markdown report"""
        content = params.get("content", "")
        filename = params.get("filename", f"report_{int(time.time())}.md")
        title = params.get("title", "Analysis Report")
        
        if not content:
            return {"error": "No content provided for report", "success": False}
        
        try:
            report_path = os.path.join(self.output_dir, filename)
            
            # Create markdown report
            report_content = f"""# {title}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

{content}

---

*Report generated by Claudio Chat Agent*
"""
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            return {
                "success": True,
                "report_path": os.path.abspath(report_path),
                "filename": filename,
                "title": title,
                "size": len(report_content)
            }
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def execute_command(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a shell command"""
        command = params.get("command", "")
        
        if not command:
            return {"error": "No command provided", "success": False}
        
        try:
            import subprocess
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                "success": True,
                "command": command,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out after 30 seconds", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def list_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List files with optional filtering"""
        path = params.get("path", ".")
        pattern = params.get("pattern", "*")
        file_type = params.get("file_type", "all")  # all, files, directories
        
        try:
            import glob
            
            search_pattern = os.path.join(path, pattern)
            matches = glob.glob(search_pattern)
            
            results = []
            for match in matches:
                try:
                    stat = os.stat(match)
                    is_file = os.path.isfile(match)
                    is_dir = os.path.isdir(match)
                    
                    if file_type == "files" and not is_file:
                        continue
                    elif file_type == "directories" and not is_dir:
                        continue
                    
                    results.append({
                        "name": os.path.basename(match),
                        "path": os.path.abspath(match),
                        "is_file": is_file,
                        "is_directory": is_dir,
                        "size": stat.st_size if is_file else 0,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                except:
                    continue
            
            return {
                "success": True,
                "path": os.path.abspath(path),
                "pattern": pattern,
                "matches": results,
                "count": len(results)
            }
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def search_content(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search for content in files"""
        path = params.get("path", ".")
        search_term = params.get("search_term", "")
        file_pattern = params.get("file_pattern", "*.txt")
        
        if not search_term:
            return {"error": "No search term provided", "success": False}
        
        try:
            import glob
            
            search_pattern = os.path.join(path, file_pattern)
            files = glob.glob(search_pattern)
            
            results = []
            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')
                        
                        matches = []
                        for i, line in enumerate(lines, 1):
                            if search_term.lower() in line.lower():
                                matches.append({
                                    "line_number": i,
                                    "line_content": line.strip(),
                                    "match_position": line.lower().find(search_term.lower())
                                })
                        
                        if matches:
                            results.append({
                                "file": os.path.abspath(file_path),
                                "matches": matches,
                                "match_count": len(matches)
                            })
                except:
                    continue
            
            return {
                "success": True,
                "search_term": search_term,
                "path": os.path.abspath(path),
                "file_pattern": file_pattern,
                "files_searched": len(files),
                "files_with_matches": len(results),
                "results": results
            }
        except Exception as e:
            return {"error": str(e), "success": False} 

# ============================================================================
# CHAT AGENT CLASS
# ============================================================================

class ClaudioChatAgent:
    """Interactive chat agent for file operations and analysis"""
    
    def __init__(self, enable_memory: bool = True, debug: bool = False, output_dir: str = "chat_output"):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.memory = ChatMemory() if enable_memory else None
        self.tool_runner = ChatToolRunner(output_dir)
        self.debug = debug
        self.output_dir = output_dir
        self.session_active = False
        
        # Initialize system message
        if self.memory:
            self.memory.add_message("system", self._get_system_prompt())
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the chat agent"""
        return """You are Claudio, a helpful file assistant and chat agent. You can help users with:

FILE OPERATIONS:
- Check if files exist
- Analyze file and directory contents
- Compare files and directories
- Search for content in files
- Create reports and documentation
- Execute shell commands safely

CAPABILITIES:
- Natural language understanding
- File system operations
- Content analysis and comparison
- Report generation in Markdown
- Shell command execution
- Directory monitoring and analysis

RESPONSE FORMAT:
Always respond with helpful, clear information. When performing file operations, provide detailed results.
If you need to use tools, specify the tool and parameters clearly.

Be conversational, friendly, and thorough in your responses."""

    def _detect_intent(self, user_input: str) -> str:
        """Detect user intent from input"""
        input_lower = user_input.lower()
        
        # File existence checks
        if any(phrase in input_lower for phrase in ["file exist", "check file", "file there", "does file"]):
            return "file_check"
        
        # Directory analysis
        elif any(phrase in input_lower for phrase in ["analyze dir", "check directory", "list files", "directory content"]):
            return "dir_analysis"
        
        # File comparison
        elif any(phrase in input_lower for phrase in ["compare file", "diff file", "difference between"]):
            return "file_compare"
        
        # Content analysis
        elif any(phrase in input_lower for phrase in ["analyze content", "read file", "file content", "what's in"]):
            return "content_analysis"
        
        # Report creation
        elif any(phrase in input_lower for phrase in ["create report", "make report", "generate report", "save to md"]):
            return "create_report"
        
        # Shell commands
        elif any(phrase in input_lower for phrase in ["run command", "execute", "shell", "cmd"]):
            return "shell_cmd"
        
        # Search operations
        elif any(phrase in input_lower for phrase in ["search for", "find in files", "grep"]):
            return "search_content"
        
        else:
            return "general"
    
    def _extract_parameters(self, user_input: str, intent: str) -> Dict[str, Any]:
        """Extract parameters from user input based on intent"""
        params = {}
        
        if intent == "file_check":
            # Try to extract file path
            words = user_input.split()
            for i, word in enumerate(words):
                if "." in word or "/" in word or "\\" in word:
                    params["path"] = word
                    break
        
        elif intent == "dir_analysis":
            # Extract directory path
            words = user_input.split()
            for word in words:
                if "/" in word or "\\" in word or word in [".", ".."]:
                    params["path"] = word
                    break
            if "recursive" in user_input.lower():
                params["recursive"] = True
        
        elif intent == "file_compare":
            # Extract two file paths
            words = user_input.split()
            files = []
            for word in words:
                if "." in word and ("/" in word or "\\" in word or not " " in word):
                    files.append(word)
            if len(files) >= 2:
                params["file1"] = files[0]
                params["file2"] = files[1]
        
        elif intent == "content_analysis":
            # Extract file path
            words = user_input.split()
            for word in words:
                if "." in word or "/" in word or "\\" in word:
                    params["path"] = word
                    break
        
        elif intent == "shell_cmd":
            # Extract command after keywords
            input_lower = user_input.lower()
            for keyword in ["run", "execute", "command"]:
                if keyword in input_lower:
                    idx = input_lower.find(keyword) + len(keyword)
                    command = user_input[idx:].strip()
                    if command:
                        params["command"] = command
                    break
        
        elif intent == "search_content":
            # Extract search term and path
            words = user_input.split()
            if "for" in words:
                for_idx = words.index("for")
                if for_idx + 1 < len(words):
                    params["search_term"] = words[for_idx + 1]
            
            for word in words:
                if "/" in word or "\\" in word:
                    params["path"] = word
                    break
        
        return params
    
    def process_message(self, user_input: str) -> ChatResponse:
        """Process a user message and return response"""
        try:
            # Detect intent and extract parameters
            intent = self._detect_intent(user_input)
            
            if self.debug:
                console.print(f"[cyan]Debug: Detected intent: {intent}[/cyan]")
            
            # Build context for LLM
            context = ""
            if self.memory:
                context = self.memory.get_context(last_n=5)
            
            # Create prompt for LLM
            prompt = f"""
CONVERSATION CONTEXT:
{context}

USER INPUT: {user_input}

DETECTED INTENT: {intent}

Respond to the user helpfully. If you need to perform file operations, specify the tool and parameters.

Available tools:
- check_file: Check if a file exists
- check_directory: Analyze directory contents  
- analyze_content: Analyze file content
- compare_files: Compare two files
- compare_directories: Compare two directories
- create_report: Create a markdown report
- execute_command: Execute shell command
- list_files: List files with filtering
- search_content: Search for content in files

Respond with JSON:
{{
    "reply": "Your helpful response",
    "intent": "{intent}",
    "tool_calls": [
        {{"tool": "tool_name", "parameters": {{"param": "value"}}}}
    ],
    "confidence": 0.9,
    "suggestions": ["suggestion1", "suggestion2"],
    "status": "success"
}}
"""
            
            # Get LLM response
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Extract response content
            content = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    content += block.text
            
            if self.debug:
                console.print(Panel(
                    content[:500] + ("..." if len(content) > 500 else ""),
                    title="[cyan]Debug: LLM Response (truncated)[/cyan]"
                ))
            
            # Parse JSON response
            try:
                start = content.find('{')
                if start != -1:
                    brace_count = 0
                    end = -1
                    for i in range(start, len(content)):
                        if content[i] == '{':
                            brace_count += 1
                        elif content[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end = i + 1
                                break
                    
                    if end != -1:
                        json_str = content[start:end]
                        parsed = json.loads(json_str)
                        chat_response = ChatResponse(**parsed)
                        
                        # Execute any tool calls
                        tool_results = []
                        for tool_call in chat_response.tool_calls:
                            tool_name = tool_call.get("tool")
                            parameters = tool_call.get("parameters", {})
                            
                            if tool_name:
                                result = self.tool_runner.execute_tool(tool_name, parameters)
                                tool_results.append({
                                    "tool": tool_name,
                                    "parameters": parameters,
                                    "result": result
                                })
                                
                                if self.debug:
                                    console.print(f"[cyan]Debug: Executed {tool_name}: {result.get('success', False)}[/cyan]")
                        
                        # Update response with tool results
                        if tool_results:
                            # Add tool results to reply
                            tool_summary = self._format_tool_results(tool_results)
                            chat_response.reply += f"\n\n{tool_summary}"
                        
                        return chat_response
            except Exception as e:
                if self.debug:
                    console.print(f"[red]Debug: JSON parsing error: {e}[/red]")
            
            # Fallback response
            return ChatResponse(
                reply=content if content else "I'm sorry, I couldn't process that request.",
                intent=intent,
                status="error" if not content else "success"
            )
            
        except Exception as e:
            if self.debug:
                console.print(f"[red]Debug: Error processing message: {e}[/red]")
                console.print(traceback.format_exc())
            
            return ChatResponse(
                reply=f"I encountered an error: {str(e)}",
                intent="general",
                status="error"
            )
    
    def _format_tool_results(self, tool_results: List[Dict[str, Any]]) -> str:
        """Format tool results for display"""
        formatted = []
        
        for result_data in tool_results:
            tool = result_data["tool"]
            result = result_data["result"]
            
            if not result.get("success"):
                formatted.append(f"❌ {tool}: {result.get('error', 'Unknown error')}")
                continue
            
            if tool == "check_file":
                if result["exists"]:
                    formatted.append(f"✅ File exists: {result['path']}")
                    formatted.append(f"   Size: {result['size']} bytes")
                    formatted.append(f"   Modified: {result['modified']}")
                else:
                    formatted.append(f"❌ File does not exist: {result['path']}")
            
            elif tool == "check_directory":
                formatted.append(f"📁 Directory: {result['path']}")
                formatted.append(f"   Files: {result['file_count']}")
                formatted.append(f"   Subdirectories: {result['directory_count']}")
                formatted.append(f"   Total size: {result['total_size']} bytes")
            
            elif tool == "analyze_content":
                formatted.append(f"📄 Content analysis: {result['path']}")
                formatted.append(f"   Lines: {result.get('line_count', 'N/A')}")
                formatted.append(f"   Words: {result.get('word_count', 'N/A')}")
                formatted.append(f"   Characters: {result.get('char_count', 'N/A')}")
            
            elif tool == "compare_files":
                status = "✅ Identical" if result["identical"] else "❌ Different"
                formatted.append(f"{status}: {result['file1']} vs {result['file2']}")
                if result["differences"]:
                    formatted.append("   Differences:")
                    for diff in result["differences"][:5]:  # Limit output
                        formatted.append(f"     - {diff}")
            
            elif tool == "create_report":
                formatted.append(f"📝 Report created: {result['report_path']}")
                formatted.append(f"   Size: {result['size']} bytes")
            
            elif tool == "execute_command":
                formatted.append(f"💻 Command executed: {result['command']}")
                formatted.append(f"   Exit code: {result['exit_code']}")
                if result["stdout"]:
                    formatted.append(f"   Output: {result['stdout'][:200]}...")
            
            elif tool == "search_content":
                formatted.append(f"🔍 Search results for '{result['search_term']}':")
                formatted.append(f"   Files searched: {result['files_searched']}")
                formatted.append(f"   Files with matches: {result['files_with_matches']}")
                
                for file_result in result["results"][:3]:  # Limit output
                    formatted.append(f"   📄 {file_result['file']}: {file_result['match_count']} matches")
        
        return "\n".join(formatted)
    
    def start_chat(self):
        """Start the interactive chat session"""
        self.session_active = True
        
        # Welcome message
        console.print(Panel(
            """[bold blue]Welcome to Claudio Chat Agent! 🤖[/bold blue]

I can help you with file operations, directory analysis, content comparison, and more!

[bold green]Commands:[/bold green]
• /help - Show this help message
• /commands - List available operations
• /exit or /quit - Exit the chat
• /clear - Clear chat history
• /stats - Show session statistics

[bold yellow]Try asking things like:[/bold yellow]
• "Check if file.txt exists in the current directory"
• "Analyze the content of /path/to/directory"
• "Compare file1.txt and file2.txt"
• "Search for 'TODO' in all .py files"
• "Create a report comparing these two directories"

[italic]Type your message or command below...[/italic]""",
            title="🚀 Claudio Chat Agent",
            expand=False
        ))
        
        while self.session_active:
            try:
                # Get user input
                user_input = Prompt.ask("\n[bold green]You[/bold green]", default="").strip()
                
                if not user_input:
                    continue
                
                # Handle special commands
                if user_input.lower() in ["/exit", "/quit"]:
                    self._handle_exit()
                    break
                elif user_input.lower() == "/help":
                    self._show_help()
                    continue
                elif user_input.lower() == "/commands":
                    self._show_commands()
                    continue
                elif user_input.lower() == "/clear":
                    self._clear_history()
                    continue
                elif user_input.lower() == "/stats":
                    self._show_stats()
                    continue
                
                # Process the message
                if self.memory:
                    self.memory.add_message("user", user_input)
                
                console.print(f"\n[bold blue]Claudio[/bold blue]: [italic]Processing...[/italic]")
                
                response = self.process_message(user_input)
                
                # Display response
                self._display_response(response)
                
                # Store assistant response
                if self.memory:
                    self.memory.add_message("assistant", response.reply, {
                        "intent": response.intent,
                        "confidence": response.confidence
                    })
                
            except KeyboardInterrupt:
                self._handle_exit()
                break
            except Exception as e:
                console.print(f"\n[red]Error: {str(e)}[/red]")
                if self.debug:
                    console.print(traceback.format_exc())
    
    def _display_response(self, response: ChatResponse):
        """Display the agent's response"""
        # Main response
        console.print(f"\n[bold blue]Claudio[/bold blue]: {response.reply}")
        
        # Show suggestions if any
        if response.suggestions:
            console.print(f"\n[bold yellow]💡 Suggestions:[/bold yellow]")
            for suggestion in response.suggestions:
                console.print(f"  • {suggestion}")
        
        # Show confidence if debug mode
        if self.debug:
            console.print(f"\n[cyan]Debug: Intent={response.intent}, Confidence={response.confidence:.2f}[/cyan]")
    
    def _show_help(self):
        """Show help information"""
        console.print(Panel(
            """[bold]Claudio Chat Agent Help[/bold]

[bold green]File Operations:[/bold green]
• Check file existence: "Does file.txt exist?"
• Analyze content: "What's in the data.csv file?"
• Compare files: "Compare old.txt and new.txt"
• List directory: "Show me files in /path/to/dir"

[bold green]Analysis & Reports:[/bold green]
• Directory analysis: "Analyze the content of this directory"
• Create reports: "Create a report comparing dir1 and dir2"
• Search content: "Search for 'function' in all .py files"

[bold green]System Commands:[/bold green]
• Execute commands: "Run the command 'ls -la'"
• Check system info: "What files are in the current directory?"

[bold green]Chat Commands:[/bold green]
• /help - Show this help
• /commands - List all available operations
• /clear - Clear chat history
• /stats - Show session statistics
• /exit - Exit the chat""",
            title="📚 Help Guide"
        ))
    
    def _show_commands(self):
        """Show available commands"""
        table = Table(title="🛠️ Available Operations")
        table.add_column("Operation", style="cyan")
        table.add_column("Description", style="green")
        table.add_column("Example", style="yellow")
        
        table.add_row("File Check", "Check if files exist", "Does config.json exist?")
        table.add_row("Content Analysis", "Analyze file content", "Analyze the content of report.txt")
        table.add_row("Directory Analysis", "List and analyze directories", "Show files in ./src directory")
        table.add_row("File Comparison", "Compare two files", "Compare old.py and new.py")
        table.add_row("Directory Comparison", "Compare two directories", "Compare ./src and ./backup")
        table.add_row("Content Search", "Search for text in files", "Search for 'TODO' in *.py files")
        table.add_row("Report Creation", "Create markdown reports", "Create a report of file differences")
        table.add_row("Shell Commands", "Execute system commands", "Run 'git status' command")
        
        console.print(table)
    
    def _clear_history(self):
        """Clear chat history"""
        if self.memory:
            self.memory.messages = []
            self.memory.add_message("system", self._get_system_prompt())
            console.print("[green]✅ Chat history cleared![/green]")
    
    def _show_stats(self):
        """Show session statistics"""
        if self.memory:
            stats = self.memory.get_stats()
            console.print(Panel(
                f"[bold]Session Statistics[/bold]\n\n"
                f"Session ID: {stats['session_id'][:8]}...\n"
                f"Total Messages: {stats['total_messages']}\n"
                f"Session Start: {stats['session_start']}\n"
                f"Last Message: {stats['last_message']}\n"
                f"Output Directory: {os.path.abspath(self.output_dir)}\n"
                f"Debug Mode: {'Enabled' if self.debug else 'Disabled'}",
                title="📊 Statistics"
            ))
        else:
            console.print("[yellow]Memory is disabled - no statistics available[/yellow]")
    
    def _handle_exit(self):
        """Handle chat exit"""
        self.session_active = False
        console.print("\n[bold blue]Claudio[/bold blue]: Goodbye! Thanks for chatting! 👋")
        if self.memory:
            stats = self.memory.get_stats()
            console.print(f"[green]Session ended. {stats['total_messages']} messages exchanged.[/green]")

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Claudio Chat Agent - Interactive File Assistant"
    )
    parser.add_argument("--enable-memory", action="store_true", default=True, help="Enable chat memory (default: enabled)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--output-dir", type=str, default="chat_output", help="Output directory for reports and files")
    
    args = parser.parse_args()
    
    # Check API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        console.print("[red]Error: ANTHROPIC_API_KEY environment variable not set[/red]")
        sys.exit(1)
    
    try:
        # Create chat agent
        agent = ClaudioChatAgent(
            enable_memory=args.enable_memory,
            debug=args.debug,
            output_dir=args.output_dir
        )
        
        # Start chat session
        agent.start_chat()
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Chat interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Fatal error: {str(e)}[/red]")
        if args.debug:
            console.print(traceback.format_exc())

if __name__ == "__main__":
    main() 