import os
import openai
import logging
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

load_dotenv()
logger = logging.getLogger(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

class Evaluator:
    def __init__(self, model_name="gpt-4o"):
        self.model_name = model_name
        self.env = Environment(loader=FileSystemLoader("llm/prompts"))

    def construct_prompt(self, exercise_content: str, student_response: str) -> str:
        try:
            template = self.env.get_template("prompt_template.j2")
            return template.render(
                exercise_content=exercise_content.strip(),
                student_response=student_response.strip()
            )
        except TemplateNotFound:
            logger.warning("Prompt template not found. Falling back to inline format.")
            return f"""Ejercicio:\n{exercise_content}\n\nRespuesta del estudiante:\n{student_response}\n\nAnaliza la respuesta..."""

    def evaluate(self, exercise_content: str, student_response: str) -> str:
        logger.info("Running LLM evaluation")
        prompt = self.construct_prompt(exercise_content, student_response)
        try:
            response = openai.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=550
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"LLM evaluation failed: {e}")
            return "Error evaluando la respuesta."
