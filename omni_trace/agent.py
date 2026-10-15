"""
Core Autonomous ReAct Agent Loop for OmniTrace.
Implements Reason -> Act -> Observe -> Reflect cycles with tool calling,
autonomous error interception (self-healing), and execution tracing.
Supports multi-provider execution (Groq & Google Gemini) for enterprise resilience.
"""

import time
import json
from typing import List, Dict, Any, Optional

from omni_trace.config import (
    GEMINI_API_KEY,
    GROQ_API_KEY,
    DEFAULT_PROVIDER,
    GEMINI_MODEL,
    GROQ_MODEL,
    MAX_RETRY_BUDGET,
    MAX_AGENT_TURNS,
)
from omni_trace.models import AgentTrace, AgentStep, AgentAction, ToolResult
from omni_trace.tools import ALL_TOOLS, inspect_schema, execute_sql, search_transcripts

SYSTEM_INSTRUCTION = """
You are OmniTrace, an Autonomous Hybrid Intelligence Agent specializing in unifying 
structured telemetry (SQL) with unstructured textual evidence (transcripts & reports).

YOUR OPERATING PROTOCOL (ReAct):
1. REASON: Analyze what data is required. Identify if the query requires structured metrics, 
   unstructured narrative text, or both.
2. ACT: Call the appropriate tools:
   - `inspect_schema`: Discover available tables and column names before writing complex SQL.
   - `execute_sql`: Query quantitative telemetry (drop-off rates, timestamps, episode completion, regional shares).
   - `search_transcripts`: Query qualitative dialogue, scene summaries, and character actions. Always use `timestamp_seconds` and `window_seconds` when investigating a drop-off event.
3. OBSERVE & REFLECT: Evaluate tool outputs carefully.
   - If an SQL query produces an error, read the error message, identify the schema mismatch, and write a corrected query (Self-Healing).
   - If a tool returns 0 matching rows or empty results, state this fact honestly. Do NOT hallucinate missing dialogue or metrics.
   - If you observe conflicting data between telemetry and transcripts, document the discrepancy.
4. SYNTHESIZE: When you have sufficient observations, provide a concise, evidence-backed final diagnosis citing both telemetry numbers and scene dialogue.
"""

# OpenAPI / JSON Schema function definitions for OpenAI/Groq compatibility
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "inspect_schema",
            "description": "Inspects available database tables or retrieves column definitions for a specific table. Use this first when you need to know which tables exist or what columns are available.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": ["string", "null"],
                        "description": "The name of the table to inspect. Pass null or empty string to list all tables."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "Executes a safe, read-only SQL query against the SQLite telemetry database. Only SELECT or WITH queries are permitted. Destructive queries (DROP, INSERT, etc.) are blocked.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The read-only SQL query to execute."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_transcripts",
            "description": "Searches show transcripts and scene dialogue with windowed temporal retrieval. Use episode_id and timestamp_seconds to locate scene dialogue around a drop-off.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": ["string", "null"],
                        "description": "Semantic query or keywords (e.g. 'confrontation', 'audio glitch')."
                    },
                    "episode_id": {
                        "type": ["integer", "null"],
                        "description": "Episode ID (e.g. 101, 103)."
                    },
                    "timestamp_seconds": {
                        "type": ["integer", "null"],
                        "description": "Scene timestamp in seconds (e.g. 790)."
                    },
                    "window_seconds": {
                        "type": ["integer", "null"],
                        "description": "Tolerance window in seconds (+/- tolerance, default 60)."
                    }
                }
            }
        }
    }
]

class OmniTraceAgent:
    """Autonomous ReAct agent for hybrid analytics and transcript retrieval."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        max_turns: int = MAX_AGENT_TURNS,
        retry_budget: int = MAX_RETRY_BUDGET
    ):
        self.provider = provider or DEFAULT_PROVIDER
        self.max_turns = max_turns
        self.retry_budget = retry_budget
        
        # Tool dispatch mapping
        self._tool_map = {
            "inspect_schema": inspect_schema,
            "execute_sql": execute_sql,
            "search_transcripts": search_transcripts,
        }

        if self.provider == "groq":
            if not GROQ_API_KEY:
                raise ValueError("GROQ_API_KEY is missing in environment variables.")
            from groq import Groq
            self.groq_client = Groq(api_key=GROQ_API_KEY)
            self.model_name = model_name or GROQ_MODEL
        else:
            if not GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY is missing in environment variables.")
            from google import genai
            self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            self.model_name = model_name or GEMINI_MODEL

    def run(self, query: str) -> AgentTrace:
        """Executes an autonomous ReAct loop with the configured provider."""
        if self.provider == "groq":
            return self._run_groq(query)
        else:
            return self._run_gemini(query)

    def _run_groq(self, query: str) -> AgentTrace:
        """ReAct loop using Groq OpenAI-compatible tool calling."""
        start_time = time.time()
        steps: List[AgentStep] = []
        tools_called: List[str] = []
        self_healing_count = 0
        consecutive_tool_errors = 0

        messages = [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": f"User Query: {query}"}
        ]

        final_answer = ""
        status = "COMPLETED"

        for turn_idx in range(1, self.max_turns + 1):
            response = None
            last_err = None
            from omni_trace.config import FALLBACK_GROQ_MODELS
            models_to_try = [self.model_name] + [m for m in FALLBACK_GROQ_MODELS if m != self.model_name]

            for candidate_model in models_to_try:
                try:
                    response = self.groq_client.chat.completions.create(
                        model=candidate_model,
                        messages=messages,
                        tools=TOOLS_SCHEMA,
                        tool_choice="auto",
                        temperature=0.1
                    )
                    self.model_name = candidate_model
                    break
                except Exception as e:
                    last_err = e
                    if "rate_limit" in str(e).lower() or "429" in str(e):
                        continue
                    raise e

            if not response:
                raise last_err or RuntimeError("All model candidates exhausted.")

            msg = response.choices[0].message
            tool_calls = msg.tool_calls

            if not tool_calls:
                final_answer = msg.content or ""
                steps.append(AgentStep(
                    step_number=turn_idx,
                    thought=final_answer or "Reached final synthesis.",
                    action=None,
                    observation="Execution complete."
                ))
                break

            # Append assistant message with tool calls
            messages.append(msg)

            for call in tool_calls:
                tool_name = call.function.name
                try:
                    tool_args = json.loads(call.function.arguments) if call.function.arguments else {}
                except json.JSONDecodeError:
                    tool_args = {}

                tools_called.append(tool_name)

                step = AgentStep(
                    step_number=turn_idx,
                    thought=msg.content or f"Invoking tool {tool_name}",
                    action=AgentAction(tool_name=tool_name, tool_args=tool_args)
                )

                tool_fn = self._tool_map.get(tool_name)
                if not tool_fn:
                    tool_output = {
                        "tool_name": tool_name,
                        "success": False,
                        "error": f"Tool '{tool_name}' is not registered."
                    }
                else:
                    try:
                        tool_output = tool_fn(**tool_args)
                    except Exception as exc:
                        tool_output = {
                            "tool_name": tool_name,
                            "success": False,
                            "error": f"Unhandled tool execution exception: {str(exc)}"
                        }

                is_success = tool_output.get("success", False)
                if not is_success:
                    consecutive_tool_errors += 1
                    step.error_detected = True
                    if consecutive_tool_errors > self.retry_budget:
                        status = "MAX_RETRY_EXCEEDED"
                        final_answer = (
                            f"Agent halted: Exceeded self-healing retry budget ({self.retry_budget} attempts). "
                            f"Last error in {tool_name}: {tool_output.get('error')}"
                        )
                        break
                else:
                    if consecutive_tool_errors > 0:
                        step.self_healed = True
                        self_healing_count += 1
                        consecutive_tool_errors = 0

                step.observation = str(tool_output)
                steps.append(step)

                # Append tool observation
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": tool_name,
                    "content": json.dumps(tool_output)
                })

            if status == "MAX_RETRY_EXCEEDED":
                break

        if not final_answer:
            final_answer = "Agent reached maximum allowed turns without final synthesis."
            status = "MAX_STEPS_EXCEEDED"

        elapsed_sec = round(time.time() - start_time, 2)

        return AgentTrace(
            query=query,
            final_answer=final_answer,
            steps=steps,
            tools_called=tools_called,
            self_healing_count=self_healing_count,
            execution_time_sec=elapsed_sec,
            status=status
        )

    def _run_gemini(self, query: str) -> AgentTrace:
        """ReAct loop using Google GenAI SDK."""
        from google.genai import types
        start_time = time.time()
        steps: List[AgentStep] = []
        tools_called: List[str] = []
        self_healing_count = 0
        consecutive_tool_errors = 0

        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=f"User Query: {query}")]
            )
        ]

        generate_config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.1,
            tools=ALL_TOOLS,
        )

        final_answer = ""
        status = "COMPLETED"

        for turn_idx in range(1, self.max_turns + 1):
            response = self.gemini_client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=generate_config
            )

            model_text = ""
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if part.text:
                        model_text += part.text

            function_calls = response.function_calls

            if not function_calls:
                final_answer = model_text.strip()
                steps.append(AgentStep(
                    step_number=turn_idx,
                    thought=final_answer or "Reached final synthesis.",
                    action=None,
                    observation="Execution complete."
                ))
                break

            contents.append(response.candidates[0].content)

            function_response_parts = []
            for call in function_calls:
                tool_name = call.name
                tool_args = call.args or {}
                tools_called.append(tool_name)

                step = AgentStep(
                    step_number=turn_idx,
                    thought=model_text.strip() if model_text else f"Invoking tool {tool_name}",
                    action=AgentAction(tool_name=tool_name, tool_args=tool_args)
                )

                tool_fn = self._tool_map.get(tool_name)
                if not tool_fn:
                    tool_output = {
                        "tool_name": tool_name,
                        "success": False,
                        "error": f"Tool '{tool_name}' is not registered."
                    }
                else:
                    try:
                        tool_output = tool_fn(**tool_args)
                    except Exception as exc:
                        tool_output = {
                            "tool_name": tool_name,
                            "success": False,
                            "error": f"Unhandled tool execution exception: {str(exc)}"
                        }

                is_success = tool_output.get("success", False)
                if not is_success:
                    consecutive_tool_errors += 1
                    step.error_detected = True
                    if consecutive_tool_errors > self.retry_budget:
                        status = "MAX_RETRY_EXCEEDED"
                        final_answer = (
                            f"Agent halted: Exceeded self-healing retry budget ({self.retry_budget} attempts). "
                            f"Last error in {tool_name}: {tool_output.get('error')}"
                        )
                        break
                else:
                    if consecutive_tool_errors > 0:
                        step.self_healed = True
                        self_healing_count += 1
                        consecutive_tool_errors = 0

                step.observation = str(tool_output)
                steps.append(step)

                function_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": tool_output}
                    )
                )

            if status == "MAX_RETRY_EXCEEDED":
                break

            contents.append(
                types.Content(role="user", parts=function_response_parts)
            )

        if not final_answer:
            final_answer = "Agent reached maximum allowed turns without final synthesis."
            status = "MAX_STEPS_EXCEEDED"

        elapsed_sec = round(time.time() - start_time, 2)

        return AgentTrace(
            query=query,
            final_answer=final_answer,
            steps=steps,
            tools_called=tools_called,
            self_healing_count=self_healing_count,
            execution_time_sec=elapsed_sec,
            status=status
        )
