
### Documentación para Usuarios

#### Introducción

**Visión General de la Plataforma**

Esta plataforma educativa está diseñada para ofrecer a estudiantes y docentes una herramienta interactiva de aprendizaje y enseñanza. A través de ejercicios prácticos y feedback inmediato, busca mejorar la comprensión de conceptos complejos y fomentar el desarrollo de habilidades de resolución de problemas.

**Propósito y Público Objetivo**

Dirigida principalmente a estudiantes de informática y áreas relacionadas, la plataforma es también una valiosa herramienta para docentes que buscan complementar sus métodos de enseñanza con recursos interactivos. Adecuada para diversos niveles de conocimiento, desde principiantes hasta avanzados.


#### Requisitos del Sistema

Para acceder a nuestra plataforma educativa, lo único que necesitas es:

- **Un navegador web actualizado:** Recomendamos el uso de Google Chrome, Mozilla Firefox, o Safari para una experiencia óptima.
- **Conexión a internet:** Para poder acceder a los contenidos y funciones de la plataforma.

#### Cómo Acceder a la Plataforma

La plataforma se accede a través de una URL que te será proporcionada por tu institución educativa o por tu docente. No hay necesidad de instalar ningún software adicional, todo lo que necesitas es tu navegador web y conexión a internet.

#### Navegando por la Plataforma

##### Vista General del Tablero

(no implementado)

Una vez que ingreses a la plataforma, te encontrarás con un tablero diseñado de manera intuitiva, donde podrás ver:

- **Unidades o Temas:** Un listado de las diferentes unidades o temas disponibles para estudiar.
- **Ejercicios y Actividades:** Acceso directo a ejercicios y actividades diseñadas para reforzar tu aprendizaje.
- **Tu Progreso:** Información sobre tu progreso en ejercicios previos, incluyendo calificaciones y retroalimentación.

#### Cómo Localizar y Seleccionar Ejercicios

Para empezar a trabajar en un ejercicio específico:

1. **Selecciona la Unidad o Tema:** En el tablero principal, navega hasta la sección que corresponde a la unidad o tema que te interesa.
2. **Explora los Ejercicios Disponibles:** Dentro de cada sección encontrarás una lista de ejercicios. Puedes leer un breve resumen de lo que trata cada uno para decidir cuál te gustaría intentar resolver.
3. **Accede al Ejercicio:** Una vez que selecciones un ejercicio, encontrarás instrucciones detalladas para su resolución. En algunos casos, también podrás acceder a consejos o pistas que te ayudarán a avanzar si te encuentras atascado.

Esta guía inicial te ayudará a familiarizarte con la plataforma y a comenzar a explorar los diversos recursos educativos que ofrece. Recuerda que la práctica constante y la exploración activa son claves para un aprendizaje efectivo.



Para clarificar tu inquietud y estructurar mejor la documentación técnica (para desarrolladores), vamos a dividirla en secciones clave y luego abordaremos tus preguntas específicas sobre el manejo de las claves API y la autenticación con Google. 


### Documentación Técnica para Desarrolladores

Esta documentación está destinada a guiar a los desarrolladores en la instalación, configuración y despliegue de la aplicación. Asegúrese de seguir cada paso cuidadosamente para configurar el entorno de desarrollo o producción adecuadamente.

#### Instalación del Software y sus Dependencias

1. **Clonar el Repositorio**: Comience clonando el repositorio de la aplicación a su máquina local o servidor.

   ```bash
   git clone <url-del-repositorio>
   cd <directorio-del-proyecto>
   ```

2. **Entorno Python**: Asegúrese de tener Python 3.8 o superior instalado. Se recomienda utilizar un entorno virtual para la instalación de las dependencias.

   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows use `venv\Scripts\activate`
   ```

3. **Instalar Dependencias**: Instale todas las dependencias requeridas utilizando `pip`.

   ```bash
   pip install -r requirements.txt
   ```

#### Configuración del Entorno

1. **Variables de Entorno**: Duplique el archivo `.env.example` proporcionado en el repositorio y renómbrelo a `.env`. Rellene las variables de entorno necesarias.

   ```plaintext
   OPENAI_API_KEY=your_openai_api_key_here
   GOOGLE_CLIENT_ID=your_google_client_id_here
   GOOGLE_CLIENT_SECRET=your_google_client_secret_here
   OAUTHLIB_INSECURE_TRANSPORT=1  # Solo para propósitos de desarrollo
   ```

2. **Configuración Adicional**: Si la aplicación requiere configuraciones adicionales, asegúrese de revisar y ajustar los archivos de configuración correspondientes.

#### Uso de Docker (Opcional)

Si prefiere desplegar la aplicación utilizando Docker, siga estos pasos:

1. **Construir la Imagen Docker**: Asegúrese de tener Docker instalado y luego construya la imagen de la aplicación.

   ```bash
   docker build -t nombre-de-tu-aplicacion .
   ```

2. **Ejecutar el Contenedor**: Inicie un contenedor basado en la imagen creada. Asegúrese de pasar las variables de entorno necesarias.

   ```bash
   docker run -d -p 5000:5000 --env-file .env nombre-de-tu-aplicacion
   ```

#### Iniciar la Aplicación

1. **Directamente en su Entorno**:

   Para iniciar la aplicación directamente en su entorno, ejecute:

   ```bash
   flask run
   ```

   Esto iniciará el servidor de desarrollo de Flask y la aplicación estará accesible en `http://localhost:5000`.

2. **Utilizando Docker**:

   Si ha optado por usar Docker, el contenedor iniciado en los pasos anteriores ya debería estar ejecutando la aplicación y accesible en `http://localhost:5000`.

#### Soporte y Contribuciones

Para cualquier problema, pregunta o contribución, por favor abra un issue en el repositorio de GitHub o envíe un pull request con sus mejoras o correcciones.

Siguiendo estas instrucciones, debería ser capaz de configurar y ejecutar la aplicación en su entorno de desarrollo o producción. Recuerde mantener seguras sus claves API y credenciales, y nunca las suba a repositorios públicos.

