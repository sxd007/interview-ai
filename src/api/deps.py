from typing import Generator

from sqlalchemy.orm import Session

from src.models import get_db


def get_config():
    from src.core import settings
    return settings


DatabaseDep = Session
