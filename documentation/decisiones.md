# Registro de decisiones técnicas

Este documento recoge cada decisión de diseño, la alternativa que se descartó y el motivo. Se actualiza en cada paso del proyecto.

## D-01. Base de datos de origen

**Decisión:** WideWorldImporters, versión OLTP (`WideWorldImporters-Full.bak`).

**Motivo:** el modelo de ventas que pide la guía (FactSales, DimDate, DimCustomer, DimProduct, DimEmployee, DimGeography) se puede derivar de sus tablas transaccionales. La versión DW ya viene dimensional, así que quitaría el trabajo de modelado que se evalúa.

**Alternativas descartadas:** WideWorldImportersDW (ya es dimensional), Pagila (PostgreSQL) y Chinook (demasiado pequeña para un proceso completo).

**Verificado:** las ventas van del 1 de enero de 2013 al 31 de mayo de 2016 (2016 es un año parcial). Las tablas transaccionales tienen `LastEditedWhen` para la carga incremental, y las dimensiones tienen `ValidFrom` y `ValidTo`.

## D-02. Motor del Data Warehouse y del staging

**Decisión:** SQL Server 2022 en la instancia local `.\SQLTANIA`, sin contenedor (ver D-15). Staging y DW en bases separadas de la misma instancia: `WWI_Staging` y `WWI_DW`.

**Motivo:** la guía pide diseñar el modelo dimensional en SQL Server. Usar el mismo motor para origen, staging y DW evita problemas de tipos de datos entre motores y reduce la configuración.

## D-03. Herramienta ETL

**Decisión:** Python (pandas, SQLAlchemy, pyodbc) para extracción y reglas de calidad, y T-SQL para las cargas (`MERGE`).

**Motivo:** la guía recomienda Python más SQL para proyectos pequeños. El código queda versionado en Git, se prueba con pytest y se ejecuta igual en cualquier equipo.

**Alternativas descartadas:** Apache Hop (sus pipelines son archivos XML difíciles de revisar en Git), SSIS (solo Windows y requiere Visual Studio) y dbt (el adaptador de SQL Server añade complejidad que no se justifica en este alcance).

## D-04. Orquestación

**Decisión:** runner de Python por etapas (extracción, staging, calidad, DW, ML, alertas), programado con el Programador de tareas de Windows. El runner registra cada etapa en la auditoría (D-22) y aplica la política de fallas de D-20.

**Motivo:** la guía indica que Airflow se justifica solo con dependencias y programación complejas. Aquí el flujo es lineal, así que un runner simple cumple el requisito de orquestación y es más fácil de explicar.

**Alternativa descartada:** Apache Airflow. Queda como trabajo futuro.

## D-05. Dashboard y API

**Decisión:** FastAPI como capa de servicios y React con Vite, TypeScript y Apache ECharts como frontend. El diseño es responsivo, para escritorio y móvil.

**Motivo:** la guía exige que el navegador no se conecte directamente a SQL Server. FastAPI usa Python, el mismo lenguaje del ETL y del modelo predictivo. React es más ligero de montar que Angular para este alcance.

**Seguridad:** la API usa un usuario de solo lectura sobre `WWI_DW`. Para la demo, el acceso al dashboard requiere un usuario de demo con token de sesión. Las credenciales van en variables de entorno, nunca en el repositorio.

**Funcionalidades:** panel principal con cuatro a seis KPIs, filtros por fecha y al menos dos dimensiones, tendencias por periodo, tabla de detalle con paginación, navegación de resumen a detalle, fecha y hora de la última actualización, y estados de carga, error y sin datos.

**Definición de KPIs:** cada KPI tiene nombre, propósito, fórmula, unidad, granularidad, filtros, fuente y responsable, y se valida contra una consulta SQL independiente.

## D-06. Modelo predictivo

**Decisión:** pronóstico semanal de ventas. Baseline estacional ingenuo y un modelo de regresión con variables de rezago calculadas solo con datos pasados. Evaluación con MAE, RMSE y sMAPE sobre un periodo final separado, y división temporal sin mezclar fechas.

**Registro y publicación:** cada entrenamiento guarda en `ml.ModelRegistry` la versión, la fecha, los parámetros, las métricas y el rango de datos usado. Las predicciones se guardan en `ml.Forecast` con el identificador de la versión del modelo y el horizonte. La API expone las predicciones y el dashboard las muestra marcadas como predicción, no como dato histórico.

**Motivo:** la guía pide una división temporal, prohíbe el data leakage y exige guardar modelo, parámetros, versión y métricas. Con historial de ventas, el pronóstico es el problema más directo de formular.

**Limitaciones que se documentan:** pocas semanas de historial por categoría, y el modelo no considera promociones ni cambios de catálogo.

## D-07. Asistente de IA generativa

**Decisión:** modelo abierto servido por la API de Groq, que es compatible con el SDK de OpenAI. La guía lista OpenAI API como alternativa recomendada; Groq es una alternativa equivalente que permite cumplir lo obligatorio con capa gratuita. El modelo no ejecuta SQL. Solo elige entre 6 consultas aprobadas y sus parámetros; el backend valida y ejecuta la consulta, y el modelo redacta la explicación con esos resultados.

**Datos enviados al servicio externo:** solo los resultados agregados de las 6 consultas aprobadas (totales, categorías, regiones y periodos). No se envían nombres de clientes, personas ni datos de contacto. Esto se documenta en el documento de GenAI, como pide la guía.

**Controles:** validación de la pregunta, límite de longitud, límite de solicitudes por minuto, y respuesta con la fecha de actualización de los datos y el periodo que la sustenta. Si no hay datos suficientes, el asistente lo dice y no inventa cifras. Si se agota la capa gratuita, se cambia a Ollama local sin modificar la arquitectura.

**Pruebas:** 10 preguntas de prueba con resultado esperado y consulta de respaldo, y al menos dos casos donde el sistema debe reconocer que no tiene información suficiente.

**Motivo:** cumple la regla de la guía de no dar acceso irrestricto a SQL, sin depender de tener la RAM suficiente para un modelo local.

**Alternativas descartadas:** Ollama local como principal (con 8 GB de RAM no cabe junto con SQL Server) y Gemini como principal (sus cuotas gratuitas se redujeron en 2026; queda como respaldo).

## D-08. Alertas

**Decisión:** la notificación principal es el panel del dashboard, que la guía lista como canal. El correo por SMTP se envía a Mailpit en su versión ejecutable para Windows, que no requiere Docker. Mailpit captura los mensajes en local y muestra la evidencia de entrega.

**Disparadores:** dos reglas de negocio (por ejemplo, ventas de la semana más de 15% por debajo de la referencia) y una de predicción (pronóstico por debajo de un umbral). Un disparador de IA generativa queda como extensión opcional.

**Contenido de cada alerta:** identificador, fecha y hora del evento, tipo y severidad, indicador o entidad afectada, valor observado y umbral o predicción, periodo de referencia, origen (regla o modelo), acción recomendada y estado (nueva, atendida, descartada o resuelta).

**Frecuencia:** el evaluador corre después de cada carga incremental. No se promete tiempo real: el ETL es por lote, y el evento de la demo se identifica como simulado.

**Evitar duplicados:** cada alerta tiene una clave formada por regla, entidad y periodo, así que el mismo evento no se notifica dos veces.

**Pruebas:** condición verdadera y falsa, duplicados, reintentos y fallas de envío, registro de generación y de entrega, y consulta del detalle y del estado.

**Motivo:** cumple el requisito de notificación de principio a fin sin enviar correos reales durante la demo, y sin Docker (D-15).

**Alternativas descartadas:** WebSockets, que queda como trabajo futuro, y un servicio de correo en la nube, que añade credenciales externas sin aportar a lo que evalúa la guía.

## D-09. Contenedores

**Decisión:** Docker Compose con SQL Server, API, frontend y Mailpit.

**Motivo:** la guía pide reproducibilidad. Un único comando levanta todo el entorno.

**Estado:** superada por D-15. Se conserva el registro por trazabilidad.

## D-10. Alcance para la entrega

**Decisión:** un solo proceso (ventas), una tabla de hechos a nivel de línea de factura y cinco dimensiones (DimDate, DimCustomer, DimProduct, DimEmployee, DimGeography). SCD Tipo 2 solo en cliente. Tres zonas de staging, según el flujo de la guía: raw, limpio y validado, y preparado. Tres alertas (D-08).

**Motivo:** el plazo de entrega es el domingo y el trabajo es individual. La guía recomienda limitar el alcance a un proceso principal, y se conservan todos los componentes que la rúbrica evalúa en versión mínima. Lo que queda fuera se documenta como trabajo futuro.
## D-11. Instancia de SQL Server para desarrollo

**Decisión:** usar la instancia local `.\SQLTANIA` (SQL Server 2022, autenticación de Windows) para todo el desarrollo. No se usa contenedor (ver D-15).

**Motivo:** la instancia por defecto de la computadora ya ocupa el puerto 1433, lo que impedía levantar el contenedor sin cambiar la configuración. Además, Docker Desktop tenía asignados 3.7 GB de memoria en una computadora de 8 GB, lo que hacía poco práctico trabajar con ambos al mismo tiempo. La instancia local evita esos conflictos y se puede revisar con SQL Server Management Studio.

**Alternativas descartadas:** SQL Server en Docker como entorno principal, por los motivos anteriores. La reproducibilidad se garantiza con el README y el script `deployment/run_all.ps1` (D-15 y D-24).

## D-12. Datos que no se cargan al DW

**Decisión:** `HashedPassword` (de `Application.People`) y `Photo` (de `Application.People` y `Warehouse.StockItems`) se excluyen desde la extracción. Por eso tampoco aparecen en ninguna zona de staging.

**Motivo:** la guía pide no publicar contraseñas ni datos sensibles, y usar datos anonimizados cuando sea posible. Una contraseña en hash no aporta al análisis, y la fotografía no se usa en ninguna métrica. Excluirlas desde el inicio evita tener que protegerlas en staging.

**Nota:** la guía pide conservar lo recibido en la zona raw. Esta excepción se documenta aquí, con su motivo.

## D-13. Ruta de reparto en la factura

**Decisión:** `Sales.Invoices.DeliveryRun` se conserva en el DW aunque dependa de `CustomerID` a través de `Sales.Customers`.

**Motivo:** la prueba mostró cero facturas con ruta distinta a la de su cliente. Conservar la columna en la factura registra la ruta vigente en el momento de la venta, aunque el cliente cambie de ruta después. Se documenta como dependencia transitiva del origen, y en el DW se mantiene a propósito.

## D-14. Precisión de los tipos decimales

**Decisión:** los montos monetarios se guardan como `decimal(18,2)` y las tasas, porcentajes y pesos como `decimal(18,3)`, para conservar la precisión del origen en el DW.

**Motivo:** el origen usa esas escalas en las 11 columnas decimales del análisis. Mantenerlas evita redondeos distintos entre el origen y el DW.

## D-15. Entorno local sin Docker

**Decisión:** el proyecto corre en la instancia local de SQL Server 2022, `.\SQLTANIA`. No se usa contenedor para la base de datos ni para el resto de los servicios. Un script de PowerShell (`deployment/run_all.ps1`) ejecuta en orden el ETL, la validación, el modelo, la carga del DW y las alertas.

**Motivo:** el puerto 1433 ya estaba ocupado por la instancia predeterminada. Docker Desktop reservaba 3.7 GB de los 8 GB de RAM del equipo, y con SQL Server en contenedor y las demás herramientas el consumo era alto. El docente aceptó el despliegue local. La guía lista Docker Compose como opción recomendada, no obligatoria, y pide que el proyecto se pueda reproducir con el README. El script y el README cumplen ese requisito.

**Alternativa descartada:** contenedor en el puerto 1434. Funcionaba, pero sumaba consumo de RAM y una capa más que explicar en la demo.

## D-16. Carga incremental con marca de tiempo

**Decisión:** cada tabla de origen tiene una marca de carga (watermark) en la tabla de control `ctl.Watermark` dentro de `WWI_Staging`. Las tablas de hechos usan `LastEditedWhen` y las dimensiones usan `ValidFrom`. En cada corrida se leen los cambios posteriores a la marca con una ventana de solapamiento de tres días, y el watermark se actualiza solo cuando la carga termina bien.

**Eliminaciones:** el origen no elimina facturas ni líneas en el alcance, así que no se implementa detección de eliminaciones. Se documenta como supuesto y se revisa si el origen cambia.

**Idempotencia:** la carga usa `MERGE` por clave de negocio, así que volver a ejecutar el mismo lote no duplica resultados.

**Motivo:** evita recargar las 70,510 facturas en cada corrida, permite reprocesar un periodo y cumple lo que pide la guía: watermark persistido, ventana de solapamiento para registros tardíos y reejecución segura.

**Alternativa descartada:** recarga completa en cada corrida. Es más simple, pero no es carga incremental y no escala con el crecimiento de las ventas.

## D-17. Particionado de la tabla de hechos por año

**Decisión:** `FactSales` se particiona por año en cuatro particiones (2013 a 2016), con `RANGE RIGHT` sobre `DateKey` en formato `yyyymmdd`.

**Motivo:** las consultas y las recargas suelen trabajar por año, y el particionado permite cargar o reemplazar un año sin tocar el resto. Con unas 228 mil líneas de factura el volumen no lo exige, así que es una decisión de diseño y no de rendimiento. La guía no lo pide, pero tampoco lo prohíbe.

**Alternativa descartada:** tabla sin particionar. Es válida para este volumen, pero no muestra el diseño que pide la rúbrica.

## D-18. Reglas de calidad y cuarentena

**Decisión:** las reglas de calidad viven en código Python, con pruebas en pytest. Cada regla tiene un identificador, una descripción y un criterio. Los registros que fallan una regla no se borran: pasan a la tabla `stg.Quarantine` con la fuente, la fecha, la ejecución, la regla fallida y el detalle.

**Transformaciones que se aplican:** perfilado de columnas, limpieza de espacios y formatos, clasificación de nulos (D-19), duplicados con clave de duplicidad y regla de supervivencia (la versión con `LastEditedWhen` más reciente), conversión explícita de tipos sin perder precisión, integridad referencial, detección de valores atípicos por reglas de negocio (por ejemplo, cantidades negativas en facturas que no son notas de crédito), y atributos derivados como año, mes y trimestre.

**Motivo:** la guía exige reglas reproducibles, cuarentena con trazabilidad y no borrar datos sin justificación. Un proceso exitoso no implica datos correctos, así que cada regla queda registrada.

## D-19. Manejo de nulos y miembro desconocido

**Decisión:** los nulos se conservan en atributos opcionales, como marca o tamaño de producto. En las dimensiones, los atributos de texto vacíos se muestran como "Desconocido". Las medidas numéricas nunca se reemplazan por cero. Los hechos que no encuentran su dimensión se asignan a un miembro desconocido, con clave `0` en la dimensión correspondiente.

**Motivo:** la guía advierte que reemplazar nulos por cero distorsiona los resultados, y que cero puede tener un significado real. Un miembro desconocido permite contar esos hechos sin perderlos y sin mezclarlos con datos válidos.

**Imputaciones:** no hay imputaciones en medidas. Si una imputación es necesaria más adelante, se documentará con método, justificación, campo afectado e impacto.

## D-20. Fallas, reintentos y registros tardíos

**Decisión:** cada etapa corre en su propia transacción. Si una etapa falla, se revierte, el watermark no se mueve y el estado queda como `failed` en la auditoría. El runner reintenta una vez después de un minuto. Si el segundo intento falla, el proceso se detiene y se registra el error. Los registros tardíos se capturan con la ventana de solapamiento de D-16.

**Motivo:** responde directamente a las preguntas de la guía sobre fallas y reintentos. La combinación de transacción, watermark y `MERGE` permite reejecutar sin inconsistencias.

## D-21. Actualización de hechos y dimensiones

**Decisión:** las tablas de hechos se actualizan con `MERGE` por clave de negocio, así que un cambio en una línea de factura reemplaza la fila anterior. El cliente usa SCD Tipo 2: al cambiar un atributo se cierra la versión anterior con `ValidTo` y se inserta una versión nueva con `IsCurrent = 1`. Producto, empleado y geografía usan SCD Tipo 1, porque no requieren historial en el alcance. `DimDate` se genera una vez y no cambia.

**Motivo:** la guía pide definir si los cambios históricos se preservan, y justificar cada estrategia. El cliente es la dimensión donde el historial aporta al análisis (por ejemplo, cambios de categoría o de ruta de reparto).

## D-22. Auditoría y monitoreo

**Decisión:** dos tablas de auditoría en `WWI_Staging`: `audit.Execution` (una fila por corrida) y `audit.Step` (una fila por etapa). Guardan `execution_id`, `pipeline_name`, `start_time`, `end_time`, `source_object`, `target_object`, `rows_read`, `rows_inserted`, `rows_updated`, `rows_rejected`, `status`, `error_detail`, `watermark_start` y `watermark_end`. El dashboard incluye una vista operativa con el estado de las ejecuciones, la hora de la última carga exitosa, los conteos, las fallas recientes y la versión del modelo.

**Motivo:** la guía pide esa auditoría mínima y un reporte operativo. Los mismos datos sirven para la rúbrica de calidad: completitud, unicidad, validez, consistencia, integridad y oportunidad.

## D-23. Frecuencia de actualización y tiempo real

**Decisión:** el ETL es por lote. En la demo se ejecuta bajo demanda, y en operación queda programado una vez al día con el Programador de tareas. El dashboard refresca sus datos cada 60 segundos y muestra la última actualización. No se promete tiempo real. El evento de la demo (una venta que dispara una alerta) se genera con un worker de simulación y se identifica como simulado.

**Motivo:** la guía advierte que un ETL nocturno no produce alertas en tiempo real, y pide definir una frecuencia medible. Confundir un lote frecuente con tiempo real es uno de los errores que señala la guía.

## D-24. Estructura del repositorio

**Decisión:** el repositorio sigue la estructura sugerida por la guía: `documentation/`, `database/` (con `source/`, `staging/`, `warehouse/` y `scripts/`), `etl/`, `backend/`, `frontend/`, `machine-learning/`, `generative-ai/`, `notifications/`, `tests/` y `deployment/` (con `run_all.ps1`).

**Motivo:** la rúbrica evalúa el proyecto completo, y una estructura conocida facilita la revisión. Los notebooks, si se usan, sirven para exploración; la lógica va en módulos o scripts reutilizables.

## D-25. Grupo principal de producto

**Decisión:** un producto puede pertenecer a varios grupos (`Warehouse.StockItemStockGroups`). En `dim.DimProduct`, el grupo principal (`PrimaryStockGroup`) es el de menor `StockGroupID` de cada producto.

**Motivo:** la dimensión tiene una fila por producto, así que cada producto debe tener un solo grupo. La regla es determinista y reproducible, y evita duplicar las ventas al unir con la dimensión. Las ventas por los demás grupos no se pueden analizar con este atributo; se documenta como limitación.

**Alternativa descartada:** una fila de producto por grupo, que multiplicaría las líneas de factura al sumar ventas.

**Nota de diseño relacionada (D-17):** la llave primaria de `fact.FactSales` es `(DateKey, InvoiceLineID)`, porque SQL Server exige que la columna de partición esté en el índice único agrupado. El `MERGE` usa `InvoiceLineID` como clave de negocio.

## D-26. Categoría principal del producto

**Decisión:** cada producto tiene una sola categoría principal en `DimProduct`: el grupo con menor `StockGroupID`. Los 133 productos con varios grupos conservan solo ese en la dimensión.

**Motivo:** un producto con varios grupos duplicaría sus hechos al unirlo con la dimensión, y la guía advierte sobre los joins uno a muchos que multiplican medidas. Usar el grupo con menor ID es una regla reproducible.

**Alternativa descartada:** puente producto-grupo (muchos a muchos). Es más fiel al origen, pero complica las métricas por categoría. Queda como trabajo futuro.

## D-27. Ancho de la columna DeliveryRun en la dimensión

**Decisión:** `DimCustomer.DeliveryRun` se define como `nvarchar(20)`, no con la longitud de origen de 5 caracteres, para que quepa el valor "Desconocido" del miembro 0 (D-19).

**Motivo:** el miembro desconocido necesita texto. Ampliar la columna en el DW no altera los datos del origen.

## D-28. Nombres de precio e impuesto en DimProduct

**Decisión:** en `dim.DimProduct` las columnas `UnitPrice` y `TaxRate` se renombran a `CatalogUnitPrice` y `CatalogTaxRate`.

**Motivo:** distinguir el catálogo actual del producto de los precios y tasas de cada venta, que viven en `fact.FactSales` (`UnitPrice`, `TaxRate`). Como `DimProduct` es SCD tipo 1, solo guarda el valor vigente del catálogo y no debe confundirse con el precio al que se vendió.
