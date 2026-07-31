# Five essential user journeys

Every intended exercise identity below includes both course and exercise ID.

## 1. Authenticate and choose a course

- **Actor:** Student with an eligible Google identity.
- **Preconditions:** Application configuration is valid; identity provider is
  available; at least one validated course index exists.
- **Input:** Login action, provider callback, then selected `course_slug`.
- **Route sequence:** `GET /login` → provider → `GET /login/callback` → `GET /`
  → `GET /get_courses` → `GET /course?course=<slug>`.
- **Domain identity:** Provider subject identifies the student; course slug
  identifies the selected content namespace.
- **External dependencies:** Google OAuth through the identity boundary; local
  filesystem content inventory.
- **Persistence effects:** Local session stores subject, name, email, and picture.
  No durable course selection is currently written.
- **Success output:** Authenticated home page, sorted course list, and course page.
- **Failures:** Invalid/unverified identity or provider failure is controlled;
  anonymous protected-route access redirects; malformed course content is absent
  or produces not-found through content routes.
- **Privacy-sensitive fields:** Provider subject, email, name, profile picture,
  session cookie.
- **Known defects:** Course selection is client/query-string state and is not
  server-side enrollment; callback creates users in a process-local legacy model.
- **Classification:** Verified identity and authenticated access are intended;
  process-local user storage and unrestricted course membership are merely observed.

## 2. Browse a specific exercise

- **Actor:** Authenticated student.
- **Preconditions:** Selected course has a valid index; exact row and `.tex` file exist.
- **Input:** Course slug and indexed filename/ID.
- **Route sequence:** `GET /course?course=<slug>` →
  `GET /get_exercises?course=<slug>` → `GET /exercises/<course>/<file>`.
- **Domain identity:** `course_slug:exercise_id`; filename must agree with its index row.
- **External dependencies:** Read-only course filesystem and referenced local assets.
- **Persistence effects:** None.
- **Success output:** Metadata grouped by `section` in the browser and safely
  rendered exact exercise content with validated local figure paths.
- **Failures:** Unknown/unsafe course, missing index/row/file, and path escape are
  404; unsafe HTML/TeX is sanitized rather than accepted as desired behavior.
- **Privacy-sensitive fields:** Authentication session only.
- **Known defects:** Grouping is client-side; no enrollment authorization exists;
  some inventoried HTML tables exceed the renderer allowlist.
- **Classification:** Indexed safe content resolution is intended. Client-only
  grouping and universal authenticated access are observed legacy behavior.

## 3. Ask for AI tutoring guidance

- **Actor:** Authenticated student viewing one immutable exercise identity.
- **Preconditions:** AI enabled; indexed exercise exists; bounded nonblank question;
  tutor and persistence dependencies available.
- **Input:** `course`, `exercise_id`, and question within configured length.
- **Route sequence:** Exercise page → `POST /submit_answer`.
- **Domain identity:** `course_slug:exercise_id` plus generated `response_id`.
- **External dependencies:** Tutor/LLM boundary and operational persistence boundary.
- **Persistence effects:** One interaction containing response ID, course, exercise
  ID, student identity, question, guidance, and timestamp. Session holds the same
  response correlation state for rating.
- **Success output:** Sanitized guidance page with a non-editable hidden response ID.
- **Failures:** Invalid input 400; missing exercise 404; disabled AI 503; model
  failure 502 with no interaction; persistence failure 503 and correlation state
  cleared. It is ambiguous whether unpersisted generated guidance should instead
  be shown; this baseline chooses the controlled failure.
- **Privacy-sensitive fields:** Stable user ID, name, question, model response,
  exercise activity and timestamp.
- **Known defects:** Legacy evaluator language suggests grading/evaluation rather
  than a settled tutoring-only policy.
- **Classification:** Course-scoped input and explicit persistence outcome are
  intended; exact legacy model behavior is merely observed.

## 4. Rate a particular AI response

- **Actor:** Authenticated student who just received one recorded response.
- **Preconditions:** Session correlation state exists and matches submitted
  response ID, course, and exercise ID.
- **Input:** Bounded nonblank feedback, `response_id`, course, exercise ID.
- **Route sequence:** Successful `/submit_answer` page → `POST /submit-feedback`.
- **Domain identity:** Response ID linked to `course_slug:exercise_id`.
- **External dependencies:** Operational persistence boundary.
- **Persistence effects:** One feedback record with feedback ID, response ID,
  course/exercise, student identity, exact generated response, and timestamp;
  correlation state is consumed after success.
- **Success output:** JSON success message.
- **Failures:** Missing input 400; unknown exercise 404; mismatched/stale/already
  rated response 409 with no write; persistence failure 500 and state retained for retry.
- **Privacy-sensitive fields:** Student ID/name, free-text feedback, generated
  response, activity identity and timestamp.
- **Known defects repaired:** Legacy feedback trusted a mutable session string and
  could silently attach stale content. That vulnerability is not contractual.
- **Classification:** Exact response correlation and duplicate rejection are intended.

## 5. Escalate to generic teacher help

- **Actor:** Authenticated student seeking human attention.
- **Preconditions:** Indexed exercise exists; bounded nonblank question;
  persistence is available.
- **Input:** Course, exercise ID, and teacher-help question.
- **Route sequence:** Feedback/exercise context → `POST /request-teacher-time` →
  `GET /confirmation`.
- **Domain identity:** `course_slug:exercise_id` plus generated teacher packet ID.
- **External dependencies:** Operational persistence only; no teacher roster.
- **Persistence effects:** Exactly one open packet containing packet ID, course,
  exercise ID, student identity/contact, question, fixed timestamp, and explicit
  `assignment=unassigned`.
- **Success output:** Confirmation and downloadable packet contain the same packet
  ID and course-scoped exercise identity.
- **Failures:** Missing/overlong input 400; missing exercise 404; persistence
  failure 500 and no confirmation.
- **Privacy-sensitive fields:** Student ID, name, email, question, activity and timestamp.
- **Known defects repaired:** Historical load-based assignment counted tickets and
  queried a teacher dataset. Intended packets are generic and never assign a teacher.
- **Classification:** Generic unassigned help packet is intended. Historical
  teacher selection is documented legacy behavior only.
