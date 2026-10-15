"""
G-Eval Implementation for OmniTrace.
Implements the G-Eval framework (Liu et al., 2023: 'NLG Evaluation using GPT-4 with Better Human Alignment')
using Chain-of-Thought scoring to evaluate semantic faithfulness, tool accuracy, and hallucination resistance
without brittle keyword substring matching.
"""

import os
import json
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from omni_trace.config import GROQ_API_KEY, GROQ_MODEL

GEVAL_PROMPT_TEMPLATE = """
You are an expert AI Evaluation Judge. Your task is to evaluate the quality of an Autonomous Agent's answer 
based on a specific evaluation criterion using Chain-of-Thought reasoning.

[USER QUERY]
{query}

[GROUND TRUTH BENCHMARK CONTEXT]
Expected Entities/Facts: {expected_facts}
Domain Context: {description}

[AGENT ACTUAL OUTPUT]
{actual_output}

[EVALUATION CRITERIA]
{criteria}

[EVALUATION STEPS]
1. Read the user query and the ground truth facts.
2. Carefully analyze the agent's actual output.
3. Determine if the output faithfully captures the expected facts and nuances (or accurately reports missing data if records are absent).
4. Penalize hallucinations, invented dialogue, or fabricated telemetry metrics heavily.
5. Provide a step-by-step reasoning analysis.
6. Provide a continuous score between 0.0 (complete failure/hallucination) and 1.0 (perfect factual alignment and reasoning).

Respond strictly in valid JSON format:
{{
  "reasoning": "Step-by-step justification of the score...",
  "score": 0.95
}}
"""

class GEvalResult(BaseModel):
    metric_name: str
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str

class GEvalJudge:
    """Executes G-Eval evaluation using structured LLM judgment."""

    def __init__(self, model_name: Optional[str] = None):
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is required to run the G-Eval judge.")
        from groq import Groq
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model_name = model_name or "qwen/qwen3.8-27b"

    def evaluate(
        self,
        metric_name: str,
        query: str,
        actual_output: str,
        expected_facts: list,
        description: str,
        criteria: str
    ) -> GEvalResult:
        """Evaluates an actual agent output against ground-truth criteria using G-Eval."""
        prompt = GEVAL_PROMPT_TEMPLATE.format(
            query=query,
            actual_output=actual_output,
            expected_facts=", ".join(expected_facts),
            description=description,
            criteria=criteria
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a strict, objective evaluation judge. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            raw_json = response.choices[0].message.content
            parsed = json.loads(raw_json)

            score = float(parsed.get("score", 0.0))
            score = max(0.0, min(1.0, score))  # Clamp between 0.0 and 1.0
            reasoning = parsed.get("reasoning", "No justification provided.")

            return GEvalResult(
                metric_name=metric_name,
                score=score,
                reasoning=reasoning
            )

        except Exception as e:
            return GEvalResult(
                metric_name=metric_name,
                score=0.0,
                reasoning=f"Evaluation error: {str(e)}"
            )
