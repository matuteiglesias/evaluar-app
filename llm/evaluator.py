import os
import openai
import logging
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

load_dotenv()
logger = logging.getLogger(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

class Evaluator:
    """
    A class to evaluate student responses using a language model.

    Attributes:
        model_name (str): The name of the language model to use for evaluation.
        env (Environment): The Jinja2 environment for loading prompt templates.

    Methods:
        construct_prompt(exercise_content: str, student_response: str) -> str:
            Constructs a prompt for the language model using the provided exercise content
            and student response. Falls back to an inline format if the template is not found.

        evaluate(exercise_content: str, student_response: str) -> str:
            Evaluates the student's response to the exercise using the language model.
            Returns the evaluation result or an error message if the evaluation fails.
    """
    def __init__(self, model_name="gpt-4o"):
        self.model_name = model_name
        self.env = Environment(loader=FileSystemLoader("llm/prompts"))

    def construct_prompt(self, exercise_content: str, student_response: str) -> str:
        """
        Constructs a prompt for evaluating a student's response to an exercise.

        This method uses a Jinja2 template to format the prompt. If the template
        is not found, it falls back to an inline string format.

        Args:
            exercise_content (str): The content of the exercise or question.
            student_response (str): The student's response to the exercise.

        Returns:
            str: A formatted prompt string for evaluation.

        Raises:
            TemplateNotFound: If the specified Jinja2 template is not found.
        """
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
        """
        Evaluates a student's response to an exercise using a language model.

        Args:
            exercise_content (str): The content of the exercise to be evaluated.
            student_response (str): The student's response to the exercise.

        Returns:
            str: The evaluation result as a string. If an error occurs during the 
            evaluation process, returns an error message.
        """
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
