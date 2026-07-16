#!/usr/bin/env python
import os
import sys
from pathlib import Path


def main() -> None:
    try:
        from dotenv import load_dotenv, find_dotenv

        env_path = find_dotenv(usecwd=False)
        if not env_path:
            env_path = str(Path(__file__).resolve().parent.parent / ".env")
        load_dotenv(env_path)
    except ImportError:
        pass
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
