import os
import openai
from dotenv import load_dotenv
from exercise import Exercise

# Load environment variables from .env file
load_dotenv()

class Evaluator:
    def __init__(self):
        # Initialize evaluator properties
        self.exercise = Exercise()
        # Load your OpenAI API key from an environment variable
        openai.api_key = os.getenv('OPENAI_API_KEY')

    def evaluate(self, response):
        # Evaluate the response using AI-based machine evaluator
        return self.machine_evaluate(response)

    def machine_evaluate(self, response):
        # Replace placeholder implementation with a call to OpenAI's API
        try:
            # Construct the prompt to send to the API
            prompt = self.construct_prompt(response)
            # Make the API call
            completion = openai.Completion.create(
                engine="text-davinci-003",  # or "gpt-4" based on your preference
                prompt=prompt,
                temperature=0.7,
                max_tokens=150,
                n=1,
                stop=None
            )
            # Extract the text from the response
            evaluated_response = completion.choices[0].text.strip()
            return evaluated_response
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return "Error evaluating response."