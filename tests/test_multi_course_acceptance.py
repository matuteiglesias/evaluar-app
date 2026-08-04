import csv
import uuid

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from evaluar.content_pipeline import compile_content
from evaluar.courses.models import Course, ExerciseVersion
from evaluar.courses.services import publish_bundle
from evaluar.identity.models import CourseMembership, User
from evaluar.support.models import HumanHelpTicket
from evaluar.tutoring.models import ActivePrompt, PromptVersion, TutoringSubmission


pytestmark = pytest.mark.django_db


def _course_source(root, slug, body):
    directory = root / "exercises" / slug
    directory.mkdir(parents=True)
    with (directory / "index.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("id", "section", "file", "name"))
        writer.writeheader()
        writer.writerow({"id": "101", "section": "A", "file": "101.tex", "name": slug})
    (directory / "101.tex").write_text(body, encoding="utf-8")


def test_two_course_request_layer_acceptance(tmp_path, client):
    _course_source(tmp_path, "alpha", "Álgebra $x + y$")
    _course_source(tmp_path, "beta", "SQL SELECT * FROM R")
    bundle = compile_content(tmp_path, source_commit="acceptance")
    first_publications = publish_bundle(bundle)
    second_publications = publish_bundle(bundle)
    assert [item.pk for item in first_publications] == [item.pk for item in second_publications]
    assert Course.objects.count() == 2

    alpha, beta = Course.objects.order_by("slug")
    alpha_version = ExerciseVersion.objects.get(exercise__course=alpha)
    beta_version = ExerciseVersion.objects.get(exercise__course=beta)
    student = User.objects.create_user(username="alpha-student")
    CourseMembership.objects.create(user=student, course=alpha, role="student")
    prompt = PromptVersion.objects.create(
        public_id="default",
        version=1,
        system_instructions="Guide.",
        model_policy={"provider": "openai", "requested_model": "not-called"},
        checksum="a" * 64,
        status="published",
    )
    ActivePrompt.objects.create(public_id="default", prompt_version=prompt)
    client.force_login(student)

    alpha_url = reverse("courses:version", args=(alpha.slug, alpha_version.exercise.slug, 1))
    beta_url = reverse("courses:version", args=(beta.slug, beta_version.exercise.slug, 1))
    assert client.get(alpha_url).status_code == 200
    assert client.get(beta_url).status_code == 403
    assert (
        client.post(
            reverse("tutoring:submit", args=(beta_version.id,)),
            {"student_answer": "cross course", "idempotency_key": uuid.uuid4()},
        ).status_code
        == 403
    )
    tutoring = client.post(
        reverse("tutoring:submit", args=(alpha_version.id,)),
        {"student_answer": "my answer", "idempotency_key": uuid.uuid4()},
    )
    assert tutoring.status_code == 302
    assert TutoringSubmission.objects.get().exercise_version == alpha_version

    alpha_support_url = reverse("support:create", args=(alpha_version.id,))
    assert client.get(alpha_support_url).status_code == 200
    support_key = client.session[f"support:create:exercise:{alpha_version.id}"]
    support = client.post(
        alpha_support_url,
        {"question": "Necesito ayuda", "priority": "normal", "idempotency_key": support_key},
    )
    assert support.status_code == 302
    assert HumanHelpTicket.objects.get().course == alpha
    assert (
        client.post(
            reverse("support:create", args=(beta_version.id,)),
            {"question": "cross", "priority": "normal", "idempotency_key": "ignored"},
        ).status_code
        == 403
    )

    alpha_version.title = "mutated"
    with pytest.raises(ValidationError):
        alpha_version.save()
