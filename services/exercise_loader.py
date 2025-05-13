

## EXERCISES ROUTES

from main import configure_logging
import re
import os
import pandas as pd

logger = configure_logging()



def get_filename_from_exercise_id(exercise_id):
    # Extract the filename from the exercise ID
    df = pd.read_csv('exercises/exercises.csv')
    filename = df.loc[df.id == int(exercise_id), 'file'].values[0]
    return filename

def get_exercise_id_from_filename(filename):
    # Extract the exercise ID from the filename
    df = pd.read_csv('exercises/exercises.csv')
    id = df.loc[df.file == filename, 'id'].values[0]
    return id


def preprocess_latex_for_mathjax(latex_content, exercise_id):
    # Reemplaza \emph{} con <em></em>
    latex_content = re.sub(r'\\emph\{(.*?)\}', r'<em>\1</em>', latex_content)
    
    # Reemplaza \textit{} con <i></i>
    latex_content = re.sub(r'\\textit\{(.*?)\}', r'<i>\1</i>', latex_content)
    
    # Reemplaza \textbf{} con <strong></strong>
    latex_content = re.sub(r'\\textbf\{(.*?)\}', r'<strong>\1</strong>', latex_content)
        
    # A robust solution would require actual LaTeX parsing
    latex_content = latex_content.replace(r'\begin{enumerate}', '<ol>')
    latex_content = latex_content.replace(r'\end{enumerate}', '</ol>')
    latex_content = latex_content.replace(r'\item', '<li>')
    # Close the list item
    latex_content = latex_content.replace(r'</li><li>', '</li>\n<li>')
    latex_content = latex_content.replace(r'\begin{center}', '<div style="text-align: center;">').replace(r'\end{center}', '</div>')

    # Reemplaza el marcador con la etiqueta img HTML
    figure_placeholder = "% FIGURA"
    # img_html = f'<img src="/tikzpics/{exercise_id}.png" alt="Figura para el ejercicio {exercise_id}" />'
    img_html = f'<img src="/tikzpics/{exercise_id}.png" alt="Figura para el ejercicio {exercise_id}" style="max-width: 80%; height: auto; display: block; margin-left: auto; margin-right: auto;" />'
    latex_content = latex_content.replace(figure_placeholder, img_html)

    return latex_content

# @app.route('/exercises/<filename>')
def get_exercise_content(filename):
    # Asumiendo que tus archivos de texto de ejercicios están almacenados en un directorio llamado 'exercises'
    exercises_dir = 'exercises'
    filepath = os.path.join(exercises_dir, filename)
    logger.info(f"Attempting to open exercise file at path: {filepath}")

    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            content = file.read()
            logger.debug(f"Successfully read content from {filename}")

            # Extrae el ID del ejercicio del nombre del archivo, asumiendo que el formato es 'ID.tex'
            exercise_id = filename.split('.')[0]

            # Opcional: Envuelve el contenido LaTeX en delimitadores aquí si es necesario
            content = preprocess_latex_for_mathjax(content, exercise_id)
            return content
    except FileNotFoundError:
        logger.error(f"File {filename} not found in directory {exercises_dir}.")
        return "Exercise content not found."
    except Exception as e:
        logger.error(f"An unexpected error occurred while trying to read {filename}: {e}")
        return "An error occurred while fetching the exercise content."
    
