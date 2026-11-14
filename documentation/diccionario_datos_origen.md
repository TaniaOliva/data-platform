# Diccionario de datos del origen: WideWorldImporters

Base de datos origen: `WideWorldImporters` (SQL Server 2022, instancia `.\SQLTANIA`).
Alcance: 11 tablas usadas en el análisis del paso 2. Total: 162 columnas.

**Convenciones**

- **Longitud:** en caracteres para `nvarchar`. La vista `sys.columns` reporta bytes (2 por carácter), así que se dividió entre 2. `máx` significa `nvarchar(max)` o `varbinary(max)`. Un guion (—) indica que el tipo no tiene longitud.
- **Permite nulos:** Sí o No, según la columna `is_nullable`.
- **Llaves:** la llave primaria es la primera columna de cada tabla con sufijo `ID`. Las llaves foráneas se indican con "FK a".
- **Tablas temporales:** `ValidFrom` y `ValidTo` marcan el periodo de vigencia de cada fila. El historial vive en tablas `*_Archive`, que no se incluyen aquí.
- **Carga incremental:** `LastEditedWhen` se usa como marca de cambio en las tablas de hechos.

---

## Application.Cities

Ciudades. Llave primaria: `CityID`.

| Columna | Tipo | Longitud | Permite nulos | Descripción |
|---|---|---|---|---|
| CityID | int | — | No | Identificador de la ciudad (llave primaria). |
| CityName | nvarchar | 50 | No | Nombre de la ciudad. |
| StateProvinceID | int | — | No | Estado o provincia donde está la ciudad (FK a Application.StateProvinces). |
| Location | geography | máx | Sí | Punto geográfico de la ciudad. |
| LatestRecordedPopulation | bigint | — | Sí | Población más reciente registrada. |
| LastEditedBy | int | — | No | Persona que hizo la última edición (FK a Application.People). |
| ValidFrom | datetime2 | — | No | Inicio de vigencia de la fila (tabla temporal). |
| ValidTo | datetime2 | — | No | Fin de vigencia de la fila (tabla temporal). |

## Application.Countries

Países y territorios. Llave primaria: `CountryID`.

| Columna | Tipo | Longitud | Permite nulos | Descripción |
|---|---|---|---|---|
| CountryID | int | — | No | Identificador del país (llave primaria). |
| CountryName | nvarchar | 60 | No | Nombre común del país. |
| FormalName | nvarchar | 60 | No | Nombre formal oficial. |
| IsoAlpha3Code | nvarchar | 3 | Sí | Código ISO 3166-1 alfa-3. |
| IsoNumericCode | int | — | Sí | Código ISO 3166-1 numérico. |
| CountryType | nvarchar | 20 | Sí | Tipo de entidad territorial. |
| LatestRecordedPopulation | bigint | — | Sí | Población más reciente registrada. |
| Continent | nvarchar | 30 | No | Continente. |
| Region | nvarchar | 30 | No | Región geográfica. |
| Subregion | nvarchar | 30 | No | Subregión geográfica. |
| Border | geography | máx | Sí | Contorno geográfico del país. |
| LastEditedBy | int | — | No | Persona que hizo la última edición (FK a Application.People). |
| ValidFrom | datetime2 | — | No | Inicio de vigencia de la fila (tabla temporal). |
| ValidTo | datetime2 | — | No | Fin de vigencia de la fila (tabla temporal). |

## Application.People

Personas: empleados, vendedores, contactos de clientes y usuarios del sistema. Llave primaria: `PersonID`.

| Columna | Tipo | Longitud | Permite nulos | Descripción |
|---|---|---|---|---|
| PersonID | int | — | No | Identificador de la persona (llave primaria). |
| FullName | nvarchar | 50 | No | Nombre completo. |
| PreferredName | nvarchar | 50 | No | Nombre preferido. |
| SearchName | nvarchar | 101 | No | Nombre normalizado para búsquedas. |
| IsPermittedToLogon | bit | — | No | Indica si la persona puede iniciar sesión. |
| LogonName | nvarchar | 50 | Sí | Nombre de inicio de sesión. |
| IsExternalLogonProvider | bit | — | No | Indica si el inicio de sesión lo valida un proveedor externo. |
| HashedPassword | varbinary | máx | Sí | Contraseña en hash. Dato sensible: no se carga al DW. |
| IsSystemUser | bit | — | No | Indica si es usuario del sistema. |
| IsEmployee | bit | — | No | Indica si la persona es empleado. |
| IsSalesperson | bit | — | No | Indica si la persona es vendedor. |
| UserPreferences | nvarchar | máx | Sí | Preferencias de usuario, en texto. |
| PhoneNumber | nvarchar | 20 | Sí | Teléfono. |
| FaxNumber | nvarchar | 20 | Sí | Fax. |
| EmailAddress | nvarchar | 256 | Sí | Correo electrónico. |
| Photo | varbinary | máx | Sí | Fotografía. No se carga al DW. |
| CustomFields | nvarchar | máx | Sí | Campos personalizados en formato JSON. |
| OtherLanguages | nvarchar | máx | Sí | Otros idiomas que habla la persona. |
| LastEditedBy | int | — | No | Persona que hizo la última edición (FK a Application.People). |
| ValidFrom | datetime2 | — | No | Inicio de vigencia de la fila (tabla temporal). |
| ValidTo | datetime2 | — | No | Fin de vigencia de la fila (tabla temporal). |

## Application.StateProvinces

Estados y provincias. Llave primaria: `StateProvinceID`.

| Columna | Tipo | Longitud | Permite nulos | Descripción |
|---|---|---|---|---|
| StateProvinceID | int | — | No | Identificador del estado o provincia (llave primaria). |
| StateProvinceCode | nvarchar | 5 | No | Código del estado o provincia. |
| StateProvinceName | nvarchar | 50 | No | Nombre del estado o provincia. |
| CountryID | int | — | No | País al que pertenece (FK a Application.Countries). |
| SalesTerritory | nvarchar | 50 | No | Territorio de ventas asignado. |
| Border | geography | máx | Sí | Contorno geográfico. |
| LatestRecordedPopulation | bigint | — | Sí | Población más reciente registrada. |
| LastEditedBy | int | — | No | Persona que hizo la última edición (FK a Application.People). |
| ValidFrom | datetime2 | — | No | Inicio de vigencia de la fila (tabla temporal). |
| ValidTo | datetime2 | — | No | Fin de vigencia de la fila (tabla temporal). |

## Sales.CustomerCategories

Categorías de cliente. Llave primaria: `CustomerCategoryID`.

| Columna | Tipo | Longitud | Permite nulos | Descripción |
|---|---|---|---|---|
| CustomerCategoryID | int | — | No | Identificador de la categoría (llave primaria). |
| CustomerCategoryName | nvarchar | 50 | No | Nombre de la categoría. |
| LastEditedBy | int | — | No | Persona que hizo la última edición (FK a Application.People). |
| ValidFrom | datetime2 | — | No | Inicio de vigencia de la fila (tabla temporal). |
| ValidTo | datetime2 | — | No | Fin de vigencia de la fila (tabla temporal). |

## Sales.Customers

Clientes. Llave primaria: `CustomerID`. Tabla temporal con SCD tipo 2 en el análisis.

| Columna | Tipo | Longitud | Permite nulos | Descripción |
|---|---|---|---|---|
| CustomerID | int | — | No | Identificador del cliente (llave primaria). |
| CustomerName | nvarchar | 100 | No | Nombre del cliente. |
| BillToCustomerID | int | — | No | Cliente al que se factura (FK a Sales.Customers). |
| CustomerCategoryID | int | — | No | Categoría del cliente (FK a Sales.CustomerCategories). |
| BuyingGroupID | int | — | Sí | Grupo de compra al que pertenece. Tabla no incluida en el análisis. |
| PrimaryContactPersonID | int | — | No | Contacto principal (FK a Application.People). |
| AlternateContactPersonID | int | — | Sí | Contacto alterno (FK a Application.People). |
| DeliveryMethodID | int | — | No | Método de entrega. Tabla no incluida en el análisis. |
| DeliveryCityID | int | — | No | Ciudad de entrega (FK a Application.Cities). |
| PostalCityID | int | — | No | Ciudad del domicilio postal (FK a Application.Cities). |
| CreditLimit | decimal | — | Sí | Límite de crédito. |
| AccountOpenedDate | date | — | No | Fecha de apertura de la cuenta. |
| StandardDiscountPercentage | decimal | — | No | Porcentaje de descuento estándar. |
| IsStatementSent | bit | — | No | Indica si se envía estado de cuenta. |
| IsOnCreditHold | bit | — | No | Indica si la cuenta está en retención de crédito. |
| PaymentDays | int | — | No | Días de plazo para pagar. |
| PhoneNumber | nvarchar | 20 | No | Teléfono. |
| FaxNumber | nvarchar | 20 | No | Fax. |
| DeliveryRun | nvarchar | 5 | Sí | Ruta de reparto asignada al cliente. |
| RunPosition | nvarchar | 5 | Sí | Posición del cliente dentro de la ruta. |
| WebsiteURL | nvarchar | 256 | No | Sitio web del cliente. |
| DeliveryAddressLine1 | nvarchar | 60 | No | Línea 1 de la dirección de entrega. |
| DeliveryAddressLine2 | nvarchar | 60 | Sí | Línea 2 de la dirección de entrega. |
| DeliveryPostalCode | nvarchar | 10 | No | Código postal de entrega. |
| DeliveryLocation | geography | máx | Sí | Punto geográfico de entrega. |
| PostalAddressLine1 | nvarchar | 60 | No | Línea 1 de la dirección postal. |
| PostalAddressLine2 | nvarchar | 60 | Sí | Línea 2 de la dirección postal. |
| PostalPostalCode | nvarchar | 10 | No | Código postal del domicilio postal. |
| LastEditedBy | int | — | No | Persona que hizo la última edición (FK a Application.People). |
| ValidFrom | datetime2 | — | No | Inicio de vigencia de la fila (tabla temporal). |
| ValidTo | datetime2 | — | No | Fin de vigencia de la fila (tabla temporal). |

## Sales.InvoiceLines

Líneas de factura. Llave primaria: `InvoiceLineID`. Tabla de hechos.

| Columna | Tipo | Longitud | Permite nulos | Descripción |
|---|---|---|---|---|
| InvoiceLineID | int | — | No | Identificador de la línea (llave primaria). |
| InvoiceID | int | — | No | Factura a la que pertenece (FK a Sales.Invoices). |
| StockItemID | int | — | No | Producto facturado (FK a Warehouse.StockItems). |
| Description | nvarchar | 100 | No | Descripción del producto en la línea, copiada al facturar. Es historial. |
| PackageTypeID | int | — | No | Tipo de empaque. Tabla no incluida en el análisis. |
| Quantity | int | — | No | Unidades facturadas. |
| UnitPrice | decimal | — | Sí | Precio unitario. |
| TaxRate | decimal | — | No | Tasa de impuesto aplicada. |
| TaxAmount | decimal | — | No | Monto de impuesto de la línea. |
| LineProfit | decimal | — | No | Utilidad de la línea. |
| ExtendedPrice | decimal | — | No | Monto total de la línea, con impuestos. |
| LastEditedBy | int | — | No | Persona que hizo la última edición (FK a Application.People). |
| LastEditedWhen | datetime2 | — | No | Fecha y hora de la última edición. Marca para la carga incremental. |

## Sales.Invoices

Encabezados de factura. Llave primaria: `InvoiceID`. Tabla de hechos en el DW.

| Columna | Tipo | Longitud | Permite nulos | Descripción |
|---|---|---|---|---|
| InvoiceID | int | — | No | Identificador de la factura (llave primaria). |
| CustomerID | int | — | No | Cliente que recibe la mercancía (FK a Sales.Customers). |
| BillToCustomerID | int | — | No | Cliente al que se factura (FK a Sales.Customers). |
| OrderID | int | — | Sí | Pedido de origen. Tabla no incluida en el análisis. |
| DeliveryMethodID | int | — | No | Método de entrega. Tabla no incluida en el análisis. |
| ContactPersonID | int | — | No | Contacto de la factura (FK a Application.People). |
| AccountsPersonID | int | — | No | Persona de cuentas por cobrar (FK a Application.People). |
| SalespersonPersonID | int | — | No | Vendedor que generó la venta (FK a Application.People). |
| PackedByPersonID | int | — | No | Persona que empacó el pedido (FK a Application.People). |
| InvoiceDate | date | — | No | Fecha de la factura. |
| CustomerPurchaseOrderNumber | nvarchar | 20 | Sí | Número de orden de compra del cliente. |
| IsCreditNote | bit | — | No | Indica si el documento es una nota de crédito. |
| CreditNoteReason | nvarchar | máx | Sí | Motivo de la nota de crédito. |
| Comments | nvarchar | máx | Sí | Comentarios visibles en la factura. |
| DeliveryInstructions | nvarchar | máx | Sí | Instrucciones de entrega. |
| InternalComments | nvarchar | máx | Sí | Comentarios internos. |
| TotalDryItems | int | — | No | Número de artículos de almacén seco. |
| TotalChillerItems | int | — | No | Número de artículos refrigerados. |
| DeliveryRun | nvarchar | 5 | Sí | Ruta de reparto. Coincide con la del cliente en todas las facturas de la prueba. |
| RunPosition | nvarchar | 5 | Sí | Posición dentro de la ruta. |
| ReturnedDeliveryData | nvarchar | máx | Sí | Datos de entrega devueltos por el repartidor, en formato JSON. |
| ConfirmedDeliveryTime | datetime2 | — | Sí | Fecha y hora de entrega confirmada. |
| ConfirmedReceivedBy | nvarchar | 4000 | Sí | Nombre de quien recibió la entrega. |
| LastEditedBy | int | — | No | Persona que hizo la última edición (FK a Application.People). |
| LastEditedWhen | datetime2 | — | No | Fecha y hora de la última edición. Marca para la carga incremental. |

## Warehouse.StockGroups

Grupos de productos. Llave primaria: `StockGroupID`.

| Columna | Tipo | Longitud | Permite nulos | Descripción |
|---|---|---|---|---|
| StockGroupID | int | — | No | Identificador del grupo (llave primaria). |
| StockGroupName | nvarchar | 50 | No | Nombre del grupo. |
| LastEditedBy | int | — | No | Persona que hizo la última edición (FK a Application.People). |
| ValidFrom | datetime2 | — | No | Inicio de vigencia de la fila (tabla temporal). |
| ValidTo | datetime2 | — | No | Fin de vigencia de la fila (tabla temporal). |

## Warehouse.StockItems

Productos. Llave primaria: `StockItemID`. Tabla temporal.

| Columna | Tipo | Longitud | Permite nulos | Descripción |
|---|---|---|---|---|
| StockItemID | int | — | No | Identificador del producto (llave primaria). |
| StockItemName | nvarchar | 100 | No | Nombre del producto. |
| SupplierID | int | — | No | Proveedor. Tabla no incluida en el análisis. |
| ColorID | int | — | Sí | Color. Tabla no incluida en el análisis. |
| UnitPackageID | int | — | No | Tipo de empaque unitario. Tabla no incluida en el análisis. |
| OuterPackageID | int | — | No | Tipo de empaque exterior. Tabla no incluida en el análisis. |
| Brand | nvarchar | 50 | Sí | Marca. |
| Size | nvarchar | 20 | Sí | Tamaño. |
| LeadTimeDays | int | — | No | Días de entrega del proveedor. |
| QuantityPerOuter | int | — | No | Unidades por empaque exterior. |
| IsChillerStock | bit | — | No | Indica si el producto requiere refrigeración. |
| Barcode | nvarchar | 50 | Sí | Código de barras. |
| TaxRate | decimal | — | No | Tasa de impuesto del producto. |
| UnitPrice | decimal | — | No | Precio unitario de venta. |
| RecommendedRetailPrice | decimal | — | Sí | Precio de venta sugerido. |
| TypicalWeightPerUnit | decimal | — | No | Peso típico por unidad. |
| MarketingComments | nvarchar | máx | Sí | Comentarios de mercadotecnia. |
| InternalComments | nvarchar | máx | Sí | Comentarios internos. |
| Photo | varbinary | máx | Sí | Fotografía del producto. No se carga al DW. |
| CustomFields | nvarchar | máx | Sí | Campos personalizados en formato JSON. |
| Tags | nvarchar | máx | Sí | Etiquetas en formato JSON. |
| SearchDetails | nvarchar | máx | No | Texto de búsqueda generado a partir de otros campos. |
| LastEditedBy | int | — | No | Persona que hizo la última edición (FK a Application.People). |
| ValidFrom | datetime2 | — | No | Inicio de vigencia de la fila (tabla temporal). |
| ValidTo | datetime2 | — | No | Fin de vigencia de la fila (tabla temporal). |

## Warehouse.StockItemStockGroups

Relación muchos a muchos entre productos y grupos. Llave primaria: `StockItemStockGroupID`.

| Columna | Tipo | Longitud | Permite nulos | Descripción |
|---|---|---|---|---|
| StockItemStockGroupID | int | — | No | Identificador de la relación (llave primaria). |
| StockItemID | int | — | No | Producto (FK a Warehouse.StockItems). |
| StockGroupID | int | — | No | Grupo (FK a Warehouse.StockGroups). |
| LastEditedBy | int | — | No | Persona que hizo la última edición (FK a Application.People). |
| LastEditedWhen | datetime2 | — | No | Fecha y hora de la última edición. |

---

## Notas para el diseño del DW

- **No se cargan al DW:** `HashedPassword` y `Photo` (de `Application.People` y `Warehouse.StockItems`) por privacidad y porque no aportan al análisis. Esto va como decisión.
- **Columnas JSON:** `CustomFields`, `Tags`, `UserPreferences` y `ReturnedDeliveryData` se guardan tal cual en staging. Solo se extraen campos si una métrica los necesita.
- **Columnas `decimal`:** el CSV no trae precisión ni escala. Hay que obtenerlas antes del DDL del DW.
- **Tablas no incluidas:** `BuyingGroups`, `DeliveryMethods`, `PackageTypes`, `Orders`, `Suppliers` y `Colors` aparecen como FK, pero no están en el análisis.
- **Pruebas de 3FN:** `Sales.Invoices.DeliveryRun` depende de `CustomerID` a través de `Sales.Customers`, no de la factura. Se documenta como dependencia transitiva en el origen; en el DW se conserva a propósito.
- **Region y Continent:** la prueba mostró que `Region` no determina `Continent`, así que no hay dependencia transitiva en `Application.Countries`.
