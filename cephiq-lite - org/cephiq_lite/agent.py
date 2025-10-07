"""
Agent - Core execution loop for Cephiq Lite

Main agent class that orchestrates:
- LLM decision making
- Tool execution
- History tracking
- Budget enforcement
"""
import time
from typing import Dict, Any, List, Optional
from .config import AgentConfig
from .llm import LLMClient
from .tools import ToolExecutor
from .prompt import PromptBuilder
from .envelope import create_error_envelope
from .tags import TagManager


class Agent:
    """Autonomous agent with envelope-based decision loop"""

    def __init__(self, config: AgentConfig):
        self.config = config

        # Initialize components
        self.llm = LLMClient(model=config.model, temperature=config.temperature)
        self.tools = ToolExecutor(
            mcp_server_path=config.mcp_server_path,
            timeout=config.tool_timeout
        )
        self.prompt_builder = PromptBuilder(custom_system_prompt=config.custom_system_prompt)

        # Tag management
        self.tag_manager = TagManager()
        self.current_tags: List = []
        self.allowed_tools: set = set()

        # State
        self.history: List[Dict[str, Any]] = []
        self.cycles_used = 0
        self.tokens_used = 0
        self.start_time: Optional[float] = None

    def run(self, goal: str) -> Dict[str, Any]:
        """
        Run agent to completion

        Args:
            goal: User's task description

        Returns:
            Final result dict with:
            - success: bool
            - final_envelope: dict
            - history: list
            - stats: dict (cycles, tokens, duration)
        """
        self.start_time = time.time()

        # Initialize tag-based permissions
        if self.config.enable_tags:
            self.current_tags = self.tag_manager.resolve_tags_for_user(
                user_id=self.config.user_id,
                user_roles=self.config.user_roles,
                org_id=self.config.org_id
            )
            self.allowed_tools = self.tag_manager.get_allowed_tools(self.current_tags)

        last_observation = None
        final_envelope = None

        while True:
            # Check budgets
            if not self._check_budgets():
                final_envelope = create_error_envelope(
                    "Budget exhausted",
                    error_type="budget_exhausted"
                )
                break

            # Build prompt with current context
            messages = self.prompt_builder.build_messages(
                goal=goal,
                history=self.history,
                last_observation=last_observation,
                budgets=self._get_remaining_budgets()
            )

            # Get LLM decision
            if self.config.verbose:
                print(f"\n[Cycle {self.cycles_used + 1}] Getting decision from LLM...")

            envelope = self.llm.decide_with_retry(messages, max_tokens=self.config.max_tokens_per_call)

            self.cycles_used += 1

            # Track decision in history
            self._record_decision(envelope)

            # Handle the decision
            state = envelope.get("state")

            if state == "tool":
                # Execute single tool
                last_observation = self._execute_single_tool(envelope)

            elif state == "tools":
                # Execute multiple tools
                last_observation = self._execute_multi_tool(envelope)

            elif state == "reply":
                # Agent is replying to user
                if self.config.verbose:
                    utterance = envelope.get("conversation", {}).get("utterance", "")
                    print(f"\n[Agent]: {utterance}")
                final_envelope = envelope

            elif state == "plan":
                # Agent created a plan
                if self.config.verbose:
                    plan_data = envelope.get("plan", {})
                    print(f"\n[Plan]: {plan_data.get('summary', 'Planning...')}")
                last_observation = None  # Plans don't produce observations

            elif state == "error":
                # Agent encountered an error
                if self.config.verbose:
                    error_data = envelope.get("error", {})
                    print(f"\n[Error]: {error_data.get('error_message', 'Unknown error')}")
                final_envelope = envelope

            elif state == "clarify":
                # Agent needs clarification
                clarify_data = envelope.get("clarify", {})
                question = clarify_data.get("question", "Need more information")

                if self.config.auto_approve:
                    # Auto-decline clarification
                    if self.config.verbose:
                        print(f"\n[Clarify]: {question} (auto-declined)")
                    final_envelope = create_error_envelope(
                        "Agent requested clarification but auto_approve=True",
                        error_type="need_input"
                    )
                else:
                    if self.config.verbose:
                        print(f"\n[Clarify]: {question}")
                    final_envelope = envelope

            elif state == "confirm":
                # Agent needs confirmation
                confirm_data = envelope.get("confirm", {})
                action = confirm_data.get("action", "Proceed with action")

                if self.config.auto_approve:
                    # Auto-approve and continue
                    if self.config.verbose:
                        print(f"\n[Confirm]: {action} (auto-approved)")
                    last_observation = {
                        "success": True,
                        "tool": "user_confirmation",
                        "result": {"approved": True},
                        "duration_ms": 0
                    }
                else:
                    if self.config.verbose:
                        print(f"\n[Confirm]: {action}")
                    final_envelope = envelope

            elif state == "reflect":
                # Agent is reflecting
                if self.config.verbose:
                    reflect_data = envelope.get("reflect", {})
                    print(f"\n[Reflect]: {reflect_data.get('thoughts', 'Thinking...')}")
                last_observation = None  # Reflection doesn't produce observations

            else:
                # Unknown state
                final_envelope = create_error_envelope(
                    f"Unknown state: {state}",
                    error_type="invalid_state"
                )

            # Check if agent wants to continue
            meta = envelope.get("meta", {})
            should_continue = meta.get("continue", False)

            if not should_continue or final_envelope:
                # Agent wants to stop or we hit an error/clarify/confirm
                if not final_envelope:
                    final_envelope = envelope
                break

        # Build result
        duration = time.time() - self.start_time if self.start_time else 0

        return {
            "success": final_envelope.get("state") not in ["error", "clarify", "confirm"],
            "final_envelope": final_envelope,
            "history": self.history,
            "stats": {
                "cycles": self.cycles_used,
                "tokens": self.tokens_used,
                "duration_seconds": round(duration, 2)
            }
        }

    def _execute_single_tool(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """Execute single tool from envelope"""
        tool = envelope.get("tool")
        arguments = envelope.get("arguments", {})

        # Check tool permissions
        if self.config.enable_tags and not self.tag_manager.validate_tool_access(tool, self.current_tags):
            return {
                "success": False,
                "tool": tool,
                "error": f"Tool '{tool}' not allowed by current permissions",
                "duration_ms": 0
            }

        if self.config.verbose:
            print(f"  -> Executing tool: {tool}")

        result = self.tools.execute_single(tool, arguments)

        # Record in history
        self._record_tool_result(result)

        if self.config.verbose:
            status = "OK" if result.get("success") else "FAIL"
            duration = result.get("duration_ms", 0)
            print(f"  <- {status} ({duration}ms)")

        return result

    def _execute_multi_tool(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """Execute multiple tools from envelope"""
        tools_array = envelope.get("tools", [])

        # Check tool permissions for each tool
        if self.config.enable_tags:
            filtered_tools = []
            for tool_item in tools_array:
                tool = tool_item.get("tool")
                if self.tag_manager.validate_tool_access(tool, self.current_tags):
                    filtered_tools.append(tool_item)
                else:
                    if self.config.verbose:
                        print(f"  → Skipping tool '{tool}' (not allowed by permissions)")

            if len(filtered_tools) != len(tools_array):
                tools_array = filtered_tools
                if not tools_array:
                    return {
                        "success": False,
                        "error": "No tools allowed by current permissions",
                        "tool": "multi_tool"
                    }

        if self.config.verbose:
            print(f"  -> Executing {len(tools_array)} tools in parallel...")

        # Check if multi-tool is enabled
        if not self.config.enable_multi_tool:
            return {
                "success": False,
                "error": "Multi-tool execution disabled in config",
                "tool": "multi_tool"
            }

        result = self.tools.execute_batch(tools_array, parallel=True)

        # Record in history
        self._record_tools_result(result)

        if self.config.verbose:
            all_ok = result.get("all_success", False)
            status = "ALL OK" if all_ok else "PARTIAL"
            print(f"  <- {status}")

        return result

    def _check_budgets(self) -> bool:
        """Check if budgets are within limits"""
        if self.cycles_used >= self.config.max_cycles:
            if self.config.verbose:
                print(f"\n[Budget] Max cycles reached: {self.cycles_used}/{self.config.max_cycles}")
            return False

        if self.tokens_used >= self.config.max_total_tokens:
            if self.config.verbose:
                print(f"\n[Budget] Max tokens reached: {self.tokens_used}/{self.config.max_total_tokens}")
            return False

        if self.config.max_time_seconds:
            elapsed = time.time() - self.start_time if self.start_time else 0
            if elapsed >= self.config.max_time_seconds:
                if self.config.verbose:
                    print(f"\n[Budget] Max time reached: {elapsed:.1f}/{self.config.max_time_seconds}s")
                return False

        return True

    def _get_remaining_budgets(self) -> Dict[str, int]:
        """Get remaining budgets for display"""
        return {
            "cycles": self.config.max_cycles - self.cycles_used,
            "tokens": self.config.max_total_tokens - self.tokens_used
        }

    def _record_decision(self, envelope: Dict[str, Any]) -> None:
        """Record decision in history"""
        self.history.append({
            "type": "decision",
            "timestamp": time.time(),
            "envelope": envelope
        })

    def _record_tool_result(self, result: Dict[str, Any]) -> None:
        """Record tool result in history"""
        self.history.append({
            "type": "tool_result",
            "timestamp": time.time(),
            "result": result
        })

    def _record_tools_result(self, result: Dict[str, Any]) -> None:
        """Record multi-tool result in history"""
        self.history.append({
            "type": "tools_result",
            "timestamp": time.time(),
            "results": result
        })


if __name__ == "__main__":
    # Self-test
    import os
    import sys

    if "ANTHROPIC_API_KEY" not in os.environ:
        print("Set ANTHROPIC_API_KEY environment variable to test")
        sys.exit(1)

    # Test with simple goal
    config = AgentConfig(
        verbose=True,
        max_cycles=10,
        auto_approve=True
    )

    agent = Agent(config)

    result = agent.run("Create a file called hello.txt with the content 'Hello from Cephiq Lite!'")

    print("\n" + "="*60)
    print("RESULT")
    print("="*60)
    print(f"Success: {result['success']}")
    print(f"Cycles: {result['stats']['cycles']}")
    print(f"Duration: {result['stats']['duration_seconds']}s")
    print(f"\nFinal state: {result['final_envelope'].get('state')}")

    if result['final_envelope'].get('state') == 'reply':
        utterance = result['final_envelope'].get('conversation', {}).get('utterance', '')
        print(f"Agent says: {utterance}")
