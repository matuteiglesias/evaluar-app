from django import forms

from .models import HumanHelpTicket, TicketMessage


class TicketCreateForm(forms.Form):
    question = forms.CharField(
        label="¿En qué necesitas ayuda?",
        min_length=10,
        max_length=5000,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 6}),
    )
    idempotency_key = forms.CharField(max_length=100, widget=forms.HiddenInput)
    priority = forms.ChoiceField(label="Prioridad", choices=HumanHelpTicket.Priority.choices)


class TicketMessageForm(forms.Form):
    body = forms.CharField(
        label="Mensaje",
        min_length=1,
        max_length=10000,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 5}),
    )
    visibility = forms.ChoiceField(label="Visibilidad", choices=TicketMessage.Visibility.choices)

    def __init__(self, *args, allow_internal=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not allow_internal:
            self.fields["visibility"].choices = [
                (TicketMessage.Visibility.PARTICIPANTS, "Participantes")
            ]
            self.fields["visibility"].widget = forms.HiddenInput()
