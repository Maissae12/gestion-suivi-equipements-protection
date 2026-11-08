from django.contrib import admin
from .models import Atelier, Employe, TypeEPI, AttributionEPI


@admin.register(Atelier)
class AtelierAdmin(admin.ModelAdmin):
    list_display = ["nom"]
    search_fields = ["nom"]


@admin.register(Employe)
class EmployeAdmin(admin.ModelAdmin):
    list_display = ["matricule", "nom", "prenom", "atelier", "date_embauche"]
    list_filter = ["atelier"]
    search_fields = ["nom", "prenom", "matricule"]


@admin.register(TypeEPI)
class TypeEPIAdmin(admin.ModelAdmin):
    list_display = ["nom", "duree_vie_mois", "prix_unitaire", "stock_disponible"]
    search_fields = ["nom"]


@admin.register(AttributionEPI)
class AttributionEPIAdmin(admin.ModelAdmin):
    list_display = ["employe", "type_epi", "date_attribution", "date_expiration", "statut", "actif", "motif_cloture"]
    list_filter = ["statut", "actif", "motif_cloture", "type_epi", "employe__atelier"]
    search_fields = ["employe__nom", "employe__prenom", "employe__matricule"]
    readonly_fields = ["date_expiration", "statut", "date_cloture", "motif_cloture"]
