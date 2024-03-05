import os
import openai
from dotenv import load_dotenv
import logging
# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)  # Usa el mismo logger configurado globalmente

from abc import ABC, abstractmethod

class Evaluator(ABC):
    def __init__(self, model_name):
        self.model_name = model_name
        openai.api_key = os.getenv('OPENAI_API_KEY')

    @abstractmethod
    def construct_prompt(self, exercise_content, response):
        pass

    @abstractmethod
    def evaluate(self, exercise_content, response):
        pass


class Evaluator35(Evaluator):
    def __init__(self):
        super().__init__(model_name="gpt-3.5-turbo-instruct")


    def construct_prompt(self, exercise_content, response, evaluation_style="neutral"):
        if not exercise_content or not response:
            logger.error("Received invalid exercise_content or response. GPT35")
            # Devuelve un valor predeterminado o maneja el error adecuadamente
            return "Error: El contenido del ejercicio o la respuesta del estudiante no es válido."
        
        # Introduction to the exercise and response for a conversational context
        prompt_introduction = (
            "A continuación, se presenta una respuesta de un estudiante a un ejercicio de ciencias de la computación. "
            "Primero, evalúa brevemente la calidad de la respuesta del estudiante a un ejercicio de ciencias de la computación. "
            "Esta evaluación inicial ayudará a evitar generar feedback extenso e inapropiado para respuestas que no lo ameriten.\n\n"
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
            "Promueve un ambiente de aprendizaje positivo, estimulando la reflexión y la iniciativa por parte del estudiante. Espanol de Argnetina. Sos mujer."
            "Ten mucho cuidado cuando cites libros, hace un doble chequeo de que efectivamente existan. No recomiendes Coursera u otras plataformas de aprendizaje online."
            "No inviertas todos los token en una respuesta larga, si el estudiante no propone una resolucion detallada. Manten la respuesta corta y concisa pero sin olvidar ningun detalle."
        )
        
        # Combining all parts into the final prompt
        complete_prompt = f"{prompt_introduction}{exercise_and_response}{evaluation_instructions}"
        # logger.info(f"Constructed prompt for OpenAI API call. : {complete_prompt}")
        return complete_prompt



    # Si es necesario, sobrescribe otros métodos específicos del modelo

    def evaluate(self, exercise_content, response):
        logger.info(f"Inside Evaluator35")
        # Call to construct the prompt with the exercise content and student's response
        prompt = self.construct_prompt(exercise_content, response)
        # API call to OpenAI
        try:

            # GPT 3.5
            completion = openai.Completion.create(
                engine="gpt-3.5-turbo-instruct",  # Adjust based on the available engines
                # engine="gpt-4-turbo-preview",  # Updated to use a GPT-4 model variant
                prompt=prompt,
                temperature=0.7,
                max_tokens=550,
                n=1,
                stop=None
            )

            # Asegurándote de acceder correctamente a la respuesta
            evaluated_response = completion.choices[0].text.strip() # GPT 3.5
            logger.info("Received evaluation response from OpenAI API.")
            
            return evaluated_response


        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return "Error evaluando la respuesta."


class Evaluator40(Evaluator):
    def __init__(self):
        super().__init__(model_name="gpt-4-turbo-preview")


    def construct_prompt(self, exercise_content, response, evaluation_style="neutral"):
        if not exercise_content or not response:
            logger.error("Received invalid exercise_content or response. GPT40")
            # Devuelve un valor predeterminado o maneja el error adecuadamente
            return "Error: El contenido del ejercicio o la respuesta del estudiante no es válido."

        # Construcción específica del prompt para GPT-4
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
            "Promueve un ambiente de aprendizaje positivo, estimulando la reflexión y la iniciativa por parte del estudiante. Espanol de Argnetina. Sos mujer."
            "Ten mucho cuidado cuando cites libros, hace un doble chequeo de que efectivamente existan. No recomiendes Coursera u otras plataformas de aprendizaje online."
            "No inviertas todos los token en una respuesta larga, si el estudiante no propone una resolucion detallada. Manten la respuesta corta y concisa pero sin olvidar ningun detalle."
        )
        
        # Combining all parts into the final prompt
        complete_prompt = f"{prompt_introduction}{exercise_and_response}{evaluation_instructions}"
        logger.info(f"Constructed prompt for OpenAI API call. : {complete_prompt}")
        return complete_prompt


    # Implementación específica para chat_completion si es diferente

    def evaluate(self, exercise_content, response):
        logger.info(f"Inside Evaluator40")

        # Call to construct the prompt with the exercise content and student's response
        # prompt = self.construct_prompt(exercise_content, response)
        # API call to OpenAI
        try:

            system_instructions = {
                "role": "system",
                "content": "You are an AI tutor evaluating a student's response to a computer science exercise. Provide detailed, constructive feedback focusing on both strengths and areas for improvement. Offer specific examples for enhancing the algorithm or addressing special cases. Recommend resources like readings, tutorials, or online tools for further exploration. Your feedback should incorporate academic and practical considerations in computer science, suitable for advanced students. Provide guidance in Spanish (Argentina) and assume a supportive and encouraging tone to foster a positive learning environment. Aim to stimulate reflection and initiative, including practical and theoretical recommendations to support academic and professional development. Encourage the examination of case studies or practical examples for a deeper, applied understanding of concepts. Suggest additional resources to enrich learning and promote a problem-solving approach."
            }


            chat_completion = openai.ChatCompletion.create(
                model="gpt-4-turbo-preview",
                messages=[
                    system_instructions,
                    {"role": "user", "content": self.construct_prompt(exercise_content, response)}
                ],
                temperature=0.7,
                max_tokens=1100,
                n=1,
                stop=None
            )

            # Asegurándote de acceder correctamente a la respuesta
            evaluated_response = chat_completion.choices[0].message['content'].strip()
            logger.info("Received evaluation response from OpenAI API.")
            
            return evaluated_response

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return "Error evaluando la respuesta."
            



class Consulta40(Evaluator):
    def __init__(self):
        super().__init__(model_name="gpt-4-turbo-preview")


    def construct_prompt(self, exercise_content, response, evaluation_style="neutral"):
        if not exercise_content or not response:
            logger.error("Received invalid exercise_content or response. GPT40")
            # Devuelve un valor predeterminado o maneja el error adecuadamente
            return "Error: El contenido del ejercicio o la respuesta del estudiante no es válido."
        

        # Construcción específica del prompt para GPT-4
        prompt_introduction = (
            "Soy un asistente de IA diseñado para actuar como un docente virtual en el campo de las ciencias de la computación. "
            "Mi objetivo es ayudarte a entender mejor los conceptos y resolver las dudas que puedas tener sobre los ejercicios propuestos. "
            "Voy a proporcionar explicaciones claras y detalladas, guiarte a través de los pasos lógicos y alentarte en tu proceso de aprendizaje. "
        )

        # Incorporación del contenido del ejercicio y la consulta del estudiante
        exercise_and_student_query = (
            f"Ejercicio:\n{exercise_content}\n\n"
            f"Consulta del estudiante:\n{response}\n\n"
        )

        # Instrucciones para la IA sobre cómo proceder con la asistencia
        assistance_instructions = (
            "Responde a la consulta siguiendo estas pautas, enfocándote en clarificar dudas y fortalecer la comprensión del estudiante. "
            "Si la consulta es sobre un problema específico, desglosa el problema y guía al estudiante hacia la solución con preguntas orientadoras y pistas, en lugar de dar la respuesta directamente. "
            "Si la consulta es conceptual, proporciona una explicación detallada del concepto, con ejemplos que ilustren su aplicación práctica. "
            "Anima al estudiante a seguir explorando el tema y a aplicar el conocimiento de manera creativa. "
            "Recuerda utilizar un lenguaje amigable y accesible, evitando jergas innecesarias, y confirma que cualquier recurso que menciones esté disponible y sea relevante. "
            "Mantén un tono alentador y asegúrate de que el estudiante se sienta apoyado en su proceso de aprendizaje. "
            "Considera la brevedad y la precisión, ajustando la longitud de tu respuesta a la complejidad de la consulta del estudiante."
        )

        
        # Combining all parts into the final prompt
        complete_prompt = f"{prompt_introduction}{exercise_and_student_query}{assistance_instructions}"
        logger.info(f"Constructed prompt for OpenAI API call. : {complete_prompt}")
        return complete_prompt


    # Implementación específica para chat_completion si es diferente

    def evaluate(self, exercise_content, response):
        logger.info(f"Inside Consulta40")

        # Call to construct the prompt with the exercise content and student's response
        # prompt = self.construct_prompt(exercise_content, response)
        # API call to OpenAI
        try:

            system_instructions = {
                "role": "system",
                "content": (
                "Sos una tutora de IA, mujer, asistiendo a estudiantes con sus consultas de ejercicios de ciencias de la computación. "
                "Tu feedback debe incorporar consideraciones académicas y prácticas en informática, adecuadas para estudiantes avanzados. "
                "Guiá en español de Argentina y mantené un tono de apoyo y aliento para fomentar un ambiente de aprendizaje positivo. "
                "Buscá estimular la reflexión y la iniciativa, incluyendo recomendaciones prácticas y teóricas para apoyar el desarrollo académico y profesional. "
                "Alentá la revisión de estudios de casos o ejemplos prácticos para una comprensión aplicada y más profunda de los conceptos. "
                )
            }


            chat_completion = openai.ChatCompletion.create(
                model="gpt-4-turbo-preview",
                messages=[
                    system_instructions,
                    {"role": "user", "content": self.construct_prompt(exercise_content, response)}
                ],
                temperature=0.7,
                max_tokens=500,
                n=1,
                stop=None
            )

            # Asegurándote de acceder correctamente a la respuesta
            evaluated_response = chat_completion.choices[0].message['content'].strip()
            logger.info("Received evaluation response from OpenAI API.")
            
            return evaluated_response

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return "Error evaluando la respuesta."
        


class AnalizadorEjercicios(Evaluator):
    def __init__(self):
        super().__init__(model_name="gpt-4-turbo-preview")


    def construct_prompt(self, exercise_content, evaluation_style="neutral"):
    
        # Construcción específica del prompt para GPT-4
        prompt_introduction = (
            "Estamos analizando ejercicios para estudiantes avanzados en ciencias de la computación.  Basándote en el siguiente detalle del ejercicio:"
        )
        
        
        exercise = (
            f"Ejercicio:\n{exercise_content}\n\n"
        )
        
        
        # Instructions for AI on how to proceed with the evaluation
        evaluation_instructions = (
            "\nGenera un Nombre: Proporciona un nombre único y atractivo para el ejercicio que capte la esencia del desafío y lo haga memorable. Este nombre debe ser breve (una palabra o una frase muy corta) y reflejar el objetivo central o la característica distintiva del problema."
            "\nDescribe en Info: Escribe una descripción muy breve y precisa que explique el núcleo del problema, su objetivo, y cualquier restricción específica o particularidad que lo haga interesante. Limita esta descripción a una o dos oraciones para mantenerla directa y accesible."
        )
        
        # Combining all parts into the final prompt
        complete_prompt = f"{prompt_introduction}{exercise}{evaluation_instructions}"
        logger.info(f"Constructed prompt for OpenAI API call. : {complete_prompt}")
        return complete_prompt


    # Implementación específica para chat_completion si es diferente

    def evaluate(self, exercise_content):
        logger.info(f"Inside AnalizadorEjercicios")

        # Call to construct the prompt with the exercise content and student's response
        # prompt = self.construct_prompt(exercise_content, response)
        # API call to OpenAI
        try:

            # system_instructions para reflejar la tarea
            system_instructions = {
                "role": "system",
                "content": "Eres una inteligencia artificial diseñada para analizar ejercicios de ciencias de la computación. Tu tarea es generar un nombre y una descripción concisa para cada ejercicio basándote en su contenido. El nombre debe ser corto y reflejar la esencia del desafío. La descripción debe ser breve, explicando el objetivo y particularidades del problema. Tu respuesta debe ser en español y orientada a estudiantes avanzados, pero puedes evitar exceso de lenguaje formal para no establecer tanta distancia con los estudiantes."
            }

            chat_completion = openai.ChatCompletion.create(
                model="gpt-4-turbo-preview",
                messages=[
                    system_instructions,
                    {"role": "user", "content": self.construct_prompt(exercise_content)}
                ],
                temperature=0.7,
                max_tokens=1100,
                n=1,
                stop=None
            )

            # Asegurándote de acceder correctamente a la respuesta
            evaluated_response = chat_completion.choices[0].message['content'].strip()
            logger.info("Received evaluation response from OpenAI API.")
            
            return evaluated_response

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return "Error evaluando la respuesta."
