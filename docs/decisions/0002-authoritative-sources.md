# ADR 0002: Authoritative sources by data family

- **Status:** Accepted for migration planning; owner approvals remain where marked
- **Date:** 2026-07-31
- **Supersedes:** The unresolved future-authority portion of ADR 0001

## Evidence and confidence

This decision uses the static Firestore collection map/profile, the immutable
content manifest, content issue and authority reports, journey contracts, current
source, and fake-adapter tests. There is **no live Firestore export manifest** in
the repository. Firestore counts, runtime-only collections/subcollections,
missing-field rates, timestamps, and record completeness therefore remain unknown.
No raw Firestore data was inspected or committed.

Repository evidence is stronger: the manifest records 2 course directories, 110
indexed exercise rows and bodies, and 7 referenced canonical exercise images.
It also records four cross-course repeated numeric IDs, five duplicate-body hash
groups, and four renderer/content conflicts. Those warnings do not invalidate the
bytes; they prohibit silently merging or normalizing them.

## Decision principles

1. Existence proves provenance, not migration need or current authorization.
2. Exercise identity is always `course_slug:exercise_id`.
3. Historical authority answers “what legacy state recorded.” Operational
   authority answers “what the future system may rely on now.” They may differ.
4. Git controls authored source; PostgreSQL controls future operational state;
   Google proves external identity; the institution controls academic authority.
5. Firestore remains historical evidence, is not a future runtime database, and
   must not be destroyed. Its verified export will be encrypted archival evidence.
6. No stale roster, email, ticket assignment, or historical activity grants a role.

## Authority and disposition matrix

| Data family | Current historical authority | Future operational authority | Classification and decision |
|---|---|---|---|
| Courses | Git course directories/indexes, with inventory conflicts noted | Git for authored course identity/content; PostgreSQL only for publication/runtime settings | **Migrate in full** as Git source. Preserve slugs. Institution owner must decide whether `demo_course` is publishable or only a fixture. |
| Exercise metadata | Git `index.csv` rows and immutable row hashes | Git | **Migrate in full** without ID normalization. PostgreSQL may cache, never silently override, Git-authored metadata. |
| Exercise bodies | Indexed Git `.tex` bytes and content hashes | Git | **Migrate in full**. Resolve duplicate and renderer conflicts editorially; never merge merely because hashes match. |
| Exercise images | Referenced `tikzpics/` bytes/hashes | Git or Git-controlled artifact storage | **Migrate in full** for the 7 referenced images. Documentation images are not exercise authority. |
| Google identities | Google subject and verified claims at authentication time | Google for authentication; PostgreSQL stores the stable subject link and local state | **Reconstruct** local links on verified login. Do not copy tokens. Domain/eligibility policy requires institution approval. |
| Application users | Process-local `models.user` plus identity claims; no durable user collection evidenced | PostgreSQL | **Reconstruct**, then **migrate selectively** only if a verified legacy user source appears. Never infer active status or roles from names/emails. |
| Teacher roster | Firestore `teachers` is historical roster evidence only; live content/count unknown | Institution-approved staff authority; PostgreSQL only if named staff features later require it | **Archive only** by default. **Do not migrate stale authorization.** Reconstruct any future staff role from the institution authority. |
| Course memberships | No legacy source found | Institution policy/roster feeding PostgreSQL | **Reconstruct**. Owner/institution must define enrollment, staff override, lifecycle, and audit rules. |
| AI interaction records | Firestore `interaction_records`, if present | PostgreSQL for new operational interactions | Legacy records are **archive only** by default; **migrate selectively** only to an approved de-identified analytical dataset. Counts and retention are unresolved. |
| AI responses | Embedded in legacy interaction/feedback records, if present | PostgreSQL, linked to response ID and interaction | Same as interactions: **archive only** by default; selective de-identified analytics only with approval. Do not manufacture missing model/prompt metadata. |
| Student feedback | Firestore `user_feedback`, if present | PostgreSQL linked to an exact response and course-scoped exercise | Legacy feedback is **archive only** by default; selective de-identified analytics only with privacy/academic approval. |
| Teacher tickets/help packets | Firestore `tickets`, if present | PostgreSQL generic teacher-help packets | **Migrate selectively:** only verified open or otherwise operationally relevant requests. Archive closed/expired history. “Open” criteria and cutover owner approval are required. |
| Ticket assignment history | Legacy ticket `teacherId` and related history, if present | No authority for generic future packets; audit archive only | **Archive only**. Never use it for future assignment or authorization. Retention/discard needs explicit approval. |
| Prompt templates and versions | Git template plus inline fallback in evaluator source | Git for prompt source/version | **Migrate in full** to explicit versioned prompt source. Every new PostgreSQL interaction records prompt hash/version, model identifier and generation parameters. Legacy missing values remain unknown. |
| Configuration | Git defaults/templates plus deployment environment | Git for non-secret defaults; deployment configuration system for environment values | **Migrate selectively** with environment review. Reconstruct deployment-specific values; do not copy stale endpoints or flags blindly. |
| Secrets | Runtime environment/credential systems; any historical local files are untrusted | Managed secret system | **Reconstruct/rotate**, never migrate through Git or content manifests. Destruction of superseded credentials occurs only after explicit security/retention approval. |
| Generated documentation | Generated `docs/` tree (18 HTML files and 2 presentation images) as historical build output | Reconstructed from authoritative source in CI | **Reconstruct**; do not migrate as source. Existing bytes may remain in Git history; discard only after explicit retention approval. |

## Confirmed architecture assumptions

All starting assumptions are confirmed with qualifications:

- Validated Git content is future exercise-source authority, conditional on the
  recorded editorial conflicts and course-scoped IDs.
- PostgreSQL is future operational-state authority, not a mirror whose stale rows
  can override Git, Google, or institutional authority.
- Google remains external identity provider; PostgreSQL owns local roles and
  memberships only after institution-approved assignment.
- Firestore remains historical source/archive input and is not future runtime.
- Only operationally relevant tickets qualify for selective operational migration.
- Old AI/feedback records default to encrypted archive; de-identified analytics is
  a separately approved purpose, not an automatic migration.
- Prompt source/version belongs in Git; exact prompt hash and model metadata belong
  with each new interaction.
- Secrets belong in managed secret storage and never Git.

## Owner and institution decisions still required

- Academic owner: `demo_course` publication status, duplicate exercise intent,
  HTML-table source/rendering resolution, course lifecycle and prompt policy.
- Institution: identity eligibility, memberships, roles, ticket operational cutoff,
  records retention/legal holds, analytics purpose, de-identification threshold,
  and deletion authorization.
- Security/operations: secret manager, rotation evidence, Firestore export custody,
  encryption, archive access, backup/restore, and PostgreSQL cutover controls.

Until these decisions are recorded, affected inventory rows remain `owner-decision-required`.
