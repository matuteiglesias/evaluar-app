

## EXERCISES ROUTES

from main import configure_logging
import re
import os
import pandas as pd

logger = configure_logging()



def preprocess_latex_for_mathjax(latex_content, exercise_id):
    """
    Preprocesses LaTeX content to make it compatible with MathJax and HTML rendering.
    This function performs the following transformations:
    - Replaces LaTeX emphasis commands (\emph{}, \textit{}, \textbf{}) with their corresponding HTML tags (<em>, <i>, <strong>).
    - Converts LaTeX enumerate environments (\begin{enumerate}, \end{enumerate}) to HTML ordered lists (<ol>, </ol>).
    - Converts LaTeX \item commands to HTML list items (<li>).
    - Ensures proper closing of list items by replacing consecutive <li> tags with properly formatted ones.
    - Converts LaTeX center environments (\begin{center}, \end{center}) to HTML div elements with center alignment.
    - Replaces a placeholder ("% FIGURA") with an HTML <img> tag for embedding an image, using the provided exercise ID to generate the image source path.
    Args:
        latex_content (str): The LaTeX content to preprocess.
        exercise_id (str): The ID of the exercise, used to generate the image source path.
    Returns:
        str: The preprocessed LaTeX content with HTML-compatible formatting.
    """
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



def get_exercise_content(filename, course='tda'):
    """
    Retrieves the content of an exercise file, processes it for rendering, and handles errors gracefully.

    Args:
        filename (str): The name of the exercise file to be loaded. Expected format is 'ID.tex'.
        course (str, optional): The course directory where the exercise file is located. Defaults to 'tda'.

    Returns:
        str: The processed content of the exercise file if successfully loaded, or an error message if the file
        is not found or another error occurs.

    Logs:
        - Logs an info message when attempting to open the file.
        - Logs a debug message upon successfully reading the file content.
        - Logs an error message if the file is not found or if an unexpected error occurs.

    Notes:
        - Assumes the exercise files are stored in a directory structure under 'exercises/{course}'.
        - Extracts the exercise ID from the filename by splitting on the '.' character.
        - Optionally preprocesses the LaTeX content for MathJax rendering using `preprocess_latex_for_mathjax`.
    """
    exercises_dir = os.path.join('exercises', course)
    filepath = os.path.join(exercises_dir, filename)
    logger.info(f"Attempting to open exercise file at path: {filepath}")

    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            content = file.read()
            logger.debug(f"Successfully read content from {filename}")

            # Extrae el ID del ejercicio del nombre del archivo, asumiendo que el formato es 'ID.tex'
            exercise_id = filename.split('.')[0]

            # Opcional: Preprocesamiento para el render con MathJax
            content = preprocess_latex_for_mathjax(content, exercise_id)
            return content
    except FileNotFoundError:
        logger.error(f"File {filename} not found in directory {exercises_dir}.")
        return "Exercise content not found."
    except Exception as e:
        logger.error(f"Unexpected error while reading {filepath}: {e}")
        return "An error occurred while fetching the exercise content."
    


def get_filename_from_exercise_id(exercise_id, course='tda'):
    """
    Retrieves the filename associated with a given exercise ID for a specific course.
    Args:
        exercise_id (int): The ID of the exercise to look up.
        course (str, optional): The course name. Defaults to 'tda'.
    Returns:
        str: The filename corresponding to the given exercise ID.
    Raises:
        FileNotFoundError: If the index file for the specified course does not exist.
        ValueError: If no exercise with the given ID is found in the course index.
    """
    index_path = os.path.join('exercises', course, 'index.csv')
    if not os.path.exists(index_path):
        raise FileNotFoundError(f"No index file found for course: {course}")

    df = pd.read_csv(index_path)
    match = df.loc[df['id'] == int(exercise_id), 'file']
    
    if match.empty:
        raise ValueError(f"No exercise found with id {exercise_id} in course {course}")
    
    return match.values[0]


def get_exercise_id_from_filename(filename, course='tda'):
    """
    Retrieves the exercise ID associated with a given filename from the course's index file.
    Args:
        filename (str): The name of the exercise file to look up.
        course (str, optional): The course name to locate the index file. Defaults to 'tda'.
    Returns:
        int: The ID of the exercise corresponding to the given filename.
    Raises:
        FileNotFoundError: If the index file for the specified course does not exist.
        ValueError: If no exercise with the given filename is found in the index file.
    """
    index_path = os.path.join('exercises', course, 'index.csv')
    if not os.path.exists(index_path):
        raise FileNotFoundError(f"No index file found for course: {course}")

    df = pd.read_csv(index_path)
    match = df.loc[df['file'] == filename, 'id']
    
    if match.empty:
        raise ValueError(f"No exercise found with filename {filename} in course {course}")
    
    return match.values[0]
