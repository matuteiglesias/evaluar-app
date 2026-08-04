# Cierre del sprint — fases 2 a 4

## Identificación del candidato

- **Rama de recuperación:** `recovery/phase4-support-no-binaries`
- **Commit verificado:** se captura de forma reproducible con `git rev-parse HEAD` en
  `artifacts/sprint-verification.txt` al completar `make verify-sprint`.
- **Cabezas de migración esperadas:**
  - `courses.0001_initial`
  - `identity.0001_initial`
  - `support.0002_alter_humanhelpticket_priority_and_more`
  - `tutoring.0004_outboxevent_claim_expires_at_outboxevent_claimed_at_and_more`

El SHA no se incrusta manualmente en este archivo porque un documento dentro del mismo commit no
puede contener el SHA de ese commit. El artefacto de verificación es la fuente autoritativa y se
genera después de hacer checkout del candidato exacto.

## Gate reproducible

Ejecutar:

```bash
make verify-sprint
```

El objetivo ejecuta, en orden:

1. pruebas de contenido e identidad de fase 2;
2. pruebas de tutoría, cola, adaptadores, operaciones y UI de fase 3;
3. pruebas de soporte y notificaciones de fase 4;
4. Ruff lint y formato;
5. mypy sobre `src/evaluar`;
6. comprobación de drift de migraciones;
7. prueba de claims concurrentes contra PostgreSQL;
8. build de la imagen de producción y captura de su image ID;
9. importación, dentro de la imagen, de dependencias web, worker, Agent Framework y Cloud Tasks;
10. migraciones en contenedor y smoke test de `/health/ready`.

## Resultados registrados en este candidato

| Comprobación | Resultado |
| --- | --- |
| Ruff | Aprobado |
| Ruff format | Aprobado, 137 archivos |
| mypy `src/evaluar` | Aprobado, 82 archivos |
| Soporte + notificaciones, sin red | Aprobado, 21 pruebas |
| Drift de migraciones | Aprobado |
| PostgreSQL claim concurrente | Pendiente de un host con Docker/PostgreSQL |
| Imagen de producción | Pendiente de un host con Docker |
| Migración y health smoke en contenedor | Pendiente de un host con Docker |

## Runtime de fase 3

La evidencia del entorno desplegable debe adjuntar la salida de:

```bash
python manage.py tutoring_operational_status --json
python manage.py check_tutoring_release --strict
```

Esa salida contiene el prompt activo y la evidencia operacional del modelo. Las dependencias de
construcción están fijadas a `agent-framework-core==1.13.0` y
`agent-framework-openai==1.12.0`. El modelo solicitado es propiedad de la versión de prompt activa,
no de este documento, para no presentar configuración de desarrollo como estado de producción.

## Evidencia de soporte

- La prueba PostgreSQL `tests/test_support_postgres.py` lanza dos claims simultáneos con conexiones
  independientes y exige un ganador, una asignación activa y un solo evento `claimed`.
- Las pruebas sin red cubren idempotencia, propiedad, coherencia de curso, referencias de tutoría,
  transiciones, membresías, privacidad de notas, eventos append-only, mensajes, asignaciones y
  outbox.
- Una entrega de notificación fallida vuelve a `pending`, conserva `last_error` e incrementa el
  contador de intentos sin modificar el ticket ya confirmado.

## Limitaciones conocidas

- El adaptador concreto de correo no forma parte del dominio: el dispatcher acepta un puerto
  `NotificationSender`. La selección de proveedor y credenciales corresponde al despliegue.
- No se añaden SMS, chat, routing automático, analítica docente, streaming ni asignación automática.
- El gate completo requiere Docker y PostgreSQL. Un resultado SQLite no sustituye la prueba de
  concurrencia marcada `postgres`.
- Los tests `live` de tutoría siguen fuera del gate no facturable y requieren autorización explícita.

## Rollback

1. Detener web y dispatchers para impedir nuevas escrituras.
2. Conservar primero un backup PostgreSQL y el identificador de la imagen actual.
3. Volver a desplegar la imagen anterior conocida como buena.
4. No revertir destructivamente tickets, mensajes, asignaciones, eventos ni referencias históricas.
5. Si la aplicación anterior no conoce las tablas `support_*`, dejarlas en la base: son aditivas y no
   interfieren con fases 2 o 3.
6. Reanudar web y worker de fase 3 y ejecutar `/health/ready` y `check_tutoring_release --strict`.
7. Investigar o reintentar notificaciones pendientes después de restaurar el servicio; nunca borrar
   el outbox como mecanismo de rollback.

## Aceptación de extremo a extremo

La validación manual final debe conservar identificadores durante todo el recorrido:

1. estudiante autenticado abre un `ExerciseVersion` autorizado e inmutable;
2. envía una respuesta y se conserva el `TutoringSubmission` exacto;
3. el worker publica la orientación asíncrona y se conserva el `TutoringResponse` exacto;
4. el estudiante valora esa respuesta;
5. crea un ticket referenciando esa respuesta;
6. un docente elegible reclama el ticket;
7. el docente inicia y responde;
8. el estudiante lee únicamente mensajes para participantes y contesta;
9. el docente resuelve;
10. se verifican el historial completo de asignaciones, eventos y outbox.

## Evaluación go/no-go

**NO-GO provisional en este entorno.** Las comprobaciones locales y sin red están aprobadas, pero no
se debe declarar cerrado el sprint hasta que `make verify-sprint` termine en un runner con Docker y
PostgreSQL, produzca `artifacts/sprint-verification.txt`, capture el image ID y apruebe la prueba de
claims concurrentes y el smoke test del contenedor. Con esas comprobaciones aprobadas y sin nuevas
limitaciones, la evaluación pasa a **GO**.
