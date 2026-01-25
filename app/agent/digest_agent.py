from typing import Optional
from pydantic import BaseModel
from .base import BaseAgent

PROMPT = """You are an expert AI news analyst specializing in summarizing technical articles, research papers, and video content about artificial intelligence.

Your role is to create concise, informative digests that help readers quickly understand the key points and significance of AI-related content.

Guidelines:
- Create a compelling title (5-10 words) that captures the essence of the content
- Write a 2-3 sentence summary that highlights the main points and why they matter
- Focus on actionable insights and implications
- Use clear, accessible language while maintaining technical accuracy
- Avoid marketing fluff - focus on substance"""


class DigestOutput(BaseModel):
    title: str
    summary: str


class DigestAgent(BaseAgent):
    def __init__(self):
        super().__init__("llama-3.3-70b-versatile")
        self.system_prompt = PROMPT

    def generate_digest(self, title: str, content: str, article_type: str) -> Optional[DigestOutput]:
        try:
            user_prompt = f"""Create a digest for this {article_type}:
Title: {title}
Content: {content[:8000]}

Output strictly valid JSON matching this schema:
{{
  "title": "Compelling title (5-10 words)",
  "summary": "2-3 sentence summary"
}}"""

            response = self.get_completion(
                messages=[
                    {"role": "system", "content": self.system_prompt + "\n\nYou must output valid JSON."},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            return DigestOutput.model_validate_json(content)
        except Exception as e:
            print(f"Error generating digest: {e}")
            return None

