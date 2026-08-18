from __future__ import annotations

import argparse
import re

import psycopg
from psycopg import sql

from app.core.config import settings

_SAFE_TEST_DATABASE = re.compile(r"^[A-Za-z0-9_]+_test$")


def _validated_database_name() -> str:
    name = settings.POSTGRES_DB
    if _SAFE_TEST_DATABASE.fullmatch(name) is None:
        raise RuntimeError(
            "Refusing to manage a database that does not end in '_test'"
        )
    return name


def _maintenance_connection() -> psycopg.Connection[tuple[object, ...]]:
    return psycopg.connect(
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        dbname="postgres",
        autocommit=True,
    )


def create_database(name: str) -> None:
    with _maintenance_connection() as connection:
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(name)
            )
        )
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def drop_database(name: str) -> None:
    with _maintenance_connection() as connection:
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(name)
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("create", "drop"))
    args = parser.parse_args()
    database_name = _validated_database_name()
    if args.action == "create":
        create_database(database_name)
    else:
        drop_database(database_name)


if __name__ == "__main__":
    main()
