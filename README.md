# Plataforma de Ingeniería de Datos y Analítica Inteligente

Solución de extremo a extremo que toma datos operacionales de una base relacional, los limpia en una zona de staging, los carga en un Data Warehouse dimensional en SQL Server y los expone mediante un dashboard, un modelo predictivo, un asistente de consultas y alertas.

**Estado actual:** paso 1 de 11 (ambiente).

## Estructura

```
data-platform/
├── backups/          Respaldos .bak (no se versionan)
├── backend/          API con FastAPI
├── database/
│   ├── source/       Scripts de la base de origen
│   ├── staging/      Scripts de la zona de staging
│   ├── data-warehouse/  Esquema dimensional
│   └── scripts/      Scripts de creación de bases y utilidades
├── deployment/       Configuración de despliegue
├── documentation/    Decisiones técnicas, diagramas y manuales
├── etl/              Pipelines de extracción, staging y carga
├── frontend/         Dashboard en React
├── generative-ai/    Asistente de consultas
├── machine-learning/ Entrenamiento y evaluación del pronóstico
├── notifications/    Reglas y envío de alertas
└── tests/            Pruebas automatizadas
```

## Requisitos

- Docker Desktop (o Docker Engine en Linux)
- Espacio libre de unos 3 GB para la imagen de SQL Server y la base de datos
- Al menos 8 GB de RAM

## Levantar el ambiente (paso 1)

**1. Crear el archivo de variables.** Copiar `.env.example` como `.env` y cambiar la contraseña de `MSSQL_SA_PASSWORD`.

**2. Descargar el respaldo de origen.** Bajar `WideWorldImporters-Full.bak` desde el release `wide-world-importers-v1.0` del repositorio `microsoft/sql-server-samples` y colocarlo en la carpeta `backups/`.

**3. Levantar SQL Server.**

```bash
docker compose up -d
```

**4. Revisar los nombres lógicos del respaldo.** Reemplazar `TU_CLAVE` por la contraseña del `.env`.

```bash
docker exec dp_sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "TU_CLAVE" -C -Q "RESTORE FILELISTONLY FROM DISK = '/var/opt/mssql/backup/WideWorldImporters-Full.bak'"
```

Anotar la columna `LogicalName` de cada fila.

**5. Restaurar WideWorldImporters.** Los nombres de la cláusula `MOVE` deben coincidir con el paso anterior. Si la salida tiene más archivos, agregar una línea `MOVE` por cada uno.

```bash
docker exec dp_sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "TU_CLAVE" -C -Q "RESTORE DATABASE WideWorldImporters FROM DISK = '/var/opt/mssql/backup/WideWorldImporters-Full.bak' WITH MOVE 'WWI_Primary' TO '/var/opt/mssql/data/WideWorldImporters.mdf', MOVE 'WWI_UserData' TO '/var/opt/mssql/data/WideWorldImporters_UserData.ndf', MOVE 'WWI_Log' TO '/var/opt/mssql/data/WideWorldImporters.ldf', MOVE 'WWI_InMemory_Data_1' TO '/var/opt/mssql/data/WideWorldImporters_InMemory_Data_1', STATS = 10"
```

**6. Crear las bases de staging y Data Warehouse.**

```bash
docker exec dp_sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "TU_CLAVE" -C -i /scripts/01_create_databases.sql
```

**7. Verificar.** La salida del paso 6 debe listar `WideWorldImporters`, `WWI_Staging` y `WWI_DW` en estado `ONLINE`.

## Decisiones

El registro completo de decisiones, con sus alternativas descartadas y su motivo, está en `documentation/decisiones.md`. Las preguntas pendientes para el docente están en `documentation/preguntas_docente.md`.
