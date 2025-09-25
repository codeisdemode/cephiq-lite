#!/usr/bin/env python
"""
Hybrid PowerShell + Python MCP Server (FastMCP)

Transports:
- stdio (default): speaks MCP over stdin/stdout. IMPORTANT: Do not print to stdout in this mode.
- sse: runs an HTTP SSE server using FastMCP settings (host/port).

Notes:
- For stdio, avoid printing to stdout before/during the session; use logging or stderr.
- For sse, FastMCP will serve SSE at settings.sse_path (default /sse).
"""

import subprocess
import re
import logging
import base64
import os
import io
import contextlib
import json
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

# Ensure stdout is properly configured for stdio transport
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

# Configure logging - force all logs to stderr to avoid stdout pollution
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('powershell_python_mcp.log'),
        logging.StreamHandler(sys.stderr)  # Also log to stderr
    ]
)

logger = logging.getLogger("hybrid-mcp")
# Create FastMCP; host/port can be overridden when using SSE via settings
mcp = FastMCP("Hybrid MCP Server")

# --- PowerShell Utilities ---

class CommandOutput(BaseModel):
    command: str
    output: str
    error: Optional[str] = None

def sanitize_path(path: str) -> str:
    return path.strip()

def execute_powershell(command: str) -> CommandOutput:
    logger.info(f"Executing PowerShell: {command}")
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True)
        return CommandOutput(
            command=command,
            output=result.stdout.strip(),
            error=None if result.returncode == 0 else result.stderr.strip()
        )
    except Exception as e:
        return CommandOutput(command=command, output="", error=str(e))

# --- PowerShell Tools ---

@mcp.tool()
def get_files(path: str = ".") -> Dict[str, Any]:
    """
    List files/directories at a given path (PowerShell-based).
    Returns JSON with 'items' array and 'path'.
    """
    safe_path = sanitize_path(path)
    ps_cmd = f'Get-ChildItem "{safe_path}" | ConvertTo-Json -Depth 1'
    result = execute_powershell(ps_cmd)
    if result.error:
        return {"items": [], "path": safe_path, "error": result.error}

    items_list = []
    try:
        # Handle empty directory case (PowerShell returns empty string)
        if not result.output or result.output.strip() == "":
            raw = []
        else:
            raw = json.loads(result.output)
            if not isinstance(raw, list):
                raw = [raw]
        for item in raw:
            # Check if it's a directory using the Attributes field (16 = Directory, 32 = Archive/File)
            attributes = item.get("Attributes", 0)
            item_type = "directory" if attributes == 16 else "file"
            items_list.append({
                "name": item.get("Name", ""),
                "type": item_type,
                "size": item.get("Length"),
                "last_write_time": item.get("LastWriteTime")
            })
    except Exception as e:
        logger.error(f"Failed to parse file list JSON: {e}")
        return {"items": [], "path": safe_path, "error": str(e)}

    return {"items": items_list, "path": safe_path}

@mcp.tool()
def read_file(path: str) -> Dict[str, Any]:
    """
    Read entire file contents via PowerShell: Get-Content
    """
    cmd_out = execute_powershell(f'Get-Content -Path "{sanitize_path(path)}"')
    return cmd_out.dict()

@mcp.tool()
def create_file(path: str, content: str = "") -> Dict[str, Any]:
    """
    Create a new file (overwrite if exists), optionally write content.
    """
    safe_path = sanitize_path(path)
    result = execute_powershell(f'New-Item -ItemType File -Path "{safe_path}" -Force')
    if content:
        escaped_content = content.replace('"', '`"')
        write_result = execute_powershell(f'Set-Content -Path "{safe_path}" -Value "{escaped_content}"')
        return write_result.dict()
    return result.dict()

@mcp.tool()
def create_directory(path: str) -> Dict[str, Any]:
    """
    Create a new directory, recursively if needed
    """
    cmd_out = execute_powershell(f'New-Item -ItemType Directory -Path "{sanitize_path(path)}" -Force')
    return cmd_out.dict()

@mcp.tool()
def delete_item(path: str, recurse: bool = False, force: bool = False) -> Dict[str, Any]:
    cmd = f'Remove-Item -Path "{sanitize_path(path)}"'
    if recurse:
        cmd += " -Recurse"
    if force:
        cmd += " -Force"
    return execute_powershell(cmd).dict()

@mcp.tool()
def copy_item(source: str, destination: str) -> Dict[str, Any]:
    cmd_out = execute_powershell(f'Copy-Item -Path "{source}" -Destination "{destination}"')
    return cmd_out.dict()

@mcp.tool()
def move_item(source: str, destination: str) -> Dict[str, Any]:
    cmd_out = execute_powershell(f'Move-Item -Path "{source}" -Destination "{destination}"')
    return cmd_out.dict()

@mcp.tool()
def get_processes(name: str = "") -> Dict[str, Any]:
    cmd = f'Get-Process {"-Name " + name if name else ""}'
    return execute_powershell(cmd).dict()

@mcp.tool()
def get_services(name: str = "") -> Dict[str, Any]:
    cmd = f'Get-Service {"-Name " + name if name else ""}'
    return execute_powershell(cmd).dict()

@mcp.tool()
def get_current_date() -> Dict[str, Any]:
    return execute_powershell("Get-Date").dict()

@mcp.tool()
def get_current_location() -> Dict[str, Any]:
    return execute_powershell("Get-Location").dict()

@mcp.tool()
def change_directory(path: str) -> Dict[str, Any]:
    return execute_powershell(f'Set-Location -Path "{sanitize_path(path)}"').dict()

@mcp.tool(name="powershell")
@mcp.tool(name="execute_powershell")
@mcp.tool(name="shell")
@mcp.tool(name="bash")
def execute_passthrough(code: Optional[str] = None, command: Optional[str] = None) -> Dict[str, Any]:
    """
    Accept code/command from LLM, pass directly to PowerShell
    """
    cmd = code or command
    if not cmd:
        return {"command": "", "output": "", "error": "Missing 'code' or 'command'"}
    return execute_powershell(cmd).dict()

# Resource: system info
@mcp.resource("system://info")
def get_system_info() -> Dict[str, Any]:
    return {
        "powershell_version": execute_powershell("$PSVersionTable | ConvertTo-Json").output,
        "os_info": execute_powershell("Get-ComputerInfo -Property CsManufacturer,CsModel,OsName,OsVersion | ConvertTo-Json").output,
        "mcp_server": "Hybrid MCP Server v1.0"
    }

# --- Python Tools ---

@mcp.tool()
def python(code: str) -> Dict[str, Any]:
    """
    Execute arbitrary Python code in this server process
    """
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            exec(code, globals())
        return {"output": output.getvalue()}
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def python_eval(expr: str) -> Dict[str, Any]:
    try:
        result = eval(expr, globals())
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}

# --- Partial File I/O Tools (READ/WRITE BLOCK) ---

@mcp.tool()
def read_block(path: str, start_line: int, num_lines: int) -> Dict[str, Any]:
    """
    Read a partial block of lines from 'path':
    - start_line: 0-based index
    - num_lines: how many lines to read
    Returns { "content": "<text>", "error": ... }
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        end_line = start_line + num_lines
        chunk = lines[start_line:end_line]
        return {"content": "".join(chunk), "error": None}
    except Exception as e:
        return {"content": "", "error": str(e)}

@mcp.tool()
def write_block(path: str, start_line: int, text: str) -> Dict[str, Any]:
    """
    Write (or overwrite) lines in 'path' starting at line index 'start_line'.
    'text' can contain newlines. If the file is shorter, we append blank lines as needed.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        block_lines = text.splitlines(True)  # keep newlines
        # Extend file if start_line is beyond current length
        if start_line > len(lines):
            lines += ["\n"] * (start_line - len(lines))

        # Overwrite or append lines
        for i, bline in enumerate(block_lines):
            idx = start_line + i
            if idx < len(lines):
                lines[idx] = bline
            else:
                lines.append(bline)

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        return {"success": True, "error": None}
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- PDF Extraction Tools ---

@mcp.tool()
def extract_pdf_text(path: str, use_ocr: bool = False) -> Dict[str, Any]:
    """
    Extract text from PDF file using PyPDF2 with fallback to pdfplumber for better extraction

    Args:
        path: Path to PDF file
        use_ocr: Whether to attempt OCR if text extraction fails (requires additional setup)

    Returns:
        Dictionary with extracted text, metadata, and extraction method used
    """
    import os
    from pathlib import Path

    try:
        # Validate file exists
        pdf_path = Path(path)
        if not pdf_path.exists():
            return {"error": f"PDF file not found: {path}"}

        if pdf_path.suffix.lower() != '.pdf':
            return {"error": f"File is not a PDF: {path}"}

        # Try pdfplumber first (better text extraction)
        try:
            import pdfplumber

            extracted_text = []
            metadata = {}
            has_text = False

            with pdfplumber.open(pdf_path) as pdf:
                metadata = {
                    "pages": len(pdf.pages),
                    "author": pdf.metadata.get("Author"),
                    "creator": pdf.metadata.get("Creator"),
                    "producer": pdf.metadata.get("Producer"),
                    "subject": pdf.metadata.get("Subject"),
                    "title": pdf.metadata.get("Title"),
                    "creation_date": pdf.metadata.get("CreationDate"),
                    "modification_date": pdf.metadata.get("ModDate")
                }

                for page_num, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        extracted_text.append(f"--- Page {page_num} ---\n{page_text}")
                        has_text = True
                    else:
                        extracted_text.append(f"--- Page {page_num} ---\n[No text found - likely scanned PDF]")

            full_text = "\n\n".join(extracted_text)

            # If no text found and OCR is requested, try OCR
            if not has_text and use_ocr:
                logger.info("No text found with pdfplumber, attempting OCR")
                ocr_result = _attempt_ocr_extraction(pdf_path)
                if ocr_result.get("success"):
                    return ocr_result

            return {
                "success": True,
                "text": full_text,
                "metadata": metadata,
                "method": "pdfplumber",
                "pages_extracted": len(extracted_text),
                "has_text": has_text,
                "ocr_available": use_ocr and not has_text
            }

        except Exception as pdfplumber_error:
            logger.warning(f"pdfplumber failed: {pdfplumber_error}, trying PyPDF2")

            # Fallback to PyPDF2
            try:
                import PyPDF2

                extracted_text = []
                has_text = False

                with open(pdf_path, 'rb') as pdf_file:
                    pdf_reader = PyPDF2.PdfReader(pdf_file)

                    metadata = {
                        "pages": len(pdf_reader.pages),
                        "author": pdf_reader.metadata.get("/Author") if pdf_reader.metadata else None,
                        "creator": pdf_reader.metadata.get("/Creator") if pdf_reader.metadata else None,
                        "producer": pdf_reader.metadata.get("/Producer") if pdf_reader.metadata else None,
                        "subject": pdf_reader.metadata.get("/Subject") if pdf_reader.metadata else None,
                        "title": pdf_reader.metadata.get("/Title") if pdf_reader.metadata else None
                    }

                    for page_num, page in enumerate(pdf_reader.pages, 1):
                        page_text = page.extract_text() or ""
                        if page_text.strip():
                            extracted_text.append(f"--- Page {page_num} ---\n{page_text}")
                            has_text = True
                        else:
                            extracted_text.append(f"--- Page {page_num} ---\n[No text found - likely scanned PDF]")

                full_text = "\n\n".join(extracted_text)

                # If no text found and OCR is requested, try OCR
                if not has_text and use_ocr:
                    logger.info("No text found with PyPDF2, attempting OCR")
                    ocr_result = _attempt_ocr_extraction(pdf_path)
                    if ocr_result.get("success"):
                        return ocr_result

                return {
                    "success": True,
                    "text": full_text,
                    "metadata": metadata,
                    "method": "PyPDF2",
                    "pages_extracted": len(extracted_text),
                    "has_text": has_text,
                    "ocr_available": use_ocr and not has_text
                }

            except Exception as pypdf2_error:
                logger.error(f"PyPDF2 also failed: {pypdf2_error}")
                return {
                    "error": f"PDF text extraction failed with both methods: {pypdf2_error}",
                    "pdfplumber_error": str(pdfplumber_error),
                    "pypdf2_error": str(pypdf2_error)
                }

    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return {"error": f"PDF extraction failed: {e}"}

def _attempt_ocr_extraction(pdf_path: Path) -> Dict[str, Any]:
    """Attempt OCR extraction for scanned PDFs"""
    try:
        # Check if OCR libraries are available
        try:
            import pytesseract
            from pdf2image import convert_from_path
        except ImportError:
            return {
                "error": "OCR libraries not available. Install pytesseract and pdf2image for OCR support.",
                "suggestion": "Run: pip install pytesseract pdf2image"
            }

        # Convert PDF to images
        images = convert_from_path(str(pdf_path))

        extracted_text = []

        for page_num, image in enumerate(images, 1):
            # Perform OCR on each page
            page_text = pytesseract.image_to_string(image)
            if page_text.strip():
                extracted_text.append(f"--- Page {page_num} (OCR) ---\n{page_text}")
            else:
                extracted_text.append(f"--- Page {page_num} (OCR) ---\n[No text recognized]")

        full_text = "\n\n".join(extracted_text)

        return {
            "success": True,
            "text": full_text,
            "method": "OCR (pytesseract)",
            "pages_extracted": len(extracted_text),
            "has_text": any(text.strip() for text in extracted_text)
        }

    except Exception as ocr_error:
        logger.error(f"OCR extraction failed: {ocr_error}")
        return {
            "error": f"OCR extraction failed: {ocr_error}",
            "suggestion": "Ensure tesseract-ocr is installed on your system"
        }

@mcp.tool()
def format_markdown_report(path: str, improvements: str = "enhanced readability and visual hierarchy") -> Dict[str, Any]:
    """
    Format and improve markdown report layout with better visual hierarchy and readability

    Args:
        path: Path to markdown file
        improvements: Description of formatting improvements to apply

    Returns:
        Dictionary with formatting results and improvements made
    """
    import os
    from pathlib import Path

    try:
        # Validate file exists
        md_path = Path(path)
        if not md_path.exists():
            return {"error": f"Markdown file not found: {path}"}

        if md_path.suffix.lower() not in ['.md', '.markdown']:
            return {"error": f"File is not a markdown file: {path}"}

        # Read the current content
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Analyze current formatting
        improvements_made = []
        formatted_content = content

        # Apply formatting improvements
        if "enhanced readability and visual hierarchy" in improvements.lower():
            # 1. Improve header consistency
            formatted_content = _improve_headers(formatted_content)
            improvements_made.append("Improved header consistency")

            # 2. Enhance table formatting
            formatted_content = _enhance_tables(formatted_content)
            improvements_made.append("Enhanced table formatting")

            # 3. Optimize spacing and structure
            formatted_content = _optimize_spacing(formatted_content)
            improvements_made.append("Optimized spacing and structure")

            # 4. Add visual elements
            formatted_content = _add_visual_elements(formatted_content)
            improvements_made.append("Added visual elements")

            # 5. Improve code blocks
            formatted_content = _improve_code_blocks(formatted_content)
            improvements_made.append("Improved code blocks")

        # Create backup and write improved version
        backup_path = md_path.with_suffix('.md.backup')
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)

        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(formatted_content)

        return {
            "success": True,
            "improvements": improvements_made,
            "backup_created": str(backup_path),
            "original_length": len(content),
            "formatted_length": len(formatted_content),
            "improvement_summary": f"Applied {len(improvements_made)} formatting improvements"
        }

    except Exception as e:
        logger.error(f"Markdown formatting failed: {e}")
        return {"error": f"Markdown formatting failed: {e}"}

def _improve_headers(content: str) -> str:
    """Improve header consistency and hierarchy"""
    lines = content.split('\n')
    improved_lines = []

    for line in lines:
        # Ensure consistent header spacing
        if line.startswith('#'):
            # Add spacing after headers
            improved_lines.append(line)
            if not line.startswith('######'):  # Don't add space after smallest headers
                improved_lines.append('')
        else:
            improved_lines.append(line)

    return '\n'.join(improved_lines)

def _enhance_tables(content: str) -> str:
    """Enhance table formatting and readability"""
    lines = content.split('\n')
    improved_lines = []
    in_table = False

    for i, line in enumerate(lines):
        if '|' in line and ('---' in line or i > 0 and '|' in lines[i-1]):
            if not in_table:
                improved_lines.append('')  # Add space before table
                in_table = True
            improved_lines.append(line)
            if i < len(lines)-1 and '|' not in lines[i+1]:
                improved_lines.append('')  # Add space after table
                in_table = False
        else:
            improved_lines.append(line)

    return '\n'.join(improved_lines)

def _optimize_spacing(content: str) -> str:
    """Optimize spacing and structure for better readability"""
    lines = content.split('\n')
    improved_lines = []

    for i, line in enumerate(lines):
        improved_lines.append(line)
        # Add spacing after major sections
        if (line.startswith('## ') and not line.startswith('###')) or line.strip() == '---':
            if i < len(lines)-1 and lines[i+1].strip() != '':
                improved_lines.append('')

    return '\n'.join(improved_lines)

def _add_visual_elements(content: str) -> str:
    """Add visual elements like progress bars and status indicators"""
    # Add progress bar for compliance scores if not present
    if 'Compliance Score:' in content and '```' not in content.split('Compliance Score:')[1][:200]:
        # Find compliance score line and add visual progress bar
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'Compliance Score:' in line and '%' in line:
                # Extract percentage
                import re
                match = re.search(r'(\d+)%', line)
                if match:
                    percentage = int(match.group(1))
                    # Add visual progress bar
                    bar_length = 50
                    filled = int(percentage / 100 * bar_length)
                    empty = bar_length - filled
                    progress_bar = f"```\n{'█' * filled}{'░' * empty}\n```"
                    lines.insert(i + 1, progress_bar)
                    lines.insert(i + 2, f"*{percentage} out of 100*")
                    lines.insert(i + 3, '')
                    break
        content = '\n'.join(lines)

    return content

def _improve_code_blocks(content: str) -> str:
    """Improve code block formatting and syntax highlighting"""
    # Ensure code blocks have proper spacing
    lines = content.split('\n')
    improved_lines = []
    in_code_block = False

    for i, line in enumerate(lines):
        if line.strip().startswith('```'):
            if not in_code_block:
                improved_lines.append('')  # Add space before code block
                in_code_block = True
            else:
                in_code_block = False
                improved_lines.append(line)
                improved_lines.append('')  # Add space after code block
                continue
        improved_lines.append(line)

    return '\n'.join(improved_lines)

@mcp.tool()
def extract_pdf_metadata(path: str) -> Dict[str, Any]:
    """
    Extract metadata from PDF file without extracting full text
    """
    import os
    from pathlib import Path

    try:
        pdf_path = Path(path)
        if not pdf_path.exists():
            return {"error": f"PDF file not found: {path}"}

        if pdf_path.suffix.lower() != '.pdf':
            return {"error": f"File is not a PDF: {path}"}

        # Try pdfplumber first
        try:
            import pdfplumber

            with pdfplumber.open(pdf_path) as pdf:
                metadata = {
                    "pages": len(pdf.pages),
                    "author": pdf.metadata.get("Author"),
                    "creator": pdf.metadata.get("Creator"),
                    "producer": pdf.metadata.get("Producer"),
                    "subject": pdf.metadata.get("Subject"),
                    "title": pdf.metadata.get("Title"),
                    "creation_date": pdf.metadata.get("CreationDate"),
                    "modification_date": pdf.metadata.get("ModDate"),
                    "method": "pdfplumber"
                }

                return {"success": True, "metadata": metadata}

        except Exception:
            # Fallback to PyPDF2
            try:
                import PyPDF2

                with open(pdf_path, 'rb') as pdf_file:
                    pdf_reader = PyPDF2.PdfReader(pdf_file)

                    metadata = {
                        "pages": len(pdf_reader.pages),
                        "author": pdf_reader.metadata.get("/Author") if pdf_reader.metadata else None,
                        "creator": pdf_reader.metadata.get("/Creator") if pdf_reader.metadata else None,
                        "producer": pdf_reader.metadata.get("/Producer") if pdf_reader.metadata else None,
                        "subject": pdf_reader.metadata.get("/Subject") if pdf_reader.metadata else None,
                        "title": pdf_reader.metadata.get("/Title") if pdf_reader.metadata else None,
                        "method": "PyPDF2"
                    }

                    return {"success": True, "metadata": metadata}

            except Exception as e:
                return {"error": f"PDF metadata extraction failed: {e}"}

    except Exception as e:
        return {"error": f"PDF metadata extraction failed: {e}"}

# --- Workflow System ---

def load_workflows_from_flows_dir(flow_dir: str = "flows") -> Dict[str, Any]:
    """Load workflow definitions from JSON files in the flows directory"""
    workflows = {}
    flow_path = Path(flow_dir)

    if not flow_path.exists():
        logger.warning(f"Flows directory '{flow_dir}' does not exist")
        return workflows

    for flow_file in flow_path.glob("*.json"):
        try:
            with open(flow_file, 'r', encoding='utf-8') as f:
                flow_def = json.load(f)

            # Validate required fields
            required_fields = ["id", "name", "steps"]
            for field in required_fields:
                if field not in flow_def:
                    logger.error(f"Flow file {flow_file} missing required field: {field}")
                    continue

            workflows[flow_def["id"]] = flow_def
            logger.info(f"Loaded workflow: {flow_def['id']} - {flow_def['name']}")

        except Exception as e:
            logger.error(f"Error loading flow file {flow_file}: {e}")

    return workflows

def create_workflow_tools():
    """Dynamically create MCP tools for each workflow at startup"""
    for template_id, template_def in workflow_templates.items():
        tool_name = f"start_{template_id}_workflow"
        description = f"Start {template_def['name']} workflow. {template_def.get('description', '')}"

        # Create a closure to capture the template_id
        def make_workflow_tool(tid: str):
            def workflow_tool() -> Dict[str, Any]:
                return start_workflow(tid)
            return workflow_tool

        # Register the tool with FastMCP
        workflow_func = make_workflow_tool(template_id)
        workflow_func.__name__ = tool_name
        workflow_func.__doc__ = description

        # Use the mcp.tool decorator programmatically
        mcp.tool(name=tool_name)(workflow_func)
        logger.info(f"Auto-registered workflow tool: {tool_name}")

# In-memory workflow state storage
workflow_states = {}

# Load workflow templates dynamically from flows directory
# Use absolute path resolution for flows directory
import os
flows_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "flows")
workflow_templates = load_workflows_from_flows_dir(flows_dir)

# Auto-create workflow tools at startup
create_workflow_tools()

@mcp.tool()
def start_workflow(template_id: str) -> Dict[str, Any]:
    """
    Start a workflow by template ID
    Returns workflow state and initial guidance for the LLM
    """
    logger.info(f"Starting workflow: {template_id}")

    if template_id not in workflow_templates:
        return {"error": f"Unknown workflow template: {template_id}"}

    template = workflow_templates[template_id]
    workflow_id = f"{template_id}_{len(workflow_states) + 1:03d}"

    # Initialize workflow state
    workflow_state = {
        "workflow_id": workflow_id,
        "template_id": template_id,
        "template_name": template["name"],
        "current_step": 1,
        "total_steps": len(template["steps"]),
        "status": "active",
        "collected_data": {},
        "step_results": {}
    }

    # Store state
    workflow_states[workflow_id] = workflow_state

    # Get first step guidance
    first_step = template["steps"][0]

    return {
        "workflow_id": workflow_id,
        "template_name": template["name"],
        "current_step": 1,
        "total_steps": len(template["steps"]),
        "step_action": first_step["action"],
        "guidance": first_step["guidance"],
        "next_tools": first_step.get("next_tools", []),
        "command": first_step.get("command"),
        "status": "started"
    }

@mcp.tool()
def continue_workflow(workflow_id: str, step_result: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Continue a workflow to the next step
    step_result: Results from the previous step's tool execution
    """
    logger.info(f"Continuing workflow: {workflow_id}")

    if workflow_id not in workflow_states:
        return {"error": f"Workflow not found: {workflow_id}"}

    state = workflow_states[workflow_id]
    template = workflow_templates[state["template_id"]]

    if state["status"] != "active":
        return {"error": f"Workflow {workflow_id} is not active (status: {state['status']})"}

    # Store results from previous step
    if step_result:
        state["step_results"][state["current_step"]] = step_result

    # Move to next step
    current_step_num = state["current_step"]
    next_step_num = current_step_num + 1

    # Check if workflow is complete
    if next_step_num > state["total_steps"]:
        state["status"] = "completed"
        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "guidance": "Workflow completed successfully! All system information has been collected.",
            "collected_data": state["step_results"]
        }

    # Get next step
    state["current_step"] = next_step_num
    next_step = template["steps"][next_step_num - 1]  # 0-indexed array

    return {
        "workflow_id": workflow_id,
        "current_step": next_step_num,
        "total_steps": state["total_steps"],
        "step_action": next_step["action"],
        "guidance": next_step["guidance"],
        "next_tools": next_step.get("next_tools", []),
        "command": next_step.get("command"),
        "status": "continuing"
    }

@mcp.tool()
def continue_current_workflow(step_result: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Continue the most recently started workflow to the next step
    step_result: Results from the previous step's tool execution
    """
    if not workflow_states:
        return {"error": "No active workflows"}

    # Get the most recent workflow (highest numbered ID)
    latest_workflow_id = max(workflow_states.keys(), key=lambda x: x.split('_')[-1])
    return continue_workflow(latest_workflow_id, step_result)

@mcp.tool()
def get_workflow_status(workflow_id: str) -> Dict[str, Any]:
    """
    Get current status of a workflow
    """
    if workflow_id not in workflow_states:
        return {"error": f"Workflow not found: {workflow_id}"}

    state = workflow_states[workflow_id]
    template = workflow_templates[state["template_id"]]

    current_step = None
    if state["current_step"] <= len(template["steps"]):
        current_step = template["steps"][state["current_step"] - 1]

    return {
        "workflow_id": workflow_id,
        "template_name": state["template_name"],
        "current_step": state["current_step"],
        "total_steps": state["total_steps"],
        "status": state["status"],
        "current_step_action": current_step["action"] if current_step else None,
        "step_results_count": len(state["step_results"])
    }

# --- Entry Point ---

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--transport", type=str, choices=["stdio", "sse"], default="stdio")
    args = parser.parse_args()

    # Configure settings for SSE if requested
    if args.transport == "sse":
        # Recreate with host/port settings
        mcp = FastMCP("Hybrid MCP Server", host=args.host, port=args.port)
        print(f"[SSE] Hybrid MCP running on http://{args.host}:{args.port} (SSE at /sse/)", file=sys.stderr)
        mcp.run("sse")
    else:
        # stdio: do not print to stdout
        print("[STDIO] Hybrid MCP running over stdio (no stdout prints)", file=sys.stderr)
        # Add debug logging to track stdio server behavior
        logger.info("Starting stdio MCP server - process should remain running")
        try:
            mcp.run("stdio")
        except Exception as e:
            logger.error(f"Stdio server failed: {e}")
            raise
