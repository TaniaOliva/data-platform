# Plataforma de Ingeniería de Datos y Analítica Inteligente

Solución de extremo a extremo que toma datos operacionales de una base relacional, los limpia en una zona de staging, los carga en un Data Warehouse dimensional en SQL Server y los expone mediante un dashboard, un modelo predictivo, un asistente de consultas y alertas.

El proyecto se ejecuta en local, sin Docker (decisión D-15).

## Estructura

```
data-platform/
├── backups/          Respaldos .bak (no se versionan)
├── backend/          API con FastAPI
├── database/
│   ├── source/       Análisis de la base de origen
│   ├── staging/      Esquemas de WWI_Staging
│   ├── warehouse/    Esquema dimensional de WWI_DW
│   └── scripts/      Creación de bases y utilidades
├── deployment/       Scripts de despliegue (run_all.ps1)
├── documentation/    Decisiones técnicas, diagramas y manuales
├── etl/              Pipelines de extracción, staging y carga
├── frontend/         Dashboard en React
├── generative-ai/    Asistente de consultas
├── machine-learning/ Entrenamiento y evaluación del pronóstico
├── notifications/    Reglas y envío de alertas
└── tests/            Pruebas automatizadas
```

## Requisitos

- Windows con SQL Server 2022 y una instancia llamada `.\SQLTANIA`
- `sqlcmd` (herramientas de línea de comandos de SQL Server) y SQL Server Management Studio, opcional
- ODBC Driver 17 o 18 for SQL Server
- Python 3.11 o superior (ETL, API y modelo)
- Node.js 20 o superior (frontend)
- Al menos 8 GB de RAM y unos 3 GB de disco libre
- El respaldo `WideWorldImporters-Full.bak`, del release `wide-world-importers-v1.0` de `microsoft/sql-server-samples`, en la carpeta `backups/`

## Variables de entorno

Copiar `.env.example` como `.env`. El archivo `.env` no se versiona.

| Variable | Descripción |
|---|---|
| `SQL_SERVER` | Instancia de SQL Server. Valor: `.\SQLTANIA` |
| `SQL_DRIVER` | Driver ODBC usado por Python |
| `SQL_TRUSTED_CONNECTION` | `yes`: autenticación de Windows (Trusted_Connection) |
| `SQL_TRUST_SERVER_CERTIFICATE` | `yes` para aceptar el certificado local |
| `SQL_SOURCE_DB` | Base de origen: `WideWorldImporters` |
| `SQL_STAGING_DB` | Base de staging: `WWI_Staging` |
| `SQL_DW_DB` | Base del Data Warehouse: `WWI_DW` |

## Orden de ejecución de los scripts

Todos los comandos se ejecutan desde la raíz del repositorio, en PowerShell. `-E` usa autenticación de Windows, `-C` acepta el certificado local e `-I` activa `QUOTED_IDENTIFIER`.

**1. Restaurar WideWorldImporters.** Revisar primero los nombres lógicos del respaldo:

```powershell
sqlcmd -S ".\SQLTANIA" -E -C -Q "RESTORE FILELISTONLY FROM DISK = 'C:\Proyectos\data-platform\backups\WideWorldImporters-Full.bak'"
```

Luego restaurar, ajustando los `MOVE` a los nombres obtenidos y las rutas a la carpeta de datos de la instancia (`<RUTA_DATOS>`):

```powershell
sqlcmd -S ".\SQLTANIA" -E -C -Q "RESTORE DATABASE WideWorldImporters FROM DISK = 'C:\Proyectos\data-platform\backups\WideWorldImporters-Full.bak' WITH MOVE 'WWI_Primary' TO '<RUTA_DATOS>\WideWorldImporters.mdf', MOVE 'WWI_UserData' TO '<RUTA_DATOS>\WideWorldImporters_UserData.ndf', MOVE 'WWI_Log' TO '<RUTA_DATOS>\WideWorldImporters.ldf', MOVE 'WWI_InMemory_Data_1' TO '<RUTA_DATOS>\WideWorldImporters_InMemory_Data_1', STATS = 10"
```

**2. Crear las bases de staging y Data Warehouse.**

```powershell
sqlcmd -S ".\SQLTANIA" -E -C -I -b -i database\scripts\01_create_databases.sql
```

**3. Analizar la fuente (solo lectura).**

```powershell
sqlcmd -S ".\SQLTANIA" -E -C -I -b -i database\source\02_analisis_fuente.sql
```

**4. Crear los esquemas de staging.**

```powershell
sqlcmd -S ".\SQLTANIA" -E -C -I -b -i database\staging\01_staging_schemas.sql
```

**5. Crear el modelo dimensional.**

```powershell
sqlcmd -S ".\SQLTANIA" -E -C -I -b -i database\warehouse\01_dw_schemas.sql
```

Los scripts de los pasos 2, 4 y 5 se pueden ejecutar varias veces sin error.

**6. Resto del flujo.** Cuando estén construidos, `deployment\run_all.ps1` ejecuta en orden el ETL, la validación, el modelo, la carga del DW y las alertas.

## Verificación

Después de los pasos 2, 4 y 5:

```powershell
sqlcmd -S ".\SQLTANIA" -E -C -Q "SELECT name, state_desc FROM sys.databases WHERE name IN ('WideWorldImporters','WWI_Staging','WWI_DW')"
```

Las tres bases deben aparecer en estado `ONLINE`.

## Decisiones

El registro completo de decisiones, con sus alternativas descartadas y su motivo, está en `documentation/decisiones.md`.
