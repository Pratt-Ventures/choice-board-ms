from __future__ import annotations
from pydantic import BaseModel, Field
from typing import ClassVar

from sqlmodel import SQLModel, create_engine
from sqlalchemy import Engine

from ..config.pvf_config_settings import pvf_settings as settings


class PvfDatabaseConnection(BaseModel):
    """Process-global database engine holder.

    The pvf startup logic (pvf_app_runner / pvf_get_alembic_config) establishes the
    connection first and hands the handle to both pvf internals and the application
    via PvfInvocation. Model metadata must be registered (pvf_bootstrap + the
    application's models module) before get_engine() when SQLite create_all is in play.
    """
    db: ClassVar[Engine | None] = None

    @staticmethod
    def get_engine() -> Engine:
        if PvfDatabaseConnection.db is None:
            if not settings.is_prod():
                print(f"Connecting database: {settings.DB_PATH_OR_CONNECTION_STRING}")

            PvfDatabaseConnection.db = create_engine(settings.DB_PATH_OR_CONNECTION_STRING, echo=settings.DB_ECHO_SQL_TO_CONSOLE)

            # In the case we're using a SQLite DB, perform migrations.  Otherwise these will be performed using
            # Alembic.
            if "sqlite" in settings.DB_PATH_OR_CONNECTION_STRING and settings.is_prod() is False and settings.BOOTSTRAP_SAMPLE_DATA:
                SQLModel.metadata.create_all(PvfDatabaseConnection.db)
        return PvfDatabaseConnection.db
