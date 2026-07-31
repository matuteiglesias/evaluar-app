import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Course",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("slug", models.SlugField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("archived", "Archived")],
                        default="active",
                        max_length=20,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ContentPublication",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("source_commit", models.CharField(max_length=64)),
                ("manifest_checksum", models.CharField(max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("validating", "Validating"),
                            ("valid", "Valid"),
                            ("published", "Published"),
                            ("rejected", "Rejected"),
                        ],
                        default="validating",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="publications",
                        to="courses.course",
                    ),
                ),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="Exercise",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("slug", models.SlugField(max_length=100)),
                ("external_key", models.CharField(max_length=255)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="exercises",
                        to="courses.course",
                    ),
                ),
            ],
            options={"ordering": ("slug",)},
        ),
        migrations.CreateModel(
            name="ExerciseVersion",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("version_number", models.PositiveIntegerField()),
                ("source_checksum", models.CharField(max_length=64)),
                ("title", models.CharField(max_length=255)),
                ("section", models.CharField(blank=True, max_length=255)),
                (
                    "source_format",
                    models.CharField(
                        choices=[
                            ("latex", "LaTeX"),
                            ("markdown", "Markdown"),
                            ("text", "Plain text"),
                        ],
                        max_length=20,
                    ),
                ),
                ("source_text", models.TextField()),
                ("rendered_html", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "exercise",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="versions",
                        to="courses.exercise",
                    ),
                ),
                (
                    "publication",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_versions",
                        to="courses.contentpublication",
                    ),
                ),
            ],
            options={"ordering": ("section", "title", "version_number")},
        ),
        migrations.CreateModel(
            name="PublishedExerciseVersion",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "publication",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="included_versions",
                        to="courses.contentpublication",
                    ),
                ),
                (
                    "version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="publication_links",
                        to="courses.exerciseversion",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="contentpublication",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "published")),
                fields=("course",),
                name="one_published_release_per_course",
            ),
        ),
        migrations.AddConstraint(
            model_name="contentpublication",
            constraint=models.UniqueConstraint(
                fields=("course", "manifest_checksum"), name="idempotent_course_publication"
            ),
        ),
        migrations.AddConstraint(
            model_name="exercise",
            constraint=models.UniqueConstraint(
                fields=("course", "slug"), name="unique_course_exercise_slug"
            ),
        ),
        migrations.AddConstraint(
            model_name="exercise",
            constraint=models.UniqueConstraint(
                fields=("course", "external_key"), name="unique_course_external_key"
            ),
        ),
        migrations.AddConstraint(
            model_name="exerciseversion",
            constraint=models.UniqueConstraint(
                fields=("exercise", "version_number"), name="unique_exercise_version"
            ),
        ),
        migrations.AddConstraint(
            model_name="exerciseversion",
            constraint=models.UniqueConstraint(
                fields=("exercise", "source_checksum"), name="unique_exercise_checksum"
            ),
        ),
        migrations.AddConstraint(
            model_name="publishedexerciseversion",
            constraint=models.UniqueConstraint(
                fields=("publication", "version"), name="unique_publication_version"
            ),
        ),
    ]
