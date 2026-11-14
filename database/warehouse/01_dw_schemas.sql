/*
    WWI_DW - Esquemas, dimensiones y tabla de hechos
    Decisiones: D-10, D-14, D-17, D-19, D-21, D-25
    El script se puede ejecutar varias veces sin error.
*/
USE WWI_DW;
GO
-- Requerido por el índice filtrado; sqlcmd lo deja en OFF por defecto
SET QUOTED_IDENTIFIER ON;
GO

-- Esquemas
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'dim')
    EXEC (N'CREATE SCHEMA dim');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'fact')
    EXEC (N'CREATE SCHEMA fact');
GO

/* ---------------------------------------------------------------
   dim.DimDate (se genera una sola vez, D-21)
   --------------------------------------------------------------- */
IF OBJECT_ID(N'dim.DimDate', N'U') IS NULL
CREATE TABLE dim.DimDate
(
    DateKey    int          NOT NULL,   -- formato yyyymmdd
    [Date]     date         NOT NULL,
    [Day]      tinyint      NOT NULL,
    [Month]    tinyint      NOT NULL,
    MonthName  nvarchar(20) NOT NULL,
    [Quarter]  tinyint      NOT NULL,
    [Year]     smallint     NOT NULL,
    IsWeekend  bit          NOT NULL,
    CONSTRAINT PK_DimDate PRIMARY KEY CLUSTERED (DateKey)
);
GO

-- Miembro desconocido (D-19)
IF NOT EXISTS (SELECT 1 FROM dim.DimDate WHERE DateKey = 0)
    INSERT INTO dim.DimDate (DateKey, [Date], [Day], [Month], MonthName, [Quarter], [Year], IsWeekend)
    VALUES (0, '1900-01-01', 0, 0, N'Desconocido', 0, 0, 0);
GO

/* ---------------------------------------------------------------
   dim.DimCustomer (SCD tipo 2, D-21)
   --------------------------------------------------------------- */
IF OBJECT_ID(N'dim.DimCustomer', N'U') IS NULL
CREATE TABLE dim.DimCustomer
(
    CustomerKey          int IDENTITY(1,1) NOT NULL,   -- llave sustituta
    CustomerID           int           NOT NULL,       -- llave natural
    CustomerName         nvarchar(100) NOT NULL,
    CustomerCategoryName nvarchar(50)  NOT NULL,
    DeliveryRun          nvarchar(20)  NULL,   -- ancho 20 para caber "Desconocido"
    City                 nvarchar(50)  NOT NULL,
    StateProvince        nvarchar(50)  NOT NULL,
    Country              nvarchar(60)  NOT NULL,
    ValidFrom            datetime2     NOT NULL,
    ValidTo              datetime2     NOT NULL,
    IsCurrent            bit           NOT NULL,
    CONSTRAINT PK_DimCustomer PRIMARY KEY CLUSTERED (CustomerKey)
);
GO

-- Solo una versión vigente por cliente
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_DimCustomer_Current' AND object_id = OBJECT_ID(N'dim.DimCustomer'))
    CREATE UNIQUE NONCLUSTERED INDEX UX_DimCustomer_Current
        ON dim.DimCustomer (CustomerID) WHERE IsCurrent = 1;
GO

-- Una fila por versión (cliente + inicio de vigencia); base del MERGE de SCD tipo 2
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_DimCustomer_Version' AND object_id = OBJECT_ID(N'dim.DimCustomer'))
    CREATE UNIQUE NONCLUSTERED INDEX UX_DimCustomer_Version
        ON dim.DimCustomer (CustomerID, ValidFrom);
GO

IF NOT EXISTS (SELECT 1 FROM dim.DimCustomer WHERE CustomerKey = 0)
BEGIN
    SET IDENTITY_INSERT dim.DimCustomer ON;
    INSERT INTO dim.DimCustomer
        (CustomerKey, CustomerID, CustomerName, CustomerCategoryName, DeliveryRun,
         City, StateProvince, Country, ValidFrom, ValidTo, IsCurrent)
    VALUES
        (0, 0, N'Desconocido', N'Desconocido', N'Desconocido',
         N'Desconocido', N'Desconocido', N'Desconocido', '1900-01-01', '9999-12-31', 1);
    SET IDENTITY_INSERT dim.DimCustomer OFF;
END
GO

/* ---------------------------------------------------------------
   dim.DimProduct (SCD tipo 1; grupo principal = menor StockGroupID, D-25)
   --------------------------------------------------------------- */
IF OBJECT_ID(N'dim.DimProduct', N'U') IS NULL
CREATE TABLE dim.DimProduct
(
    ProductKey        int IDENTITY(1,1) NOT NULL,
    StockItemID       int            NOT NULL,
    StockItemName     nvarchar(100)  NOT NULL,
    Brand             nvarchar(50)   NULL,
    Size              nvarchar(20)   NULL,
    CatalogUnitPrice  decimal(18,2)  NULL,   -- precio de catálogo actual (D-28); NULL en el miembro desconocido (D-19)
    CatalogTaxRate    decimal(18,3)  NULL,   -- tasa de catálogo actual (D-28)
    PrimaryStockGroup nvarchar(50)   NOT NULL,
    CONSTRAINT PK_DimProduct PRIMARY KEY CLUSTERED (ProductKey),
    CONSTRAINT UQ_DimProduct_StockItemID UNIQUE (StockItemID)
);
GO

-- Migración D-28: renombra columnas si la tabla se creó con los nombres anteriores
IF COL_LENGTH(N'dim.DimProduct', N'UnitPrice') IS NOT NULL
    EXEC sp_rename N'dim.DimProduct.UnitPrice', N'CatalogUnitPrice', N'COLUMN';
IF COL_LENGTH(N'dim.DimProduct', N'TaxRate') IS NOT NULL
    EXEC sp_rename N'dim.DimProduct.TaxRate', N'CatalogTaxRate', N'COLUMN';
GO

IF NOT EXISTS (SELECT 1 FROM dim.DimProduct WHERE ProductKey = 0)
BEGIN
    SET IDENTITY_INSERT dim.DimProduct ON;
    INSERT INTO dim.DimProduct
        (ProductKey, StockItemID, StockItemName, Brand, Size, CatalogUnitPrice, CatalogTaxRate, PrimaryStockGroup)
    VALUES
        (0, 0, N'Desconocido', N'Desconocido', N'Desconocido', NULL, NULL, N'Desconocido');
    SET IDENTITY_INSERT dim.DimProduct OFF;
END
GO

/* ---------------------------------------------------------------
   dim.DimEmployee (SCD tipo 1; solo personas con IsEmployee = 1)
   --------------------------------------------------------------- */
IF OBJECT_ID(N'dim.DimEmployee', N'U') IS NULL
CREATE TABLE dim.DimEmployee
(
    EmployeeKey int IDENTITY(1,1) NOT NULL,
    PersonID    int           NOT NULL,
    FullName    nvarchar(50)  NOT NULL,
    CONSTRAINT PK_DimEmployee PRIMARY KEY CLUSTERED (EmployeeKey),
    CONSTRAINT UQ_DimEmployee_PersonID UNIQUE (PersonID)
);
GO

IF NOT EXISTS (SELECT 1 FROM dim.DimEmployee WHERE EmployeeKey = 0)
BEGIN
    SET IDENTITY_INSERT dim.DimEmployee ON;
    INSERT INTO dim.DimEmployee (EmployeeKey, PersonID, FullName)
    VALUES (0, 0, N'Desconocido');
    SET IDENTITY_INSERT dim.DimEmployee OFF;
END
GO

/* ---------------------------------------------------------------
   dim.DimGeography (aplanada, D-10; SCD tipo 1)
   --------------------------------------------------------------- */
IF OBJECT_ID(N'dim.DimGeography', N'U') IS NULL
CREATE TABLE dim.DimGeography
(
    GeographyKey      int IDENTITY(1,1) NOT NULL,
    CityID            int           NOT NULL,
    CityName          nvarchar(50)  NOT NULL,
    StateProvinceName nvarchar(50)  NOT NULL,
    SalesTerritory    nvarchar(50)  NOT NULL,
    CountryName       nvarchar(60)  NOT NULL,
    Continent         nvarchar(30)  NOT NULL,
    Region            nvarchar(30)  NOT NULL,
    Subregion         nvarchar(30)  NOT NULL,
    CONSTRAINT PK_DimGeography PRIMARY KEY CLUSTERED (GeographyKey),
    CONSTRAINT UQ_DimGeography_CityID UNIQUE (CityID)
);
GO

IF NOT EXISTS (SELECT 1 FROM dim.DimGeography WHERE GeographyKey = 0)
BEGIN
    SET IDENTITY_INSERT dim.DimGeography ON;
    INSERT INTO dim.DimGeography
        (GeographyKey, CityID, CityName, StateProvinceName, SalesTerritory,
         CountryName, Continent, Region, Subregion)
    VALUES
        (0, 0, N'Desconocido', N'Desconocido', N'Desconocido',
         N'Desconocido', N'Desconocido', N'Desconocido', N'Desconocido');
    SET IDENTITY_INSERT dim.DimGeography OFF;
END
GO

/* ---------------------------------------------------------------
   Particionado anual de la tabla de hechos (D-17)
   RANGE RIGHT sobre DateKey: <2014 | 2014 | 2015 | >=2016
   --------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM sys.partition_functions WHERE name = N'pf_SalesYear')
    CREATE PARTITION FUNCTION pf_SalesYear (int)
    AS RANGE RIGHT FOR VALUES (20140101, 20150101, 20160101);
GO

IF NOT EXISTS (SELECT 1 FROM sys.partition_schemes WHERE name = N'ps_SalesYear')
    CREATE PARTITION SCHEME ps_SalesYear
    AS PARTITION pf_SalesYear ALL TO ([PRIMARY]);
GO

/* ---------------------------------------------------------------
   fact.FactSales: una fila por línea de factura (D-10)
   La llave primaria incluye DateKey porque SQL Server exige que la
   columna de partición forme parte de un índice único alineado.
   InvoiceLineID es la clave de negocio para el MERGE (D-16, D-21).
   --------------------------------------------------------------- */
IF OBJECT_ID(N'fact.FactSales', N'U') IS NULL
CREATE TABLE fact.FactSales
(
    InvoiceLineID int           NOT NULL,   -- clave de negocio
    DateKey       int           NOT NULL CONSTRAINT DF_FactSales_DateKey      DEFAULT (0),
    CustomerKey   int           NOT NULL CONSTRAINT DF_FactSales_CustomerKey  DEFAULT (0),
    ProductKey    int           NOT NULL CONSTRAINT DF_FactSales_ProductKey   DEFAULT (0),
    EmployeeKey   int           NOT NULL CONSTRAINT DF_FactSales_EmployeeKey  DEFAULT (0),
    GeographyKey  int           NOT NULL CONSTRAINT DF_FactSales_GeographyKey DEFAULT (0),
    Quantity      int           NOT NULL,
    UnitPrice     decimal(18,2) NULL,       -- nullable en el origen
    TaxRate       decimal(18,3) NOT NULL,
    TaxAmount     decimal(18,2) NOT NULL,
    LineProfit    decimal(18,2) NOT NULL,
    ExtendedPrice decimal(18,2) NOT NULL,
    CONSTRAINT PK_FactSales PRIMARY KEY CLUSTERED (DateKey, InvoiceLineID)
        ON ps_SalesYear (DateKey),
    CONSTRAINT FK_FactSales_DimDate      FOREIGN KEY (DateKey)      REFERENCES dim.DimDate (DateKey),
    CONSTRAINT FK_FactSales_DimCustomer  FOREIGN KEY (CustomerKey)  REFERENCES dim.DimCustomer (CustomerKey),
    CONSTRAINT FK_FactSales_DimProduct   FOREIGN KEY (ProductKey)   REFERENCES dim.DimProduct (ProductKey),
    CONSTRAINT FK_FactSales_DimEmployee  FOREIGN KEY (EmployeeKey)  REFERENCES dim.DimEmployee (EmployeeKey),
    CONSTRAINT FK_FactSales_DimGeography FOREIGN KEY (GeographyKey) REFERENCES dim.DimGeography (GeographyKey)
) ON ps_SalesYear (DateKey);
GO

-- Índices de apoyo para las uniones con las dimensiones
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_FactSales_CustomerKey' AND object_id = OBJECT_ID(N'fact.FactSales'))
    CREATE NONCLUSTERED INDEX IX_FactSales_CustomerKey ON fact.FactSales (CustomerKey) ON ps_SalesYear (DateKey);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_FactSales_ProductKey' AND object_id = OBJECT_ID(N'fact.FactSales'))
    CREATE NONCLUSTERED INDEX IX_FactSales_ProductKey ON fact.FactSales (ProductKey) ON ps_SalesYear (DateKey);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_FactSales_InvoiceLineID' AND object_id = OBJECT_ID(N'fact.FactSales'))
    CREATE NONCLUSTERED INDEX IX_FactSales_InvoiceLineID ON fact.FactSales (InvoiceLineID);
GO

-- Verificación
SELECT s.name AS [Schema], t.name AS [Table]
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name IN (N'dim', N'fact')
ORDER BY s.name, t.name;

SELECT p.partition_number, rv.value AS UpperBoundExclusive, p.rows
FROM sys.partitions p
JOIN sys.indexes i ON i.object_id = p.object_id AND i.index_id = p.index_id
LEFT JOIN sys.partition_schemes ps ON ps.data_space_id = i.data_space_id
LEFT JOIN sys.partition_range_values rv ON rv.function_id = ps.function_id AND rv.boundary_id = p.partition_number
WHERE p.object_id = OBJECT_ID(N'fact.FactSales') AND i.index_id = 1
ORDER BY p.partition_number;
GO
