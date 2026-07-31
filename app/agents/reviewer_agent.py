from typing import Dict, Any
from google import genai
from google.genai import types
import json
import os

class ReviewerAgent:
    def __init__(self):
        # Configura explícitamente el uso de Vertex AI en GCP
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            raise ValueError("Por favor configura la variable de entorno GOOGLE_CLOUD_PROJECT")
            
        self.client = genai.Client(vertexai=True, project=project_id, location="us-central1")
        self.model_name = "gemini-2.5-pro"

    def review_code(self, diff_content: str, business_context: str = "") -> Dict[str, Any]:
        """
        Takes a code diff, sends it to Gemini Pro, and returns structured feedback.
        """
        base_instruction = (
            "You are a Senior Security and Architecture Engineer performing a Code Review. "
            "You will be given a code diff or a file's content. "
            "Think step-by-step (Chain-of-Thought) to identify: "
            "1. Security vulnerabilities. "
            "2. Logic bugs. "
            "3. Architecture/Best practices improvements. "
        )
        
        if business_context:
            base_instruction += (
                f"\n\nCRITICAL: You MUST strictly enforce the following PinApp business rules and contracts "
                f"extracted from our knowledge base. Evaluate the diff against these rules:\n"
                f"<BUSINESS_RULES>\n{business_context}\n</BUSINESS_RULES>\n\n"
            )

        system_instruction = base_instruction + (
            "Output your final response STRICTLY in valid JSON format matching the following schema: "
            "{\"risk_level\": \"LOW|MEDIUM|HIGH\", \"analysis\": \"Detailed explanation of the findings\", \"issues\": [{\"line_number\": \"12\", \"description\": \"explanation of the issue\"}]}"
        )
        
        prompt = f"Please review the following code changes:\n\n{diff_content}"
        
        # We use JSON response schema to ensure predictable routing/UI rendering
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
            )
        )
        
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            return {"error": "Failed to parse LLM output as JSON", "raw_output": response.text}
