# 📘 Plataforma de Consultas Interactivas

Bienvenidos a una plataforma abierta y colaborativa para **gestionar ejercicios, consultas y tutorías** en materias universitarias de forma organizada, escalable y eficiente.

> ⚙️ Pensada para docentes, estudiantes y ayudantes que quieren mejorar la experiencia de enseñanza-aprendizaje en cursos técnicos.

---

## 🎯 ¿Qué resuelve esta plataforma?

Muchas materias tienen los mismos problemas:
- Los ejercicios están dispersos, poco estructurados o sólo en PDF.
- Las consultas de estudiantes se pierden o se responden tarde.
- Es difícil escalar la dinámica de tutoría con muchos alumnos.
- No hay forma sencilla de colaborar o iterar sobre el contenido.

Esta plataforma ofrece una solución:
- ✅ Ejercicios organizados por curso y sección, en `.tex` y con metadata.
- ✅ Visualización clara, con separación por secciones temáticas.
- ✅ Formulario integrado para consultas vinculadas a ejercicios.
- ✅ Capacidad de feedback automatizado (IA).
- ✅ Sistema adaptable: se pueden sumar nuevas materias fácilmente.

---

## 🖼️ Capturas / Demo

_(agregar capturas reales del home, selector de curso y tabla de ejercicios)_

- Página de bienvenida con selector de materia:
  ![Pantalla de inicio](docs/assets/home.png)

- Visualización de ejercicios y acceso a consultas:
  ![Ejercicios cargados](docs/assets/tabla-ejercicios.png)

**Docs:** https://matuteiglesias.github.io/evaluar-app/

---

## 🙌 ¿Cómo podés contribuir?

Buscamos colaboración en múltiples frentes. Algunas formas concretas:

| Tipo de contribución             | Qué implica                                                                 |
|----------------------------------|------------------------------------------------------------------------------|
| 📚 **Agregar una materia nueva** | Crear una carpeta con ejercicios `.tex` + un `index.csv`                   |
| 🧠 **Sumar ejercicios**          | Proponer nuevos problemas a materias existentes                             |
| 🖌️ **Mejoras de diseño**         | Mejorar el layout, estilos, UX de la plataforma                             |
| 💬 **Corrección de errores**     | Fixes de bugs o mejoras en scripts / rutas Flask                            |
| 🤖 **IA & feedback automático**  | Ayudá a mejorar el sistema de evaluación automatizada por IA               |
| 📝 **Documentación**             | Ayudá a que otros puedan contribuir más fácilmente                          |

---

## 📎 Empezá ahora

👉 Leé el archivo [CONTRIBUTING.md](CONTRIBUTING.md) para saber cómo agregar tu curso o contribuir de otra manera.

Podés testear todo localmente en minutos. No necesitás experiencia avanzada en desarrollo.

---

## 💡 Filosofía

Creemos que:
- La docencia merece mejores herramientas.
- Las plataformas pueden ser simples, accesibles y libres.
- El contenido y el código pueden evolucionar colaborativamente.

¡Sumate y hacé que tu materia sea parte del cambio!

---

## 🧑‍💻 Créditos y comunidad

Esta plataforma fue creada por Matías Iglesias y está abierta a mejoras.  
Licencia MIT.  
¿Tenés ideas? ¿Querés sumar tu cátedra?  
> 📬 Contacto: 'mniglesias@dc.uba.ar'


## Phase 2 Django application

The production foundation lives in `src/evaluar`. It provides Google OpenID Connect sign-in,
course-scoped memberships, immutable versioned exercises, and read-only access to the single
published release for each course. It intentionally contains no AI execution or teacher workflow.

```bash
uv sync
uv run python manage.py migrate
DJANGO_SETTINGS_MODULE=config.settings.local uv run python manage.py runserver
```

Set `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `GOOGLE_CLIENT_ID`, and
`GOOGLE_CLIENT_SECRET` in production. Run with `config.settings.production` (the WSGI/ASGI
default); production startup rejects missing secrets and enables HTTPS cookie and HSTS settings.

The framework-independent compiler is available as `content_pipeline.compile_content(root)`. It
returns a canonical bundle with checksums and formal validation findings; content import/publishing
should reject bundles whose `valid` property is false.

### Content release workflow

Course and content records use UUID primary keys. Imported identifiers remain course-scoped external
keys such as `tda:101`, while deterministic author-facing slugs are generated from exercise titles.
Content is compiled outside request handling and publishing is checksum-verified and atomic:

```bash
python manage.py validate_content ./content
python manage.py build_content_bundle ./content --output ./build/content
python manage.py publish_content ./build/content
```

Re-publishing the same bundle is idempotent. Unchanged immutable versions may be included in a new
complete release without being copied. HTTP views resolve only database identities and only expose
versions included in the course's active publication.

### PostgreSQL and container startup

Development remains possible without Docker using the local SQLite default. To run the production
shape with PostgreSQL, use `docker compose up --build`. The image migrates an empty database before
starting Gunicorn and exposes `/health/live` and database-backed `/health/ready` probes.
