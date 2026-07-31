import uuid

from django import forms
from django.conf import settings


class AnswerSubmissionForm(forms.Form):
    student_answer = forms.CharField(
        label="Tu respuesta",
        widget=forms.Textarea(
            attrs={
                "rows": 10,
                "placeholder": "Explica tu razonamiento o escribe tu solución…",
            }
        ),
    )
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)

    def clean_student_answer(self):
        answer = self.cleaned_data["student_answer"].strip()
        if len(answer) > settings.TUTORING_MAX_ANSWER_CHARS:
            raise forms.ValidationError(
                f"La respuesta no puede superar {settings.TUTORING_MAX_ANSWER_CHARS} caracteres."
            )
        return answer

    @classmethod
    def fresh(cls):
        return cls(initial={"idempotency_key": uuid.uuid4()})


class ResponseFeedbackForm(forms.Form):
    helpful = forms.TypedChoiceField(
        label="¿Te resultó útil?",
        choices=(("true", "Sí"), ("false", "No")),
        coerce=lambda value: value == "true",
        widget=forms.RadioSelect,
    )
    comment = forms.CharField(
        label="Comentario opcional",
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
