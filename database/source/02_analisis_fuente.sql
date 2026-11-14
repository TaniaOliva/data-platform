-- Análisis de la fuente (WideWorldImporters)
USE WideWorldImporters;
GO

-- Consulta 1: tablas por esquema y número de filas
SELECT s.name AS esquema, t.name AS tabla, SUM(p.rows) AS filas
FROM sys.tables AS t
INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
INNER JOIN sys.partitions AS p ON p.object_id = t.object_id AND p.index_id IN (0, 1)
GROUP BY s.name, t.name
ORDER BY s.name, filas DESC;
GO

-- Consulta 2: facturas por año y rango de fechas
SELECT YEAR(InvoiceDate) AS anio,
       COUNT(*) AS facturas,
       MIN(InvoiceDate) AS primera_factura,
       MAX(InvoiceDate) AS ultima_factura
FROM Sales.Invoices
GROUP BY YEAR(InvoiceDate)
ORDER BY anio;
GO

-- Consulta 3: tablas con columna de última edición (para carga incremental)
SELECT TABLE_SCHEMA AS esquema, TABLE_NAME AS tabla, COLUMN_NAME AS columna, DATA_TYPE AS tipo
FROM INFORMATION_SCHEMA.COLUMNS
WHERE COLUMN_NAME = N'LastEditedWhen'
ORDER BY esquema, tabla;
GO

-- Consulta 4: totales de referencia para la reconciliación
SELECT COUNT(*) AS lineas,
       COUNT(DISTINCT InvoiceLineID) AS lineas_distintas,
       SUM(Quantity) AS unidades,
       SUM(ExtendedPrice) AS monto_total
FROM Sales.InvoiceLines;
GO

-- Consulta 5: columnas de auditoría en las tablas de dimensiones
SELECT TABLE_SCHEMA AS esquema, TABLE_NAME AS tabla, COLUMN_NAME AS columna, DATA_TYPE AS tipo
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA + N'.' + TABLE_NAME IN (N'Sales.Customers', N'Warehouse.StockItems', N'Application.People', N'Application.Cities')
  AND COLUMN_NAME IN (N'ValidFrom', N'ValidTo', N'LastEditedWhen')
ORDER BY esquema, tabla, columna;


-- Consulta 6: productos que pertenecen a más de un grupo
SELECT COUNT(*) AS productos_con_mas_de_un_grupo
FROM (
    SELECT StockItemID
    FROM Warehouse.StockItemStockGroups
    GROUP BY StockItemID
    HAVING COUNT(*) > 1
) AS multiples;
GO

-- Consulta 7: grupos de producto y cantidad de productos por grupo
SELECT sg.StockGroupID, sg.StockGroupName, COUNT(*) AS productos
FROM Warehouse.StockItemStockGroups AS sisg
INNER JOIN Warehouse.StockGroups AS sg ON sg.StockGroupID = sisg.StockGroupID
GROUP BY sg.StockGroupID, sg.StockGroupName
ORDER BY productos DESC;
GO

-- Consulta 8: diccionario de columnas de las tablas del análisis
SELECT s.name AS esquema, t.name AS tabla, c.name AS columna,
       TYPE_NAME(c.user_type_id) AS tipo, c.max_length AS longitud,
       c.is_nullable AS permite_nulos
FROM sys.columns AS c
INNER JOIN sys.tables AS t ON t.object_id = c.object_id
INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
WHERE s.name + N'.' + t.name IN (
    N'Sales.Invoices', N'Sales.InvoiceLines', N'Sales.Customers', N'Sales.CustomerCategories',
    N'Warehouse.StockItems', N'Warehouse.StockGroups', N'Warehouse.StockItemStockGroups',
    N'Application.People', N'Application.Cities', N'Application.StateProvinces', N'Application.Countries')
ORDER BY esquema, tabla, c.column_id;
GO