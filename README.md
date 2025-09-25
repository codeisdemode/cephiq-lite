# Cephiq Core - AI Agent Orchestration Platform

A sophisticated AI agent orchestration system built with Model Context Protocol (MCP) that enables intelligent workflow automation, contract analysis, and multi-agent collaboration.

## 🚀 Features

### Core Capabilities
- **MCP Server Architecture**: Hybrid PowerShell + Python MCP server with SSE and stdio transports
- **Workflow Automation**: Template-based workflow system with dynamic tool registration
- **Contract Analysis**: Specialized workflows for Dutch construction contract compliance
- **PDF Processing**: Intelligent PDF text extraction with OCR fallback
- **Multi-Agent Collaboration**: Advanced agent orchestration with state management

### Workflow System
- **Contract Analysis Workflow**: 7-step process for comprehensive contract review
- **Employee Onboarding**: Automated employee onboarding process
- **RMA Return Process**: Device return and replacement workflow
- **System Information Collection**: Automated system diagnostics

### Technical Features
- **Enhanced Chat CLI**: Clean, intuitive interface with real-time agent control
- **Dynamic Tool Registration**: Automatic MCP tool discovery and registration
- **State Machine Support**: Advanced envelope schema for agent state management
- **Error Handling**: Robust error recovery and logging

## 📋 Quick Start

### Prerequisites
- Python 3.8+
- PowerShell 5.1+
- Required Python packages (install via `pip install -r requirements.txt`)

### Installation
```bash
# Clone the repository
git clone https://github.com/codeisdemode/cephiq-core.git
cd cephiq-core

# Install dependencies
pip install -r requirements.txt

# Start the enhanced chat CLI
python chat_cli_enhanced.py
```

### Running the System

#### Start MCP Server
```bash
# Start the hybrid MCP server
python orchestrator/combined_mcp_server.py
```

#### Use Enhanced Chat CLI
```bash
# Start the enhanced interface
python chat_cli_enhanced.py
```

## 🏗️ Architecture

### Core Components

#### MCP Server (`orchestrator/combined_mcp_server.py`)
- Hybrid PowerShell + Python implementation
- Supports both SSE and stdio transports
- Dynamic workflow tool registration
- PDF processing with OCR capabilities

#### Workflow System (`flows/` directory)
- JSON-based workflow templates
- Step-by-step execution with completion checks
- Dynamic tool assignment per workflow step

#### Chat CLI (`chat_cli_enhanced.py`)
- Clean, user-friendly interface
- Real-time agent status monitoring
- Keyboard shortcuts for agent control

### Key Directories
- `orchestrator/` - Core orchestration logic and MCP server
- `flows/` - Workflow template definitions
- `contracten/` - Contract analysis examples and reports
- `logs/` - System and debug logs

## 📊 Workflows

### Contract Analysis Workflow
A comprehensive 7-step process for analyzing Dutch construction contracts:

1. **Contract Intake** - Plan creation and scope definition
2. **Text Extraction** - PDF text and metadata extraction
3. **Compliance Analysis** - VAT, safety plans, payment terms review
4. **Risk Assessment** - Comprehensive risk evaluation
5. **Report Generation** - Detailed analysis report creation
6. **Quality Review** - Report validation and verification
7. **Report Formatting** - Professional layout and formatting

### Available Workflows
- `contract_analysis` - Dutch construction contract review
- `employee_onboarding` - Automated employee onboarding
- `rma_return` - Device return and replacement process
- `system_info` - System diagnostics and information collection

## 🔧 Tools & Capabilities

### PDF Processing
- `extract_pdf_text` - Intelligent text extraction with OCR fallback
- `extract_pdf_metadata` - Comprehensive PDF metadata extraction
- `format_markdown_report` - Professional report formatting and layout

### File Operations
- `read_file` / `write_block` - File reading and writing
- `create_file` / `create_directory` - File and directory management
- `copy_item` / `move_item` / `delete_item` - File operations

### System Operations
- `get_files` / `get_current_date` - System information
- `get_processes` / `get_services` - Process and service management
- `python` / `powershell` - Script execution capabilities

## 🛠️ Development

### Adding New Workflows
1. Create workflow template in `flows/` directory
2. Define steps with actions, guidance, and completion checks
3. Tools are automatically registered at startup

### Custom Tool Development
```python
@mcp.tool()
def custom_tool(param1: str, param2: int) -> Dict[str, Any]:
    """Custom tool description"""
    # Implementation here
    return {"result": "success"}
```

### Testing
```bash
# Test workflow configuration
python test_complete_workflow.py

# Test PDF extraction
python test_pdf_extractor.py

# Test report formatting
python test_report_formatting.py
```

## 📈 Recent Updates

### Latest Features
- **Enhanced Contract Analysis**: 7-step workflow with professional formatting
- **PDF OCR Support**: Intelligent text extraction with OCR fallback
- **Improved CLI Interface**: Cleaner, more intuitive user experience
- **Workflow State Management**: Advanced state tracking and recovery

### Key Improvements
- Dynamic MCP tool registration
- Enhanced error handling and logging
- Better workflow completion tracking
- Professional report formatting capabilities

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines for details on:
- Code style and standards
- Testing requirements
- Documentation updates
- Feature proposals

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

For support and questions:
- Create an issue on GitHub
- Check the documentation in `docs/` directory
- Review existing workflow examples

## 🔗 Related Projects

- [Model Context Protocol](https://github.com/modelcontextprotocol) - MCP specification
- [FastMCP](https://github.com/modelcontextprotocol/fastmcp) - FastMCP implementation

---

**Cephiq Core** - Empowering intelligent automation through advanced AI agent orchestration.