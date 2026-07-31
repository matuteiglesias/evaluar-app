## EXERCISES ROUTES

from main import configure_logging
import re

logger = configure_logging()


def preprocess_latex_for_mathjax(latex_content, exercise_id):
    r"""
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
    latex_content = re.sub(r"\\emph\{(.*?)\}", r"<em>\1</em>", latex_content)

    # Reemplaza \textit{} con <i></i>
    latex_content = re.sub(r"\\textit\{(.*?)\}", r"<i>\1</i>", latex_content)

    # Reemplaza \textbf{} con <strong></strong>
    latex_content = re.sub(r"\\textbf\{(.*?)\}", r"<strong>\1</strong>", latex_content)

    # A robust solution would require actual LaTeX parsing
    latex_content = latex_content.replace(r"\begin{enumerate}", "<ol>")
    latex_content = latex_content.replace(r"\end{enumerate}", "</ol>")
    latex_content = latex_content.replace(r"\item", "<li>")
    # Close the list item
    latex_content = latex_content.replace(r"</li><li>", "</li>\n<li>")
    latex_content = latex_content.replace(
        r"\begin{center}", '<div class="exercise-center">'
    ).replace(r"\end{center}", "</div>")

    # Reemplaza el marcador con la etiqueta img HTML
    figure_placeholder = "% FIGURA"
    # img_html = f'<img src="/tikzpics/{exercise_id}.png" alt="Figura para el ejercicio {exercise_id}" />'
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "", str(exercise_id))
    img_html = (
        f'<img src="/tikzpics/{safe_id}.png" '
        f'alt="Figura para el ejercicio {safe_id}" class="exercise-figure">'
    )
    latex_content = latex_content.replace(figure_placeholder, img_html)

    return latex_content
