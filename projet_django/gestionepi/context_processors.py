from datetime import date, timedelta
from .models import AttributionEPI


def notifications_epi(request):
    if not request.user.is_authenticated:
        return {}

    aujourdhui = date.today()
    dans_7_jours = aujourdhui + timedelta(days=7)

    notifications = AttributionEPI.objects.filter(
        actif=True,
        date_expiration__gte=aujourdhui,
        date_expiration__lte=dans_7_jours,
    ).select_related("employe", "type_epi").order_by("date_expiration")

    return {
        "nb_notifications": notifications.count(),
        "notifications": notifications[:8],  # limite l'aperçu dans le menu déroulant
    }