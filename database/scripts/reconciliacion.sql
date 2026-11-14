/*
    Reconciliación origen vs Data Warehouse.
    Las consultas siguen el orden de database/source/02_analisis_fuente.sql:
    1 totales de líneas (consulta 4), 2 facturas por año (consulta 2), 3 dimensiones, 4 grupos de producto
    (consultas 6 y 7), y al final calidad: cuarentena, miembros desconocidos, claves y auditoría.
    Se puede ejecutar en SSMS o con sqlcmd -I. Solo lee datos.
*/
SET NOCOUNT ON;
GO

-- Consulta 1: totales de líneas de factura (origen) frente a fact.FactSales
SELECT 'Origen' AS fuente,
       COUNT(*) AS lineas, COUNT(DISTINCT InvoiceLineID) AS lineas_distintas,
       SUM(Quantity) AS unidades, SUM(ExtendedPrice) AS monto_total,
       SUM(TaxAmount) AS impuesto_total, SUM(LineProfit) AS utilidad_total
FROM WideWorldImporters.Sales.InvoiceLines
UNION ALL
SELECT 'DW', COUNT(*), COUNT(DISTINCT InvoiceLineID), SUM(Quantity), SUM(ExtendedPrice),
       SUM(TaxAmount), SUM(LineProfit)
FROM WWI_DW.fact.FactSales;
GO

-- Consulta 1b: diferencia (debe ser 0 cuando no hay registros en cuarentena)
SELECT o.lineas - d.lineas AS dif_lineas,
       o.unidades - d.unidades AS dif_unidades,
       o.monto_total - d.monto_total AS dif_monto,
       CASE WHEN o.lineas = d.lineas AND o.unidades = d.unidades AND o.monto_total = d.monto_total
            THEN 'OK' ELSE 'REVISAR' END AS resultado
FROM (SELECT COUNT(*) AS lineas, SUM(Quantity) AS unidades, SUM(ExtendedPrice) AS monto_total
      FROM WideWorldImporters.Sales.InvoiceLines) AS o
CROSS JOIN (SELECT COUNT(*) AS lineas, SUM(Quantity) AS unidades, SUM(ExtendedPrice) AS monto_total
            FROM WWI_DW.fact.FactSales) AS d;
GO

-- Consulta 2: líneas y monto por año (origen por fecha de factura) frente al DW por partición
SELECT YEAR(i.InvoiceDate) AS anio, 'Origen' AS fuente,
       COUNT(*) AS lineas, SUM(l.ExtendedPrice) AS monto_total
FROM WideWorldImporters.Sales.InvoiceLines AS l
JOIN WideWorldImporters.Sales.Invoices AS i ON i.InvoiceID = l.InvoiceID
GROUP BY YEAR(i.InvoiceDate)
UNION ALL
SELECT d.[Year], 'DW', COUNT(*), SUM(f.ExtendedPrice)
FROM WWI_DW.fact.FactSales AS f
JOIN WWI_DW.dim.DimDate AS d ON d.DateKey = f.DateKey
GROUP BY d.[Year]
ORDER BY anio, fuente;
GO

-- Consulta 2b: facturas distintas
SELECT 'Origen' AS fuente, COUNT(*) AS facturas FROM WideWorldImporters.Sales.Invoices
UNION ALL
SELECT 'DW', COUNT(DISTINCT l.InvoiceID)
FROM WWI_DW.fact.FactSales AS f
JOIN WWI_Staging.ready.SalesLine AS l ON l.InvoiceLineID = f.InvoiceLineID;
GO

-- Consulta 3: conteo de filas por dimensión (sin el miembro desconocido, clave 0)
SELECT 'DimCustomer (clientes distintos)' AS dimension,
       (SELECT COUNT(*) FROM WideWorldImporters.Sales.Customers) AS origen,
       (SELECT COUNT(DISTINCT CustomerID) FROM WWI_DW.dim.DimCustomer WHERE CustomerKey <> 0) AS dw
UNION ALL
SELECT 'DimCustomer (versiones vigentes)',
       (SELECT COUNT(*) FROM WideWorldImporters.Sales.Customers),
       (SELECT COUNT(*) FROM WWI_DW.dim.DimCustomer WHERE IsCurrent = 1 AND CustomerKey <> 0)
UNION ALL
SELECT 'DimProduct',
       (SELECT COUNT(*) FROM WideWorldImporters.Warehouse.StockItems),
       (SELECT COUNT(*) FROM WWI_DW.dim.DimProduct WHERE ProductKey <> 0)
UNION ALL
SELECT 'DimEmployee',
       (SELECT COUNT(*) FROM WideWorldImporters.Application.People WHERE IsEmployee = 1),
       (SELECT COUNT(*) FROM WWI_DW.dim.DimEmployee WHERE EmployeeKey <> 0)
UNION ALL
SELECT 'DimGeography',
       (SELECT COUNT(*) FROM WideWorldImporters.Application.Cities),
       (SELECT COUNT(*) FROM WWI_DW.dim.DimGeography WHERE GeographyKey <> 0)
UNION ALL
SELECT 'DimDate (2013-2016)', 1461,
       (SELECT COUNT(*) FROM WWI_DW.dim.DimDate WHERE DateKey <> 0);
GO

-- Consulta 4: productos con más de un grupo y grupo principal asignado (D-25, D-26)
SELECT 'Origen: productos con más de un grupo' AS indicador, COUNT(*) AS valor
FROM (SELECT StockItemID FROM WideWorldImporters.Warehouse.StockItemStockGroups
      GROUP BY StockItemID HAVING COUNT(*) > 1) AS m
UNION ALL
SELECT 'DW: productos sin grupo principal', COUNT(*)
FROM WWI_DW.dim.DimProduct WHERE ProductKey <> 0 AND PrimaryStockGroup = N'Desconocido'
UNION ALL
SELECT 'DW: productos con grupo distinto al de menor StockGroupID', COUNT(*)
FROM WWI_DW.dim.DimProduct AS p
JOIN (SELECT sisg.StockItemID, sg.StockGroupName
      FROM WideWorldImporters.Warehouse.StockItemStockGroups AS sisg
      JOIN WideWorldImporters.Warehouse.StockGroups AS sg ON sg.StockGroupID = sisg.StockGroupID
      WHERE sisg.StockGroupID = (SELECT MIN(x.StockGroupID)
                                 FROM WideWorldImporters.Warehouse.StockItemStockGroups AS x
                                 WHERE x.StockItemID = sisg.StockItemID)) AS esperado
     ON esperado.StockItemID = p.StockItemID
WHERE p.PrimaryStockGroup <> esperado.StockGroupName COLLATE DATABASE_DEFAULT;
GO

-- Consulta 5: registros en cuarentena por fuente y regla (explican diferencias de la consulta 1b)
SELECT SourceName, RuleID, COUNT(*) AS registros
FROM WWI_Staging.stg.Quarantine
GROUP BY SourceName, RuleID
ORDER BY SourceName, RuleID;
GO

-- Consulta 6: hechos asignados al miembro desconocido (clave 0, D-19)
SELECT SUM(CASE WHEN CustomerKey = 0 THEN 1 ELSE 0 END) AS sin_cliente,
       SUM(CASE WHEN ProductKey = 0 THEN 1 ELSE 0 END) AS sin_producto,
       SUM(CASE WHEN EmployeeKey = 0 THEN 1 ELSE 0 END) AS sin_empleado,
       SUM(CASE WHEN GeographyKey = 0 THEN 1 ELSE 0 END) AS sin_geografia,
       SUM(CASE WHEN DateKey = 0 THEN 1 ELSE 0 END) AS sin_fecha
FROM WWI_DW.fact.FactSales;
GO

-- Consulta 7: integridad. Duplicados de la clave de negocio y clientes con más de una versión vigente (ambos 0)
SELECT (SELECT COUNT(*) FROM (SELECT InvoiceLineID FROM WWI_DW.fact.FactSales
                              GROUP BY InvoiceLineID HAVING COUNT(*) > 1) AS d) AS lineas_duplicadas,
       (SELECT COUNT(*) FROM (SELECT CustomerID FROM WWI_DW.dim.DimCustomer
                              WHERE IsCurrent = 1 GROUP BY CustomerID HAVING COUNT(*) > 1) AS v) AS clientes_con_varias_vigentes;
GO

-- Consulta 8: la clave de cliente de cada venta corresponde a la versión vigente en la fecha de la factura (debe ser 0)
SELECT COUNT(*) AS ventas_con_version_incorrecta
FROM WWI_DW.fact.FactSales AS f
JOIN WWI_DW.dim.DimCustomer AS c ON c.CustomerKey = f.CustomerKey
JOIN WWI_DW.dim.DimDate AS d ON d.DateKey = f.DateKey
WHERE f.CustomerKey <> 0
  AND NOT (CAST(d.[Date] AS datetime2) >= c.ValidFrom AND CAST(d.[Date] AS datetime2) < c.ValidTo);
GO

-- Consulta 9: auditoría de la última corrida
SELECT e.ExecutionID, e.Status, e.StartTime, e.EndTime,
       s.StepName, s.Status AS StepStatus, s.RowsRead, s.RowsInserted, s.RowsUpdated, s.RowsRejected
FROM WWI_Staging.audit.Execution AS e
JOIN WWI_Staging.audit.Step AS s ON s.ExecutionID = e.ExecutionID
WHERE e.ExecutionID = (SELECT MAX(ExecutionID) FROM WWI_Staging.audit.Execution)
ORDER BY s.StepID;
GO

-- Consulta 10: marcas de carga confirmadas
SELECT TableName, LastWatermark, UpdatedAt FROM WWI_Staging.ctl.Watermark ORDER BY TableName;
GO
