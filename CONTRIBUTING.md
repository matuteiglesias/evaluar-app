


# 🤝 Cómo Contribuir

¡Gracias por tu interés en colaborar con la plataforma de consultas!  
Este documento te guía paso a paso para contribuir de manera efectiva, tanto si querés sumar ejercicios como si querés trabajar en la lógica del sistema.

---

## 🧱 Tipos de contribución posibles

| Tipo de aporte               | Descripción                                                                 |
|-----------------------------|-----------------------------------------------------------------------------|
| 🧑‍🏫 **Agregar una materia** | Crear una nueva carpeta con ejercicios `.tex` y su índice `index.csv`.      |
| 🧪 **Sumar ejercicios**      | Proponer nuevos ejercicios para materias ya existentes.                     |
| 🧠 **Mejorar UX / diseño**   | Propuestas de estilo, layout, interacciones, accesibilidad.                 |
| 🤖 **IA y feedback**         | Mejorar el motor de evaluación automática basado en LLMs.                   |
| 🔧 **Desarrollo Backend**    | Mejorar rutas, parsing de archivos, autenticación, modularidad.             |
| 🧾 **Documentación**         | Ayudar a que nuevas personas entiendan cómo participar y extender el sistema.|

---

## 🚀 Para empezar rápido (modo colaborador)

1. **Cloná el repositorio**

```bash
git clone https://github.com/matuteiglesias/evaluar-app.git
cd evaluar-app
```

2. **Configurá tu entorno virtual (Python 3.10+)**

```bash
python -m venv env
source env/bin/activate  # En Windows: env\Scripts\activate
```


3. **Instalá las dependencias**

```bash
pip install -r env/requirements.txt
```

4. **Copiá y completá las variables de entorno**

```bash
cp env.template .env
# luego editá el archivo con tus claves necesarias
```

5. **Ejecutá la app localmente**

```bash
export FLASK_APP=main.py
flask run
```

Nota:

Regeneracion de docs

```bash
PYTHONPATH=. python3 -m pdoc ./main.py ./routes ./services ./llm ./models --output-dir docs
```



---

## 📂 Estructura para agregar una nueva materia

Para agregar una nueva materia, seguí este esquema:

```
exercises/
└── nombre_de_la_materia/
    ├── 101.tex
    ├── 102.tex
    ├── ...
    └── index.csv
```

El archivo `index.csv` debe tener las siguientes columnas:


|id|name|info|file|section|
|----------|------------------|----------------------------------------|-----------------|------------------|
101|Algoritmo Subconjuntos|Explora backtracking para sumas de subconjuntos|101.tex|1
102|Mágicos|Construcción de cuadrados mágicos|102.tex|1


- El campo `section` es usado para agrupar visualmente los ejercicios en la UI.
- La columna `info` sirve para mostrar una breve descripción contextual del ejercicio.

---

## 🌐 Acceder a tu curso en la plataforma

Una vez agregados los ejercicios, se podrá acceder a ellos con:

```
http://localhost:5000/course?course=nombre_de_la_materia
```

Por ejemplo:

```
http://localhost:5000/course?course=tda
http://localhost:5000/course?course=compiladores
```

---

## 💬 Sugerencias y cambios mayores

Si querés proponer una nueva funcionalidad o cambio en la estructura del sistema, bienvenidx:

1. Abri un [issue](https://github.com/<repo>/issues) explicando tu idea.
o bien...
2. Envia un pull request con el cambio documentado y razonado.

---

## ⚠️ Buenas prácticas

* No subir claves ni archivos `.env` al repositorio.
* Asegurate de que el código corra localmente antes de hacer push.
* Usá nombres de variables y archivos claros y consistentes.
* Los `.tex` deben estar escritos en LaTeX bien formado.
* Todo contenido nuevo debe ir acompañado de un `index.csv`.

---

## 📬 ¿Dudas?

Podés escribir a Matías directamente o dejar un issue abierto.
¡Gracias por sumarte a este proyecto colaborativo!
