from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("alertes/", views.alertes, name="alertes"),

    # Employés
    path("employes/", views.liste_employes, name="liste_employes"),
    path("employes/ajouter/", views.creer_employe, name="creer_employe"),
    path("employes/<int:pk>/", views.detail_employe, name="detail_employe"),
    path("employes/<int:pk>/modifier/", views.modifier_employe, name="modifier_employe"),
    path("employes/<int:pk>/supprimer/", views.supprimer_employe, name="supprimer_employe"),

    # Types d'EPI
    path("types-epi/", views.liste_types_epi, name="liste_types_epi"),
    path("types-epi/ajouter/", views.creer_type_epi, name="creer_type_epi"),
    path("types-epi/<int:pk>/modifier/", views.modifier_type_epi, name="modifier_type_epi"),

    # Attributions
    path("attributions/", views.liste_attributions, name="liste_attributions"),
    path("attributions/ajouter/", views.creer_attribution, name="creer_attribution"),
    path("attributions/<int:pk>/renouveler/", views.renouveler_attribution, name="renouveler_attribution"),
]
