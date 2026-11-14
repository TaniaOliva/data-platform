/*
    WWI_Staging - Zonas clean y ready
    Decisiones: D-10, D-18, D-19
    Las tablas raw se crean desde Python (etl/extract) a partir de los metadatos del origen.
    El script se puede ejecutar varias veces sin error.
*/
USE WWI_Staging;
GO
SET QUOTED_IDENTIFIER ON;
GO

/* ===================== Zona clean (validada y limpia) ===================== */
-- Los textos vacíos pasan a NULL; "Desconocido" se aplica en la zona ready (D-19).

IF OBJECT_ID(N'clean.People', N'U') IS NULL
CREATE TABLE clean.People (
    PersonID int NOT NULL CONSTRAINT PK_clean_People PRIMARY KEY,
    FullName nvarchar(50) NULL,
    IsEmployee bit NOT NULL,
    IsSalesperson bit NOT NULL
);
IF OBJECT_ID(N'clean.Countries', N'U') IS NULL
CREATE TABLE clean.Countries (
    CountryID int NOT NULL CONSTRAINT PK_clean_Countries PRIMARY KEY,
    CountryName nvarchar(60) NULL,
    Continent nvarchar(30) NULL,
    Region nvarchar(30) NULL,
    Subregion nvarchar(30) NULL
);
IF OBJECT_ID(N'clean.StateProvinces', N'U') IS NULL
CREATE TABLE clean.StateProvinces (
    StateProvinceID int NOT NULL CONSTRAINT PK_clean_StateProvinces PRIMARY KEY,
    StateProvinceName nvarchar(50) NULL,
    SalesTerritory nvarchar(50) NULL,
    CountryID int NOT NULL
);
IF OBJECT_ID(N'clean.Cities', N'U') IS NULL
CREATE TABLE clean.Cities (
    CityID int NOT NULL CONSTRAINT PK_clean_Cities PRIMARY KEY,
    CityName nvarchar(50) NULL,
    StateProvinceID int NOT NULL
);
IF OBJECT_ID(N'clean.CustomerCategories', N'U') IS NULL
CREATE TABLE clean.CustomerCategories (
    CustomerCategoryID int NOT NULL CONSTRAINT PK_clean_CustomerCategories PRIMARY KEY,
    CustomerCategoryName nvarchar(50) NULL
);
-- Historial completo del cliente: filas actuales y de Customers_Archive
IF OBJECT_ID(N'clean.Customers', N'U') IS NULL
CREATE TABLE clean.Customers (
    CustomerID int NOT NULL,
    ValidFrom datetime2 NOT NULL,
    ValidTo datetime2 NOT NULL,
    CustomerName nvarchar(100) NULL,
    CustomerCategoryID int NOT NULL,
    DeliveryRun nvarchar(5) NULL,
    DeliveryCityID int NOT NULL,
    CONSTRAINT PK_clean_Customers PRIMARY KEY (CustomerID, ValidFrom)
);
IF OBJECT_ID(N'clean.Invoices', N'U') IS NULL
CREATE TABLE clean.Invoices (
    InvoiceID int NOT NULL CONSTRAINT PK_clean_Invoices PRIMARY KEY,
    CustomerID int NOT NULL,
    SalespersonPersonID int NOT NULL,
    InvoiceDate date NOT NULL,
    IsCreditNote bit NOT NULL
);
IF OBJECT_ID(N'clean.InvoiceLines', N'U') IS NULL
CREATE TABLE clean.InvoiceLines (
    InvoiceLineID int NOT NULL CONSTRAINT PK_clean_InvoiceLines PRIMARY KEY,
    InvoiceID int NOT NULL,
    StockItemID int NOT NULL,
    Quantity int NOT NULL,
    UnitPrice decimal(18,2) NULL,
    TaxRate decimal(18,3) NOT NULL,
    TaxAmount decimal(18,2) NOT NULL,
    LineProfit decimal(18,2) NOT NULL,
    ExtendedPrice decimal(18,2) NOT NULL
);
IF OBJECT_ID(N'clean.StockGroups', N'U') IS NULL
CREATE TABLE clean.StockGroups (
    StockGroupID int NOT NULL CONSTRAINT PK_clean_StockGroups PRIMARY KEY,
    StockGroupName nvarchar(50) NULL
);
IF OBJECT_ID(N'clean.StockItems', N'U') IS NULL
CREATE TABLE clean.StockItems (
    StockItemID int NOT NULL CONSTRAINT PK_clean_StockItems PRIMARY KEY,
    StockItemName nvarchar(100) NULL,
    Brand nvarchar(50) NULL,
    Size nvarchar(20) NULL,
    UnitPrice decimal(18,2) NULL,
    TaxRate decimal(18,3) NULL
);
IF OBJECT_ID(N'clean.StockItemStockGroups', N'U') IS NULL
CREATE TABLE clean.StockItemStockGroups (
    StockItemStockGroupID int NOT NULL CONSTRAINT PK_clean_StockItemStockGroups PRIMARY KEY,
    StockItemID int NOT NULL,
    StockGroupID int NOT NULL
);
GO

/* ===================== Zona ready (integración, forma del DW) ===================== */
-- Se recalcula completa desde clean en cada corrida (TRUNCATE + INSERT).

IF OBJECT_ID(N'ready.Customer', N'U') IS NULL
CREATE TABLE ready.Customer (
    CustomerID int NOT NULL,
    ValidFrom datetime2 NOT NULL,
    ValidTo datetime2 NOT NULL,
    CustomerName nvarchar(100) NOT NULL,
    CustomerCategoryName nvarchar(50) NOT NULL,
    DeliveryRun nvarchar(20) NOT NULL,
    City nvarchar(50) NOT NULL,
    StateProvince nvarchar(50) NOT NULL,
    Country nvarchar(60) NOT NULL,
    CONSTRAINT PK_ready_Customer PRIMARY KEY (CustomerID, ValidFrom)
);
IF OBJECT_ID(N'ready.Product', N'U') IS NULL
CREATE TABLE ready.Product (
    StockItemID int NOT NULL CONSTRAINT PK_ready_Product PRIMARY KEY,
    StockItemName nvarchar(100) NOT NULL,
    Brand nvarchar(50) NULL,
    Size nvarchar(20) NULL,
    CatalogUnitPrice decimal(18,2) NULL,
    CatalogTaxRate decimal(18,3) NULL,
    PrimaryStockGroup nvarchar(50) NOT NULL
);
IF OBJECT_ID(N'ready.Employee', N'U') IS NULL
CREATE TABLE ready.Employee (
    PersonID int NOT NULL CONSTRAINT PK_ready_Employee PRIMARY KEY,
    FullName nvarchar(50) NOT NULL
);
IF OBJECT_ID(N'ready.Geography', N'U') IS NULL
CREATE TABLE ready.Geography (
    CityID int NOT NULL CONSTRAINT PK_ready_Geography PRIMARY KEY,
    CityName nvarchar(50) NOT NULL,
    StateProvinceName nvarchar(50) NOT NULL,
    SalesTerritory nvarchar(50) NOT NULL,
    CountryName nvarchar(60) NOT NULL,
    Continent nvarchar(30) NOT NULL,
    Region nvarchar(30) NOT NULL,
    Subregion nvarchar(30) NOT NULL
);
IF OBJECT_ID(N'ready.SalesLine', N'U') IS NULL
CREATE TABLE ready.SalesLine (
    InvoiceLineID int NOT NULL CONSTRAINT PK_ready_SalesLine PRIMARY KEY,
    InvoiceID int NOT NULL,
    InvoiceDate date NOT NULL,
    CustomerID int NOT NULL,
    StockItemID int NOT NULL,
    SalespersonPersonID int NOT NULL,
    DeliveryCityID int NULL,
    Quantity int NOT NULL,
    UnitPrice decimal(18,2) NULL,
    TaxRate decimal(18,3) NOT NULL,
    TaxAmount decimal(18,2) NOT NULL,
    LineProfit decimal(18,2) NOT NULL,
    ExtendedPrice decimal(18,2) NOT NULL
);
GO

SELECT s.name AS [Schema], t.name AS [Table]
FROM sys.tables t JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name IN (N'clean', N'ready') ORDER BY s.name, t.name;
GO
