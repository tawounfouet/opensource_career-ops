import os
from pathlib import Path

try:
    from dotenv import load_dotenv, find_dotenv

    env_path = find_dotenv(usecwd=False)
    if not env_path:
        env_path = str(Path(__file__).resolve().parent.parent.parent / ".env")
    load_dotenv(env_path)
except ImportError:
    pass

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
application = get_wsgi_application()
