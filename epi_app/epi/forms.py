from django import forms
from .models import Atelier, Employe, TypeEPI, AttributionEPI


class AtelierForm(forms.ModelForm):
    class Meta:
        model = Atelier
        fields = ["nom"]
        widgets = {
            "nom": forms.TextInput(attrs={"class": "form-control"}),
        }


class EmployeForm(forms.ModelForm):
    class Meta:
        model = Employe
        fields = ["matricule", "nom", "prenom", "atelier", "date_embauche"]
        widgets = {
            "matricule": forms.TextInput(attrs={"class": "form-control"}),
            "nom": forms.TextInput(attrs={"class": "form-control"}),
            "prenom": forms.TextInput(attrs={"class": "form-control"}),
            "atelier": forms.Select(attrs={"class": "form-select"}),
            "date_embauche": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }


class TypeEPIForm(forms.ModelForm):
    class Meta:
        model = TypeEPI
        fields = ["nom", "duree_vie_mois", "prix_unitaire", "stock_disponible"]
        widgets = {
            "nom": forms.TextInput(attrs={"class": "form-control"}),
            "duree_vie_mois": forms.NumberInput(attrs={"class": "form-control"}),
            "prix_unitaire": forms.NumberInput(attrs={"class": "form-control"}),
            "stock_disponible": forms.NumberInput(attrs={"class": "form-control"}),
        }


class AttributionEPIForm(forms.ModelForm):
    class Meta:
        model = AttributionEPI
        fields = ["employe", "type_epi", "date_attribution"]
        widgets = {
            "employe": forms.Select(attrs={"class": "form-select"}),
            "type_epi": forms.Select(attrs={"class": "form-select"}),
            "date_attribution": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }
