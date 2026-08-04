import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("courses", "0001_initial"), ("identity", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="PendingCourseEnrollment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("identity", models.EmailField(max_length=254)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("student", "Student"),
                            ("teacher", "Teacher"),
                            ("course_admin", "Course administrator"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("suspended", "Suspended"),
                            ("inactive", "Inactive"),
                        ],
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pending_enrollments",
                        to="courses.course",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="pendingcourseenrollment",
            constraint=models.UniqueConstraint(
                fields=("course", "identity"), name="unique_pending_course_identity"
            ),
        ),
        migrations.AlterField(
            model_name="auditevent",
            name="event",
            field=models.CharField(
                choices=[
                    ("sign_in", "Sign in"),
                    ("membership_created", "Membership created"),
                    ("membership_changed", "Membership changed"),
                    ("membership_deleted", "Membership deleted"),
                    ("enrollment_pending", "Enrollment pending"),
                    ("enrollment_changed", "Enrollment changed"),
                ],
                max_length=32,
            ),
        ),
    ]
