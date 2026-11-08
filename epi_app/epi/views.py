from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.core.paginator import Paginator
from datetime import date, timedelta
import json

from .models import Atelier, Employe, TypeEPI, AttributionEPI
from .forms import AtelierForm, EmployeForm, TypeEPIForm, AttributionEPIForm


# ---------- DASHBOARD ----------

@login_required
def dashboard(request):
    total_employes = Employe.objects.count()
    attributions_actives = AttributionEPI.objects.filter(actif=True)
    total_attributions = attributions_actives.count()

    nb_ok = attributions_actives.filter(statut=AttributionEPI.Statut.OK).count()
    nb_a_renouveler = attributions_actives.filter(statut=AttributionEPI.Statut.A_RENOUVELER).count()
    nb_expire = attributions_actives.filter(statut=AttributionEPI.Statut.EXPIRE).count()

    taux_conformite = round((nb_ok / total_attributions) * 100, 1) if total_attributions else 0

    # Répartition par atelier des équipements expirés
    par_atelier = (
        attributions_actives.filter(statut=AttributionEPI.Statut.EXPIRE)
        .values("employe__atelier__nom")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    ateliers_labels = [item["employe__atelier__nom"] for item in par_atelier]
    ateliers_data = [item["total"] for item in par_atelier]

    context = {
        "total_employes": total_employes,
        "total_attributions": total_attributions,
        "taux_conformite": taux_conformite,
        "nb_ok": nb_ok,
        "nb_a_renouveler": nb_a_renouveler,
        "nb_expire": nb_expire,
        "statut_labels": json.dumps(["OK", "À renouveler", "Expiré"]),
        "statut_data": json.dumps([nb_ok, nb_a_renouveler, nb_expire]),
        "ateliers_labels": json.dumps(ateliers_labels),
        "ateliers_data": json.dumps(ateliers_data),
    }
    return render(request, "epi/dashboard.html", context)


# ---------- ALERTES ----------

@login_required
def alertes(request):
    seuil = date.today() + timedelta(days=30)
    liste = AttributionEPI.objects.filter(
        actif=True, date_expiration__lte=seuil
    ).select_related("employe", "type_epi").order_by("date_expiration")
    return render(request, "epi/alertes.html", {"alertes": liste})


# ---------- EMPLOYES ----------

@login_required
def liste_employes(request):
    q = request.GET.get("q", "")
    atelier_id = request.GET.get("atelier", "")
    employes = Employe.objects.select_related("atelier").all()
    if q:
        employes = employes.filter(Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(matricule__icontains=q))
    if atelier_id:
        employes = employes.filter(atelier_id=atelier_id)

    paginator = Paginator(employes, 15)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "epi/liste_employes.html", {
        "page_obj": page, "q": q, "ateliers": Atelier.objects.all(), "atelier_id": atelier_id,
    })


@login_required
def detail_employe(request, pk):
    employe = get_object_or_404(Employe, pk=pk)
    attributions = employe.attributions.select_related("type_epi").order_by("-date_attribution")
    return render(request, "epi/detail_employe.html", {"employe": employe, "attributions": attributions})


@login_required
def creer_employe(request):
    if request.method == "POST":
        form = EmployeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Employé ajouté avec succès.")
            return redirect("liste_employes")
    else:
        form = EmployeForm()
    return render(request, "epi/form_employe.html", {"form": form, "titre": "Ajouter un employé"})


@login_required
def modifier_employe(request, pk):
    employe = get_object_or_404(Employe, pk=pk)
    if request.method == "POST":
        form = EmployeForm(request.POST, instance=employe)
        if form.is_valid():
            form.save()
            messages.success(request, "Employé modifié avec succès.")
            return redirect("liste_employes")
    else:
        form = EmployeForm(instance=employe)
    return render(request, "epi/form_employe.html", {"form": form, "titre": "Modifier l'employé"})


@login_required
def supprimer_employe(request, pk):
    employe = get_object_or_404(Employe, pk=pk)
    if request.method == "POST":
        employe.delete()
        messages.success(request, "Employé supprimé.")
        return redirect("liste_employes")
    return render(request, "epi/confirmer_suppression.html", {"objet": employe})


# ---------- TYPES EPI ----------

@login_required
def liste_types_epi(request):
    types = TypeEPI.objects.all()
    return render(request, "epi/liste_types_epi.html", {"types": types})


@login_required
def creer_type_epi(request):
    if request.method == "POST":
        form = TypeEPIForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Type d'EPI ajouté avec succès.")
            return redirect("liste_types_epi")
    else:
        form = TypeEPIForm()
    return render(request, "epi/form_type_epi.html", {"form": form, "titre": "Ajouter un type d'EPI"})


@login_required
def modifier_type_epi(request, pk):
    type_epi = get_object_or_404(TypeEPI, pk=pk)
    if request.method == "POST":
        form = TypeEPIForm(request.POST, instance=type_epi)
        if form.is_valid():
            form.save()
            messages.success(request, "Type d'EPI modifié avec succès.")
            return redirect("liste_types_epi")
    else:
        form = TypeEPIForm(instance=type_epi)
    return render(request, "epi/form_type_epi.html", {"form": form, "titre": "Modifier le type d'EPI"})


# ---------- ATTRIBUTIONS ----------

@login_required
def liste_attributions(request):
    statut = request.GET.get("statut", "")
    atelier_id = request.GET.get("atelier", "")

    attributions = AttributionEPI.objects.filter(actif=True).select_related("employe", "type_epi", "employe__atelier")
    if statut:
        attributions = attributions.filter(statut=statut)
    if atelier_id:
        attributions = attributions.filter(employe__atelier_id=atelier_id)

    paginator = Paginator(attributions, 15)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "epi/liste_attributions.html", {
        "page_obj": page, "statut": statut, "atelier_id": atelier_id,
        "ateliers": Atelier.objects.all(), "statuts": AttributionEPI.Statut.choices,
    })


@login_required
def creer_attribution(request):
    if request.method == "POST":
        form = AttributionEPIForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Attribution créée avec succès.")
            return redirect("liste_attributions")
    else:
        form = AttributionEPIForm()
    return render(request, "epi/form_attribution.html", {"form": form, "titre": "Nouvelle attribution"})


@login_required
def renouveler_attribution(request, pk):
    attribution = get_object_or_404(AttributionEPI, pk=pk)
    if request.method == "POST":
        attribution.renouveler()
        messages.success(request, "Équipement renouvelé avec succès.")
    return redirect("liste_attributions")
