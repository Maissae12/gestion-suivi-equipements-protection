from django.db import models
from datetime import date, timedelta


class Atelier(models.Model):
    """Représente un atelier/service du site (ex: Concassage, Broyage, Laverie...)."""
    nom = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nom

    class Meta:
        verbose_name = "Atelier"
        verbose_name_plural = "Ateliers"
        ordering = ["nom"]


class Employe(models.Model):
    """Un employé du site, rattaché à un atelier."""
    matricule = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    atelier = models.ForeignKey(Atelier, on_delete=models.PROTECT, related_name="employes")
    date_embauche = models.DateField()

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.matricule})"

    class Meta:
        verbose_name = "Employé"
        verbose_name_plural = "Employés"
        ordering = ["nom", "prenom"]


class TypeEPI(models.Model):
    """Catalogue des types d'équipements de protection individuelle."""
    nom = models.CharField(max_length=100, unique=True)
    duree_vie_mois = models.PositiveIntegerField(help_text="Durée de vie standard en mois")
    prix_unitaire = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    stock_disponible = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.nom

    class Meta:
        verbose_name = "Type d'EPI"
        verbose_name_plural = "Types d'EPI"
        ordering = ["nom"]


class AttributionEPI(models.Model):
    """Table centrale : attribution d'un équipement à un employé, avec suivi du statut."""

    class Statut(models.TextChoices):
        OK = "OK", "OK"
        A_RENOUVELER = "A_RENOUVELER", "À renouveler bientôt"
        EXPIRE = "EXPIRE", "Expiré"

    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name="attributions")
    type_epi = models.ForeignKey(TypeEPI, on_delete=models.PROTECT, related_name="attributions")
    date_attribution = models.DateField(default=date.today)
    date_expiration = models.DateField(editable=False, null=True, blank=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.OK, editable=False)
    actif = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.date_expiration:
            self.date_expiration = self.date_attribution + timedelta(days=self.type_epi.duree_vie_mois * 30)
        self.statut = self.calculer_statut()
        super().save(*args, **kwargs)

    def calculer_statut(self):
        aujourdhui = date.today()
        if self.date_expiration < aujourdhui:
            return self.Statut.EXPIRE
        elif self.date_expiration < aujourdhui + timedelta(days=30):
            return self.Statut.A_RENOUVELER
        return self.Statut.OK

    def renouveler(self):
        self.actif = False
        self.save()
        return AttributionEPI.objects.create(
            employe=self.employe,
            type_epi=self.type_epi,
            date_attribution=date.today(),
        )

    def __str__(self):
        return f"{self.type_epi} - {self.employe} ({self.statut})"

    class Meta:
        verbose_name = "Attribution EPI"
        verbose_name_plural = "Attributions EPI"
        ordering = ["date_expiration"]
