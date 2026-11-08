import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from gestionepi.models import Atelier, Employe, TypeEPI, AttributionEPI

ATELIERS = [
    "Site de Khouribga",
    "Site de Benguerir",
    "Site de Youssoufia",
    "Site de Jorf Lasfar",
    "Site de Safi",
    "Site de Laâyoune (Boucraâ)",
    "Direction Mines",
    "Direction Chimie",
    "Direction Logistique",
    "Direction Maintenance",
]
NOMS = ["Bouazza", "El Amrani", "Chafik", "Ziani", "Benali", "Fassi", "Idrissi", "Tazi", "Naciri", "Kabbaj"]
PRENOMS = ["Ahmed", "Fatima", "Youssef", "Khadija", "Omar", "Salma", "Hamza", "Nadia", "Karim", "Zineb"]
TYPES_EPI = [
    ("Casque de sécurité", 36, 150),
    ("Gants de protection", 2, 40),
    ("Chaussures de sécurité", 12, 250),
    ("Masque respiratoire", 6, 60),
    ("Gilet haute visibilité", 18, 90),
    ("Lunettes de protection", 12, 70),
]


class Command(BaseCommand):
    help = "Génère un jeu de données de démonstration pour l'application EPI"

    def add_arguments(self, parser):
        parser.add_argument("--employes", type=int, default=60)

    def handle(self, *args, **options):
        nb_employes = options["employes"]

        self.stdout.write("Suppression des anciennes données...")
        AttributionEPI.objects.all().delete()
        Employe.objects.all().delete()
        TypeEPI.objects.all().delete()
        Atelier.objects.all().delete()

        self.stdout.write("Création des ateliers...")
        ateliers = [Atelier.objects.create(nom=nom) for nom in ATELIERS]

        self.stdout.write("Création des types d'EPI...")
        types_epi = [
            TypeEPI.objects.create(
                nom=nom, duree_vie_mois=duree, prix_unitaire=prix,
                stock_disponible=nb_employes + random.randint(20, 50)
            )
            for nom, duree, prix in TYPES_EPI
        ]

        self.stdout.write(f"Création de {nb_employes} employés...")
        employes = []
        for i in range(nb_employes):
            e = Employe.objects.create(
                matricule=f"OCP{1000 + i}",
                nom=random.choice(NOMS),
                prenom=random.choice(PRENOMS),
                atelier=random.choice(ateliers),
                date_embauche=date.today() - timedelta(days=random.randint(100, 3000)),
            )
            employes.append(e)

        self.stdout.write("Création des attributions EPI...")
        count = 0
        ruptures = 0
        for employe in employes:
            for type_epi in random.sample(types_epi, k=random.randint(2, 4)):
                # dates réparties dans le passé pour avoir un mix de statuts OK/à renouveler/expiré
                jours_ecoules = random.randint(0, type_epi.duree_vie_mois * 30 + 60)
                date_attrib = date.today() - timedelta(days=jours_ecoules)
                try:
                    AttributionEPI.objects.create(
                        employe=employe, type_epi=type_epi, date_attribution=date_attrib
                    )
                    count += 1
                except ValidationError:
                    ruptures += 1

        self.stdout.write(self.style.SUCCESS(
            f"Terminé : {len(ateliers)} ateliers, {len(types_epi)} types d'EPI, "
            f"{len(employes)} employés, {count} attributions créées "
            f"({ruptures} ignorées faute de stock)."
        ))