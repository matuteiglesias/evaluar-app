import pandas as pd
from flask import jsonify, request
import os
import openai
from dotenv import load_dotenv

def get_exercises():
    df = pd.read_csv('./exercises/exercises.csv')
    return jsonify(df.to_dict(orient='records'))

def preprocess_latex_for_mathjax(latex_content):
    # Simple replacement; for demonstration purposes only
    # A robust solution would require actual LaTeX parsing
    latex_content = latex_content.replace(r'\begin{enumerate}', '<ol>')
    latex_content = latex_content.replace(r'\end{enumerate}', '</ol>')
    latex_content = latex_content.replace(r'\item', '<li>')
    # Close the list item
    latex_content = latex_content.replace(r'</li><li>', '</li>\n<li>')
    latex_content = latex_content.replace(r'\begin{center}', '<div style="text-align: center;">').replace(r'\end{center}', '</div>')
    return latex_content


def get_exercise_content(filename):
    # Assuming your exercise text files are stored in a directory named 'exercises'
    exercises_dir = 'exercises'
    filepath = os.path.join(exercises_dir, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            content = file.read()
            # Optional: Wrap LaTeX content in delimiters here if necessary
            content = preprocess_latex_for_mathjax(content)
            return content
    except FileNotFoundError:
        return "Exercise content not found."
    

    # print("Current user session data:", session.get('user'))

    # if 'user' not in session:
    #     return redirect(url_for('login'))

    # user_details = session.get('user')
    # if not user_details:
    #     print("User details not found in session.")
    #     return redirect(url_for('index'))

    exercise_id = request.form.get('exercise_id')
    response = request.form.get('response')

# Fetch the exercise content based on the exercise_id
exercise_content = get_exercise_content('57')

response = 'This is a sample response to the exercise.'

# from evaluator import Evaluator
# evaluator = Evaluator()
# evaluated_response = evaluator.evaluate(exercise_content, response)


system_instructions = {
    "role": "system",
    "content": "You are an AI tutor evaluating a student's response to a computer science exercise. Provide detailed, constructive feedback focusing on both strengths and areas for improvement. Offer specific examples for enhancing the algorithm or addressing special cases. Recommend resources like readings, tutorials, or online tools for further exploration. Your feedback should incorporate academic and practical considerations in computer science, suitable for advanced students. Provide guidance in Spanish (Argentina) and assume a supportive and encouraging tone to foster a positive learning environment. Aim to stimulate reflection and initiative, including practical and theoretical recommendations to support academic and professional development. Encourage the examination of case studies or practical examples for a deeper, applied understanding of concepts. Suggest additional resources to enrich learning and promote a problem-solving approach."
}


# completion = openai.Completion.create(
#     # engine="gpt-3.5-turbo-instruct",  # Adjust based on the available engines
#     engine="gpt-4-turbo-preview",  # Updated to use a GPT-4 model variant
#     prompt=prompt,
#     temperature=0.7,
#     max_tokens=550,
#     n=1,
#     stop=None
# )
# evaluated_response = completion.choices[0].text.strip()

def construct_prompt(exercise_content, response):
    # Introduction to the exercise and response for a conversational context
    prompt_introduction = (
        "A continuación, se presenta una respuesta de un estudiante a un ejercicio de ciencias de la computación. "
        "Basándote en criterios académicos de alto nivel y enfocándome en proporcionar un feedback constructivo, "
        "analiza la respuesta, destacando los aspectos positivos y señalando áreas de mejora. "
        "Además, ofrece recomendaciones para profundizar en la comprensión de los conceptos tratados. "
    )
    
    # Incorporating the exercise content and student's response
    exercise_and_response = (
        f"Ejercicio:\n{exercise_content}\n\n"
        f"Respuesta del estudiante:\n{response}\n\n"
    )
    
    # Instructions for AI on how to proceed with the evaluation
    evaluation_instructions = (
        "Evalúa la respuesta siguiendo estas directrices, equilibrando comentarios positivos con áreas de mejora. "
        "Proporciona ejemplos concretos de cómo mejorar el algoritmo o abordar casos especiales y orienta hacia recursos específicos que puedan explorar para reforzar los conceptos discutidos. "
        "Promueve un ambiente de aprendizaje positivo, estimulando la reflexión y la iniciativa por parte del estudiante."
    )
    
    # Combining all parts into the final prompt
    complete_prompt = f"{prompt_introduction}{exercise_and_response}{evaluation_instructions}"
    return complete_prompt




chat_completion = openai.ChatCompletion.create(
    model="gpt-4-turbo-preview",  # Specify the chat model
    messages=[
        system_instructions,
        {"role": "user", "content": construct_prompt(exercise_content, response)}
    ],
    temperature=0.7,
    max_tokens=550,
    n=1,
    stop=None
)
            
# evaluated_response = completion.choices[0].text.strip()
# Correctly accessing the response message content
evaluated_response = chat_completion.choices[0].message['content'].strip()

print(evaluated_response)
