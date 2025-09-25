"""
Workflow Resolver for MCP Integration
Resolves intents to workflow templates and creates tool envelopes
"""

from typing import Dict, List, Optional, Any

class WorkflowResolver:
    """Resolves intents to workflow templates and creates appropriate envelopes"""

    def __init__(self):
        # Template ID mapping for compatibility with MCP server
        self.template_mapping = {
            'rma_process_v1': 'rma_return',
            'employee_onboarding_v1': 'employee_onboarding',
            'system_info_v1': 'system_info',
            'contract_analysis_v1': 'contract_analysis'
        }

    def resolve_intent_to_template(self, intent_name: str) -> Optional[str]:
        """
        Resolve an intent name to a template ID

        Args:
            intent_name: The recognized intent name

        Returns:
            Template ID for MCP server or None if not mapped
        """
        return self.template_mapping.get(intent_name)

    def create_workflow_envelope(self, template_id: str, intent_name: str, confidence: float) -> Dict[str, Any]:
        """
        Create a tool envelope to start a workflow

        Args:
            template_id: The template ID for the MCP server
            intent_name: The original intent name
            confidence: The confidence score

        Returns:
            Envelope dictionary ready for execution
        """
        return {
            "tool_calls": [
                {
                    "name": "mcp_call",
                    "arguments": {
                        "name": "start_workflow",
                        "arguments": {
                            "template_id": template_id
                        }
                    }
                }
            ],
            "flow_context": {
                "workflow_triggered": True,
                "intent_name": intent_name,
                "confidence": confidence,
                "template_id": template_id
            }
        }

    def resolve_and_create_envelope(self, intent_name: str, confidence: float) -> Optional[Dict[str, Any]]:
        """
        Resolve intent and create workflow envelope

        Args:
            intent_name: The recognized intent name
            confidence: The confidence score

        Returns:
            Envelope dictionary or None if intent cannot be resolved
        """
        template_id = self.resolve_intent_to_template(intent_name)
        if template_id:
            return self.create_workflow_envelope(template_id, intent_name, confidence)
        return None