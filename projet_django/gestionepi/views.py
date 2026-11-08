from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.db.models import Count, Q,Sum
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from datetime import date, timedelta
import json
from reportlab.platypus import Image
from django.conf import settings
import os
from openpyxl.drawing.image import Image as XLImage
from .models import Atelier, Employe, TypeEPI, AttributionEPI
from .forms import AtelierForm, EmployeForm, TypeEPIForm, AttributionEPIForm, IncidentForm
from django.http import HttpResponse
import openpyxl
from openpyxl.styles import Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
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
    par_atelier = (
        attributions_actives.filter(statut=AttributionEPI.Statut.EXPIRE)
        .values("employe__atelier__nom")
        .annotate(total=Count("id"))
        .order_by("-total"))
    ateliers_labels = [item["employe__atelier__nom"] for item in par_atelier]
    ateliers_data = [item["total"] for item in par_atelier]
# ---- Top employés à risque (incidents = perte ou dommage) ----
    top_employes_risque = (
        AttributionEPI.objects
        .filter(motif_cloture__in=["PERTE", "DOMMAGE"])
        .values("employe__id", "employe__nom", "employe__prenom")
        .annotate(nb_incidents=Count("id"))
        .order_by("-nb_incidents")[:5]
    )
    # ---- Coût total des incidents, selon la période choisie ----
    periode = request.GET.get("periode", "mois")
    aujourdhui = date.today()
    if periode == "annee":
        debut_periode = aujourdhui.replace(month=1, day=1)
    elif periode == "trimestre":
        premier_mois_trimestre = ((aujourdhui.month - 1) // 3) * 3 + 1
        debut_periode = aujourdhui.replace(month=premier_mois_trimestre, day=1)
    else:  # "mois" par défaut
        debut_periode = aujourdhui.replace(day=1)
    cout_incidents_periode = (
        AttributionEPI.objects
        .filter(
            motif_cloture__in=["PERTE", "DOMMAGE"],
            date_cloture__gte=debut_periode,
        )
        .aggregate(total=Sum("type_epi__prix_unitaire"))["total"] or 0
    )
    # ---- EPI en rupture de stock imminente ----
    epi_stock_faible = TypeEPI.objects.filter(stock_disponible__lt=models.F("seuil_alerte")).order_by("stock_disponible")

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
        "top_employes_risque": top_employes_risque,
"cout_incidents_periode": cout_incidents_periode,
        "periode": periode,        "epi_stock_faible": epi_stock_faible,
    }
    return render(request, "gestionepi/dashboard.html", context)

@login_required
def fiche_employe_pdf(request, pk):
    employe = get_object_or_404(Employe, pk=pk)
    attributions = employe.attributions.select_related("type_epi").order_by("-date_attribution")
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="fiche_{employe.matricule}.pdf"'
    doc = SimpleDocTemplate(response, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm)
    elements = []
    styles = getSampleStyleSheet()
    logo_path = os.path.join(settings.BASE_DIR, "gestionepi", "static", "gestionepi", "images", "logo-ocp.png")
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=3*cm, height=3*cm)
        titre = Paragraph("Fiche de suivi EPI<br/><font size=10 color='#555555'>Groupe OCP</font>", styles["Title"])
        entete = Table([[logo, titre]], colWidths=[3.5*cm, None])
        entete.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ]))
        elements.append(entete)
    else:
        elements.append(Paragraph("Fiche de suivi EPI — Groupe OCP", styles["Title"]))

    elements.append(Spacer(1, 0.5*cm))

    # ---- Infos employé ----
    infos = [
        ["Nom complet :", f"{employe.prenom} {employe.nom}"],
        ["Matricule :", employe.matricule],
        ["Atelier :", employe.atelier.nom],
        ["Date d'embauche :", employe.date_embauche.strftime("%d/%m/%Y")],
        ["Généré le :", date.today().strftime("%d/%m/%Y")],
    ]
    table_infos = Table(infos, colWidths=[4*cm, 10*cm])
    table_infos.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table_infos)
    elements.append(Spacer(1, 0.7*cm))

    elements.append(Paragraph("Historique des attributions", styles["Heading2"]))
    elements.append(Spacer(1, 0.3*cm))

    data = [["Équipement", "Attribution", "Expiration/Clôture", "Statut / Motif"]]
    for a in attributions:
        if a.actif:
            statut_texte = a.get_statut_display()
            date_fin = a.date_expiration.strftime("%d/%m/%Y") if a.date_expiration else ""
        else:
            statut_texte = a.get_motif_cloture_display() if a.motif_cloture else "Clôturé"
            date_fin = a.date_cloture.strftime("%d/%m/%Y") if a.date_cloture else ""
        data.append([a.type_epi.nom, a.date_attribution.strftime("%d/%m/%Y"), date_fin, statut_texte])

    table = Table(data, repeatRows=1, colWidths=[5*cm, 3*cm, 3.5*cm, 4*cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#053724")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#053724")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#E8F3ED")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)

    doc.build(elements)
    return response
# ---------- ALERTES ----------

@login_required
def alertes(request):
    seuil = date.today() + timedelta(days=30)

    q = request.GET.get("q", "")
    epi = request.GET.get("epi", "")
    date_expiration = request.GET.get("date_expiration", "")
    atelier_id = request.GET.get("atelier", "")

    liste = AttributionEPI.objects.filter(
        actif=True, date_expiration__lte=seuil
    ).select_related("employe", "type_epi", "employe__atelier")

    if q:
        liste = liste.filter(
            Q(employe__nom__icontains=q) |
            Q(employe__prenom__icontains=q) |
            Q(employe__matricule__icontains=q)
        )
    if epi:
        liste = liste.filter(type_epi__nom__icontains=epi)
    if date_expiration:
        liste = liste.filter(date_expiration=date_expiration)
    if atelier_id:
        liste = liste.filter(employe__atelier_id=atelier_id)

    liste = liste.order_by("date_expiration")

    return render(request, "gestionepi/alertes.html", {
        "alertes": liste,
        "ateliers": Atelier.objects.all(),
    })


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
    return render(request, "gestionepi/liste_employes.html", {
        "page_obj": page, "q": q, "ateliers": Atelier.objects.all(), "atelier_id": atelier_id,
    })
@login_required
def detail_employe(request, pk):
    employe = get_object_or_404(Employe, pk=pk)
    attributions = employe.attributions.select_related("type_epi").order_by("-date_attribution")
    return render(request, "gestionepi/detail_employe.html", {"employe": employe, "attributions": attributions})

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
    return render(request, "gestionepi/form_employe.html", {"form": form, "titre": "Ajouter un employé"})
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
    return render(request, "gestionepi/form_employe.html", {"form": form, "titre": "Modifier l'employé"})
@login_required
def supprimer_employe(request, pk):
    employe = get_object_or_404(Employe, pk=pk)
    if request.method == "POST":
        employe.delete()
        messages.success(request, "Employé supprimé.")
        return redirect("liste_employes")
    return render(request, "gestionepi/confirmer_suppression.html", {"objet": employe})

# ---------- TYPES EPI ----------

@login_required
def liste_types_epi(request):
    q = request.GET.get("q", "")
    duree = request.GET.get("duree", "")
    prix_min = request.GET.get("prix_min", "")
    prix_max = request.GET.get("prix_max", "")
    stock = request.GET.get("stock", "")

    types = TypeEPI.objects.all()

    if q:
        types = types.filter(nom__icontains=q)
    if duree:
        types = types.filter(duree_vie_mois=duree)
    if prix_min:
        types = types.filter(prix_unitaire__gte=prix_min)
    if prix_max:
        types = types.filter(prix_unitaire__lte=prix_max)
    if stock:
        types = types.filter(stock_disponible=stock)

    return render(request, "gestionepi/liste_types_epi.html", {
        "types": types,
        "q": q, "duree": duree, "prix_min": prix_min, "prix_max": prix_max, "stock": stock,
    })

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
    return render(request, "gestionepi/form_type_epi.html", {"form": form, "titre": "Ajouter un type d'EPI"})


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
    return render(request, "gestionepi/form_type_epi.html", {"form": form, "titre": "Modifier le type d'EPI"})


@login_required
def supprimer_type_epi(request, pk):
    type_epi = get_object_or_404(TypeEPI, pk=pk)
    if request.method == "POST":
        try:
            type_epi.delete()
            messages.success(request, "Type d'EPI supprimé.")
        except models.ProtectedError:
            messages.error(
                request,
                f"Impossible de supprimer '{type_epi.nom}' : il est encore utilisé dans des attributions existantes."
            )
        return redirect("liste_types_epi")
    return render(request, "gestionepi/confirmer_suppression.html", {"objet": type_epi})


# ---------- ATTRIBUTIONS ----------

@login_required
def liste_attributions(request):
    q = request.GET.get("q", "")
    statut = request.GET.get("statut", "")
    atelier_id = request.GET.get("atelier", "")

    attributions = AttributionEPI.objects.filter(actif=True).select_related("employe", "type_epi", "employe__atelier")
    if q:
        attributions = attributions.filter(
            Q(employe__nom__icontains=q) |
            Q(employe__prenom__icontains=q) |
            Q(employe__matricule__icontains=q)
        )
    if statut:
        attributions = attributions.filter(statut=statut)
    if atelier_id:
        attributions = attributions.filter(employe__atelier_id=atelier_id)

    paginator = Paginator(attributions, 15)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "gestionepi/liste_attributions.html", {
        "page_obj": page, "q": q, "statut": statut, "atelier_id": atelier_id,
        "ateliers": Atelier.objects.all(), "statuts": AttributionEPI.Statut.choices,
    })
@login_required
def exporter_attributions_excel(request):
    q = request.GET.get("q", "")
    statut = request.GET.get("statut", "")
    atelier_id = request.GET.get("atelier", "")
    attributions = AttributionEPI.objects.filter(actif=True).select_related(
        "employe", "type_epi", "employe__atelier"
    )
    if q:
        attributions = attributions.filter(
            Q(employe__nom__icontains=q) |
            Q(employe__prenom__icontains=q) |
            Q(employe__matricule__icontains=q)
        )
    if statut:
        attributions = attributions.filter(statut=statut)
    if atelier_id:
        attributions = attributions.filter(employe__atelier_id=atelier_id)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Attributions EPI"

    # ---- Logo ----
    logo_path = os.path.join(settings.BASE_DIR, "gestionepi", "static", "gestionepi", "images", "logo-ocp.png")
    if os.path.exists(logo_path):
        img = XLImage(logo_path)
        img.width = 80
        img.height = 80
        ws.add_image(img, "A1")
        ws.row_dimensions[1].height = 60
        ws.row_dimensions[2].height = 22
        titre_cell = ws.cell(row=2, column=2, value="Attributions EPI actives — Groupe OCP")
        titre_cell.font = Font(bold=True, size=14, color="053724")
        ligne_entetes = 4
    else:
        ligne_entetes = 1

    entetes = ["Employé", "Matricule", "Atelier", "Équipement", "Date attribution", "Date expiration", "Statut"]
    for col_num, entete in enumerate(entetes, start=1):
        cell = ws.cell(row=ligne_entetes, column=col_num, value=entete)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="053724", end_color="053724", fill_type="solid")

    ligne = ligne_entetes + 1
    for a in attributions:
        ws.cell(row=ligne, column=1, value=f"{a.employe.prenom} {a.employe.nom}")
        ws.cell(row=ligne, column=2, value=a.employe.matricule)
        ws.cell(row=ligne, column=3, value=a.employe.atelier.nom)
        ws.cell(row=ligne, column=4, value=a.type_epi.nom)
        ws.cell(row=ligne, column=5, value=a.date_attribution.strftime("%d/%m/%Y"))
        ws.cell(row=ligne, column=6, value=a.date_expiration.strftime("%d/%m/%Y") if a.date_expiration else "")
        ws.cell(row=ligne, column=7, value=a.get_statut_display())
        if ligne % 2 == 0:
            for col in range(1, 8):
                ws.cell(row=ligne, column=col).fill = PatternFill(start_color="E8F3ED", end_color="E8F3ED", fill_type="solid")
        ligne += 1

    for col_letter in ["A", "B", "C", "D", "E", "F", "G"]:
        largeur_max = max(
            (len(str(ws.cell(row=r, column=ord(col_letter) - 64).value or "")) for r in range(ligne_entetes, ligne)),
            default=10,
        ) + 2
        ws.column_dimensions[col_letter].width = largeur_max

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="attributions_epi.xlsx"'
    wb.save(response)
    return response


@login_required
def exporter_attributions_pdf(request):
    q = request.GET.get("q", "")
    statut = request.GET.get("statut", "")
    atelier_id = request.GET.get("atelier", "")

    attributions = AttributionEPI.objects.filter(actif=True).select_related(
        "employe", "type_epi", "employe__atelier"
    )
    if q:
        attributions = attributions.filter(
            Q(employe__nom__icontains=q) |
            Q(employe__prenom__icontains=q) |
            Q(employe__matricule__icontains=q)
        )
    if statut:
        attributions = attributions.filter(statut=statut)
    if atelier_id:
        attributions = attributions.filter(employe__atelier_id=atelier_id)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="attributions_epi.pdf"'

    doc = SimpleDocTemplate(response, pagesize=landscape(A4),
                             topMargin=1.5*cm, bottomMargin=1.5*cm)
    elements = []
    styles = getSampleStyleSheet()

    # ---- En-tête avec logo ----
    logo_path = os.path.join(settings.BASE_DIR, "gestionepi", "static", "gestionepi", "images", "logo-ocp.png")
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=3*cm, height=3*cm)
        titre = Paragraph("Attributions EPI actives<br/><font size=10 color='#555555'>Groupe OCP</font>", styles["Title"])
        entete = Table([[logo, titre]], colWidths=[3.5*cm, None])
        entete.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ]))
        elements.append(entete)
    else:
        elements.append(Paragraph("Attributions EPI actives — Groupe OCP", styles["Title"]))

    elements.append(Spacer(1, 0.5*cm))

    date_generation = Paragraph(f"Généré le {date.today().strftime('%d/%m/%Y')}", styles["Normal"])
    elements.append(date_generation)
    elements.append(Spacer(1, 0.5*cm))

    data = [["Employé", "Matricule", "Atelier", "Équipement", "Attribution", "Expiration", "Statut"]]
    for a in attributions:
        data.append([
            f"{a.employe.prenom} {a.employe.nom}",
            a.employe.matricule,
            a.employe.atelier.nom,
            a.type_epi.nom,
            a.date_attribution.strftime("%d/%m/%Y"),
            a.date_expiration.strftime("%d/%m/%Y") if a.date_expiration else "",
            a.get_statut_display(),
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#053724")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#053724")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#E8F3ED")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)

    doc.build(elements)
    return response

@login_required
def historique_attributions(request):
    q = request.GET.get("q", "")
    motif = request.GET.get("motif", "")

    historique = AttributionEPI.objects.filter(actif=False).select_related(
        "employe", "type_epi", "employe__atelier"
    ).order_by("-date_cloture")

    if q:
        historique = historique.filter(
            Q(employe__nom__icontains=q) |
            Q(employe__prenom__icontains=q) |
            Q(employe__matricule__icontains=q)
        )
    if motif:
        historique = historique.filter(motif_cloture=motif)

    paginator = Paginator(historique, 20)
    page = paginator.get_page(request.GET.get("page"))

    return render(request, "gestionepi/historique_attributions.html", {
        "page_obj": page, "q": q, "motif": motif,
        "motifs": AttributionEPI.MotifCloture.choices,
    })
@login_required
def exporter_historique_excel(request):
    q = request.GET.get("q", "")
    motif = request.GET.get("motif", "")

    historique = AttributionEPI.objects.filter(actif=False).select_related(
        "employe", "type_epi", "employe__atelier"
    ).order_by("-date_cloture")

    if q:
        historique = historique.filter(
            Q(employe__nom__icontains=q) |
            Q(employe__prenom__icontains=q) |
            Q(employe__matricule__icontains=q)
        )
    if motif:
        historique = historique.filter(motif_cloture=motif)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Historique EPI"
    # ---- Logo ----
    logo_path = os.path.join(settings.BASE_DIR, "gestionepi", "static", "gestionepi", "images", "logo-ocp.png")
    if os.path.exists(logo_path):
        img = XLImage(logo_path)
        img.width = 80
        img.height = 80
        ws.add_image(img, "A1")
        ws.row_dimensions[1].height = 60
        ws.row_dimensions[2].height = 22
        titre_cell = ws.cell(row=2, column=2, value="Historique des attributions EPI — Groupe OCP")
        titre_cell.font = Font(bold=True, size=14, color="053724")
        ligne_entetes = 4
    else:
        ligne_entetes = 1

    entetes = ["Employé", "Matricule", "Atelier", "Équipement", "Date attribution", "Date clôture", "Motif"]
    for col_num, entete in enumerate(entetes, start=1):
        cell = ws.cell(row=ligne_entetes, column=col_num, value=entete)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="053724", end_color="053724", fill_type="solid")

    ligne = ligne_entetes + 1
    for a in historique:
        ws.cell(row=ligne, column=1, value=f"{a.employe.prenom} {a.employe.nom}")
        ws.cell(row=ligne, column=2, value=a.employe.matricule)
        ws.cell(row=ligne, column=3, value=a.employe.atelier.nom)
        ws.cell(row=ligne, column=4, value=a.type_epi.nom)
        ws.cell(row=ligne, column=5, value=a.date_attribution.strftime("%d/%m/%Y"))
        ws.cell(row=ligne, column=6, value=a.date_cloture.strftime("%d/%m/%Y") if a.date_cloture else "")
        ws.cell(row=ligne, column=7, value=a.get_motif_cloture_display() if a.motif_cloture else "")
        if ligne % 2 == 0:
            for col in range(1, 8):
                ws.cell(row=ligne, column=col).fill = PatternFill(start_color="E8F3ED", end_color="E8F3ED", fill_type="solid")
        ligne += 1

    for col_letter in ["A", "B", "C", "D", "E", "F", "G"]:
        largeur_max = max(
            (len(str(ws.cell(row=r, column=ord(col_letter) - 64).value or "")) for r in range(ligne_entetes, ligne)),
            default=10,
        ) + 2
        ws.column_dimensions[col_letter].width = largeur_max

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="historique_epi.xlsx"'
    wb.save(response)
    return response

@login_required
def exporter_historique_pdf(request):
    q = request.GET.get("q", "")
    motif = request.GET.get("motif", "")

    historique = AttributionEPI.objects.filter(actif=False).select_related(
        "employe", "type_epi", "employe__atelier"
    ).order_by("-date_cloture")

    if q:
        historique = historique.filter(
            Q(employe__nom__icontains=q) |
            Q(employe__prenom__icontains=q) |
            Q(employe__matricule__icontains=q)
        )
    if motif:
        historique = historique.filter(motif_cloture=motif)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="historique_epi.pdf"'

    doc = SimpleDocTemplate(response, pagesize=landscape(A4),
                             topMargin=1.5*cm, bottomMargin=1.5*cm)
    elements = []
    styles = getSampleStyleSheet()

    # ---- En-tête avec logo ----
    logo_path = os.path.join(settings.BASE_DIR, "gestionepi", "static", "gestionepi", "images", "logo-ocp.png")
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=3*cm, height=3*cm)
        titre = Paragraph("Historique des attributions EPI<br/><font size=10 color='#555555'>Groupe OCP</font>", styles["Title"])
        entete = Table([[logo, titre]], colWidths=[3.5*cm, None])
        entete.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ]))
        elements.append(entete)
    else:
        elements.append(Paragraph("Historique des attributions EPI — Groupe OCP", styles["Title"]))

    elements.append(Spacer(1, 0.5*cm))

    date_generation = Paragraph(f"Généré le {date.today().strftime('%d/%m/%Y')}", styles["Normal"])
    elements.append(date_generation)
    elements.append(Spacer(1, 0.5*cm))

    data = [["Employé", "Matricule", "Atelier", "Équipement", "Attribution", "Clôture", "Motif"]]
    for a in historique:
        data.append([
            f"{a.employe.prenom} {a.employe.nom}",
            a.employe.matricule,
            a.employe.atelier.nom,
            a.type_epi.nom,
            a.date_attribution.strftime("%d/%m/%Y"),
            a.date_cloture.strftime("%d/%m/%Y") if a.date_cloture else "",
            a.get_motif_cloture_display() if a.motif_cloture else "",
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#053724")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#053724")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#E8F3ED")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)

    doc.build(elements)
    return response

@login_required
def creer_attribution(request):
    if request.method == "POST":
        form = AttributionEPIForm(request.POST)
        if form.is_valid():
            employe = form.cleaned_data["employe"]
            type_epi = form.cleaned_data["type_epi"]
            deja_actif = AttributionEPI.objects.filter(employe=employe, type_epi=type_epi, actif=True).exists()
            if deja_actif:
                form.add_error(None, f"{employe} possède déjà un(e) {type_epi} actif(ve). "
                                      f"Utilisez le renouvellement ou déclarez un incident (perte/dommage) "
                                      f"plutôt que d'en créer un nouveau.")
            else:
                try:
                    form.save()
                    messages.success(request, "Attribution créée avec succès.")
                    return redirect("liste_attributions")
                except ValidationError as e:
                    messages.error(request, e.message)
    else:
        form = AttributionEPIForm()
    return render(request, "gestionepi/form_attribution.html", {"form": form, "titre": "Nouvelle attribution"})


@login_required
def renouveler_attribution(request, pk):
    attribution = get_object_or_404(AttributionEPI, pk=pk)
    if request.method == "POST":
        try:
            attribution.renouveler()
            messages.success(request, "Équipement renouvelé avec succès.")
        except ValidationError as e:
            messages.error(request, e.message)
    return redirect("liste_attributions")


@login_required
def declarer_incident(request, pk):
    attribution = get_object_or_404(AttributionEPI, pk=pk, actif=True)
    if request.method == "POST":
        form = IncidentForm(request.POST)
        if form.is_valid():
            motif = form.cleaned_data["motif"]
            try:
                attribution.declarer_incident(motif)
                messages.success(request, "Incident déclaré : un nouvel équipement a été attribué.")
                return redirect("liste_attributions")
            except ValidationError as e:
                messages.error(request, e.message)
    else:
        form = IncidentForm()
    return render(request, "gestionepi/form_incident.html", {"form": form, "attribution": attribution})


@login_required
def supprimer_attribution(request, pk):
    attribution = get_object_or_404(AttributionEPI, pk=pk)
    if request.method == "POST":
        TypeEPI.objects.filter(pk=attribution.type_epi.pk).update(
            stock_disponible=models.F('stock_disponible') + 1
        )
        attribution.delete()
        messages.success(request, "Attribution supprimée et stock restitué.")
        return redirect("liste_attributions")
    return render(request, "gestionepi/confirmer_suppression.html", {"objet": attribution})