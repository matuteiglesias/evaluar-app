# Journey route traceability

| Journey | Routes | Services/boundaries | External dependencies | Data written | Executable tests |
|---|---|---|---|---|---|
| Authenticate and choose a course | `/login`, `/login/callback`, `/`, `/get_courses`, `/course` | `services.identity`, `models.user`, `exercise_repository` | Google OAuth; course filesystem | Local user/session only | `test_journey_authenticate_and_choose_course` |
| Browse a specific exercise | `/course`, `/get_exercises`, `/exercises/<course>/<filename>`, `/tikzpics/<filename>` | `exercise_repository`, `safe_rendering`, content inventory assumptions | Course filesystem; local assets | None | `test_journey_browse_course_sections_and_exact_exercise` |
| Ask for AI guidance | `/exercises/<course>/<filename>`, `/submit_answer` | tutor boundary, `exercise_repository`, `safe_rendering`, persistence, clock, ID generator | OpenAI in legacy runtime; Firestore compatibility store | One `interaction_records` compatibility record | `test_journey_ai_guidance_uses_scoped_content_and_persists` |
| Rate a response | `/submit_answer`, `/submit-feedback` | persistence, clock, ID generator, response session correlation | Firestore compatibility store | One `user_feedback` compatibility record | `test_journey_feedback_is_bound_to_one_response` |
| Generic teacher help | `/request-teacher-time`, `/confirmation` | `exercise_repository`, persistence, clock, ID generator | Firestore compatibility store; **no teacher lookup** | One open unassigned `tickets` compatibility record | `test_journey_generic_teacher_packet_has_no_teacher_assignment` |

All named tests use Flask's test client, temporary course trees, a fake identity,
in-memory persistence, deterministic tutor output, deterministic IDs, and a fixed
clock. No traceability test resolves a real credential or network client.

The Firestore collection names above describe current compatibility writes only.
Future rows belong in PostgreSQL under a separately reviewed schema. The GCP
Firestore data remains untouched pending authorized export and archival.
