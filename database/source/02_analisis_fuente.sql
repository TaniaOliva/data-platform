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