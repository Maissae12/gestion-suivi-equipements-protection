"""
WSGI config for gestion_suivi_des_equipements_protection project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "gestion_suivi_des_equipements_protection.settings"
)

application = get_wsgi_application()
