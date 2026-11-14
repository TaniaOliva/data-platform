"""Conexiones a SQL Server."""
import pyodbc

from etl.config import Settings, connection_string


def connect(settings: Settings, database: str, autocommit: bool = False) -> pyodbc.Connection:
    return pyodbc.connect(connection_string(settings, database), autocommit=autocommit)
