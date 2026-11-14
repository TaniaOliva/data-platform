"""Configuración de conexión. Lee variables de entorno (.env); no guarda secretos."""
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv es opcional
    pass

# Días de solapamiento de la carga incremental (D-16)
OVERLAP_DAYS = 3
# Valor mínimo de la marca de carga (carga inicial)
MIN_WATERMARK = "0001-01-01T00:00:00"


@dataclass(frozen=True)
class Settings:
    server: str
    driver: str
    trust_cert: str
    source_db: str
    staging_db: str
    dw_db: str


def load_settings() -> Settings:
    env = os.environ.get
    return Settings(
        server=env("SQL_SERVER", r".\SQLTANIA"),
        driver=env("SQL_DRIVER", "ODBC Driver 17 for SQL Server"),
        trust_cert=env("SQL_TRUST_SERVER_CERTIFICATE", "yes"),
        source_db=env("SQL_SOURCE_DB", "WideWorldImporters"),
        staging_db=env("SQL_STAGING_DB", "WWI_Staging"),
        dw_db=env("SQL_DW_DB", "WWI_DW"),
    )


def connection_string(settings: Settings, database: str) -> str:
    """Autenticación de Windows (Trusted_Connection); sin usuario ni contraseña."""
    return (
        f"DRIVER={{{settings.driver}}};SERVER={settings.server};DATABASE={database};"
        f"Trusted_Connection=yes;TrustServerCertificate={settings.trust_cert}"
    )
