from django.db import models
from django.core.exceptions import ValidationError
from datetime import date, timedelta

class TypeEPI(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    duree_vie_mois = models.PositiveIntegerField(help_text="Durée de vie standard en mois")
    prix_unitaire = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    stock_disponible = models.PositiveIntegerField(default=0)
    seuil_alerte = models.PositiveIntegerField(default=10, help_text="Alerte si le stock descend sous ce seuil")

    def __str__(self):
        return self.nom

    class Meta:
        verbose_name = "Type d'EPI"
        verbose_name_plural = "Types d'EPI"
        ordering = ["nom"]
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




class AttributionEPI(models.Model):
    """Table centrale : attribution d'un équipement à un employé, avec suivi du statut."""

    class Statut(models.TextChoices):
        OK = "OK", "OK"
        A_RENOUVELER = "A_RENOUVELER", "À renouveler bientôt"
        EXPIRE = "EXPIRE", "Expiré"

    class MotifCloture(models.TextChoices):
        EXPIRATION = "EXPIRATION", "Expiration normale"
        PERTE = "PERTE", "Perte"
        DOMMAGE = "DOMMAGE", "Endommagé / déchiré"

    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name="attributions")
    type_epi = models.ForeignKey(TypeEPI, on_delete=models.PROTECT, related_name="attributions")
    date_attribution = models.DateField(default=date.today)
    date_expiration = models.DateField(editable=False, null=True, blank=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.OK, editable=False)
    actif = models.BooleanField(default=True)
    date_cloture = models.DateField(null=True, blank=True, editable=False)
    motif_cloture = models.CharField(max_length=20, choices=MotifCloture.choices, null=True, blank=True, editable=False)

    def save(self, *args, **kwargs):
        est_nouveau = self.pk is None
        if not self.date_expiration:
            self.date_expiration = self.date_attribution + timedelta(days=self.type_epi.duree_vie_mois * 30)
        self.statut = self.calculer_statut()

        if est_nouveau and self.type_epi.stock_disponible <= 0:
            raise ValidationError(
                f"Stock insuffisant pour '{self.type_epi.nom}' (stock disponible : 0)."
            )

        super().save(*args, **kwargs)
        if est_nouveau:
            TypeEPI.objects.filter(pk=self.type_epi.pk).update(
                stock_disponible=models.F('stock_disponible') - 1
            )
            self.type_epi.refresh_from_db()
    def calculer_statut(self):
        aujourdhui = date.today()
        if self.date_expiration < aujourdhui:
            return self.Statut.EXPIRE
        elif self.date_expiration < aujourdhui + timedelta(days=30):
            return self.Statut.A_RENOUVELER
        return self.Statut.OK
    def _cloturer_et_remplacer(self, motif):
        """Clôture l'attribution actuelle avec un motif donné et en crée une nouvelle."""
        self.actif = False
        self.date_cloture = date.today()
        self.motif_cloture = motif
        self.save()
        return AttributionEPI.objects.create(
            employe=self.employe,
            type_epi=self.type_epi,
            date_attribution=date.today(),
        )

    def renouveler(self):
        """Renouvellement normal : l'équipement arrive en fin de vie (expiré ou bientôt)."""
        return self._cloturer_et_remplacer(self.MotifCloture.EXPIRATION)

    def declarer_incident(self, motif):
        """Déclaration de perte ou de dommage : remplace l'équipement avant son expiration prévue.
        motif doit être MotifCloture.PERTE ou MotifCloture.DOMMAGE."""
        return self._cloturer_et_remplacer(motif)

    def __str__(self):
        return f"{self.type_epi} - {self.employe} ({self.statut})"

    class Meta:
        verbose_name = "Attribution EPI"
        verbose_name_plural = "Attributions EPI"
        ordering = ["date_expiration"]
        constraints = [
            models.UniqueConstraint(
                fields=["employe", "type_epi"],
                condition=models.Q(actif=True),
                name="un_seul_epi_actif_par_type_et_employe",
            )
        ]