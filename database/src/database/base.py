"""Declarative base shared by every ORM model.

Alembic autogenerate reads metadata from here, so any model module must be
imported before a migration is generated.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all canonical financial models."""
