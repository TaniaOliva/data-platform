/*
    WWI_Staging - Esquemas, control, auditoría y cuarentena
    Decisiones: D-16, D-18, D-20, D-22
    El script se puede ejecutar varias veces sin error.
*/
USE WWI_Staging;
GO

-- Esquemas: zonas raw, clean y ready (D-10) y soporte
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'raw')   EXEC (N'CREATE SCHEMA raw');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'clean') EXEC (N'CREATE SCHEMA clean');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'ready') EXEC (N'CREATE SCHEMA ready');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'ctl')   EXEC (N'CREATE SCHEMA ctl');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'audit') EXEC (N'CREATE SCHEMA audit');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'stg')   EXEC (N'CREATE SCHEMA stg');
GO

-- Marca de carga por tabla de origen (D-16)
IF OBJECT_ID(N'ctl.Watermark', N'U') IS NULL
CREATE TABLE ctl.Watermark
(
    TableName     nvarchar(128) NOT NULL,
    LastWatermark datetime2     NOT NULL,
    UpdatedAt     datetime2     NOT NULL CONSTRAINT DF_Watermark_UpdatedAt DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT PK_Watermark PRIMARY KEY CLUSTERED (TableName)
);
GO

-- Una fila por corrida del pipeline (D-22)
IF OBJECT_ID(N'audit.Execution', N'U') IS NULL
CREATE TABLE audit.Execution
(
    ExecutionID  bigint IDENTITY(1,1) NOT NULL,
    PipelineName nvarchar(100) NOT NULL,
    StartTime    datetime2     NOT NULL CONSTRAINT DF_Execution_StartTime DEFAULT (SYSUTCDATETIME()),
    EndTime      datetime2     NULL,
    Status       nvarchar(20)  NOT NULL CONSTRAINT DF_Execution_Status DEFAULT (N'running'),
    ErrorDetail  nvarchar(max) NULL,
    CONSTRAINT PK_Execution PRIMARY KEY CLUSTERED (ExecutionID),
    CONSTRAINT CK_Execution_Status CHECK (Status IN (N'running', N'success', N'failed'))
);
GO

-- Una fila por etapa dentro de una corrida (D-22)
IF OBJECT_ID(N'audit.Step', N'U') IS NULL
CREATE TABLE audit.Step
(
    StepID         bigint IDENTITY(1,1) NOT NULL,
    ExecutionID    bigint        NOT NULL,
    StepName       nvarchar(100) NOT NULL,
    StartTime      datetime2     NOT NULL CONSTRAINT DF_Step_StartTime DEFAULT (SYSUTCDATETIME()),
    EndTime        datetime2     NULL,
    SourceObject   nvarchar(256) NULL,
    TargetObject   nvarchar(256) NULL,
    RowsRead       int           NULL,
    RowsInserted   int           NULL,
    RowsUpdated    int           NULL,
    RowsRejected   int           NULL,
    Status         nvarchar(20)  NOT NULL CONSTRAINT DF_Step_Status DEFAULT (N'running'),
    ErrorDetail    nvarchar(max) NULL,
    WatermarkStart datetime2     NULL,
    WatermarkEnd   datetime2     NULL,
    CONSTRAINT PK_Step PRIMARY KEY CLUSTERED (StepID),
    CONSTRAINT FK_Step_Execution FOREIGN KEY (ExecutionID) REFERENCES audit.Execution (ExecutionID),
    CONSTRAINT CK_Step_Status CHECK (Status IN (N'running', N'success', N'failed'))
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_Step_ExecutionID' AND object_id = OBJECT_ID(N'audit.Step'))
    CREATE NONCLUSTERED INDEX IX_Step_ExecutionID ON audit.Step (ExecutionID);
GO

-- Registros rechazados por reglas de calidad (D-18)
IF OBJECT_ID(N'stg.Quarantine', N'U') IS NULL
CREATE TABLE stg.Quarantine
(
    QuarantineID   bigint IDENTITY(1,1) NOT NULL,
    SourceName     nvarchar(256) NOT NULL,   -- fuente (tabla de origen)
    QuarantineDate datetime2     NOT NULL CONSTRAINT DF_Quarantine_Date DEFAULT (SYSUTCDATETIME()),
    ExecutionID    bigint        NOT NULL,
    RuleID         nvarchar(50)  NOT NULL,   -- regla fallida
    Detail         nvarchar(max) NULL,
    CONSTRAINT PK_Quarantine PRIMARY KEY CLUSTERED (QuarantineID),
    CONSTRAINT FK_Quarantine_Execution FOREIGN KEY (ExecutionID) REFERENCES audit.Execution (ExecutionID)
);
GO

-- Verificación
SELECT s.name AS [Schema], t.name AS [Table]
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name IN (N'raw', N'clean', N'ready', N'ctl', N'audit', N'stg')
ORDER BY s.name, t.name;
GO
