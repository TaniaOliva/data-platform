# Registro de decisiones técnicas

Este documento recoge cada decisión de diseño, la alternativa que se descartó y el motivo. Se actualiza en cada paso del proyecto.

## D-01. Base de datos de origen

**Decisión:** WideWorldImporters, versión OLTP (`WideWorldImporters-Full.bak`).

**Motivo:** el modelo de ventas que pide la guía (FactSales, DimDate, DimCustomer, DimProduct, DimEmployee, DimGeography) se puede derivar de sus tablas transaccionales. La versión DW ya viene dimensional, así que quitaría el trabajo de modelado que se evalúa.

**Alternativas descartadas:** WideWorldImportersDW (ya es dimensional), Pagila (PostgreSQL) y Chinook (demasiado pequeña para un proceso completo).

**Pendiente de verificar:** rango de fechas del historial de ventas, y si las tablas tienen columnas de última edición para la carga incremental.

## D-02. Motor del Data Warehouse y del staging

**Decisión:** SQL Server 2022 (imagen Developer en Docker). Staging y DW en bases separadas de la misma instancia: `WWI_Staging` y `WWI_DW`.

**Motivo:** el DW debe estar en SQL Server según la guía. Usar el mismo motor para origen, staging y DW evita problemas de tipos de datos entre motores y reduce la configuración.

## D-03. Herramienta ETL

**Decisión:** Python (pandas, SQLAlchemy, pyodbc) para extracción y reglas de calidad, y T-SQL para las cargas (`MERGE`).

**Motivo:** el código queda versionado en Git, se prueba con pytest y se ejecuta igual en cualquier equipo. La guía exige reproducibilidad.

**Alternativas descartadas:** Apache Hop (sus pipelines son archivos XML difíciles de revisar en Git), SSIS (solo Windows y requiere Visual Studio) y dbt (el adaptador de SQL Server añade complejidad que no se justifica en este alcance).

## D-04. Orquestación

**Decisión:** runner de Python por etapas (extracción, staging, calidad, DW, ML, alertas), programado con el Programador de tareas de Windows o con cron.

**Motivo:** cumple el requisito de orquestación con un mecanismo simple y explicable.

**Alternativa descartada:** Apache Airflow. La guía lo justifica solo cuando hay dependencias complejas, y aquí no las hay. Queda como trabajo futuro.

## D-05. Dashboard y API

**Decisión:** FastAPI como capa de servicios y React con Vite, TypeScript y Apache ECharts como frontend.

**Motivo:** la guía exige que el navegador no se conecte directamente a SQL Server. FastAPI usa Python, el mismo lenguaje del ETL y del modelo predictivo. React es más ligero de montar que Angular para este alcance.

**Seguridad:** la API usa un usuario de solo lectura sobre `WWI_DW`.

## D-06. Modelo predictivo

**Decisión:** pronóstico semanal de ventas. Baseline estacional ingenuo y un modelo de regresión con variables de rezago calculadas solo con datos pasados. Evaluación con MAE, RMSE y sMAPE sobre un periodo final separado.

**Motivo:** la guía pide una división temporal y prohíbe el data leakage. Con historial de ventas, el pronóstico es el problema más directo de formular.

## D-07. Asistente de IA generativa

**Decisión:** modelo abierto servido por la API de Groq, que es compatible con el SDK de OpenAI. El modelo no ejecuta SQL. Solo elige entre 6 consultas aprobadas y sus parámetros; el backend valida y ejecuta la consulta, y el modelo redacta la explicación con esos resultados.

**Motivo:** cumple la regla de la guía de no dar acceso irrestricto a SQL, sin depender de tener la RAM suficiente para un modelo local.

**Alternativas descartadas:** Ollama local (con 8 GB de RAM no cabe junto con SQL Server) y Gemini como principal (sus cuotas gratuitas se redujeron en 2026; queda como respaldo).

**Pendiente:** confirmar con el docente si una API externa es aceptable.

## D-08. Alertas

**Decisión:** tabla de reglas en la base de datos, evaluador en Python, panel con actualización periódica y correo por SMTP. Para la demo, el correo va a Mailpit, que captura los mensajes en local.

**Motivo:** cumple el requisito de notificación sin enviar correos reales durante la demo.

**Alternativa descartada:** WebSockets, que queda como trabajo futuro.

## D-09. Contenedores

**Decisión:** Docker Compose con SQL Server, API, frontend y Mailpit.

**Motivo:** la guía pide reproducibilidad. Un único comando levanta todo el entorno.

**Pendiente:** confirmar con el docente si un despliegue local es suficiente o si se requiere una URL pública. Esto define si se usa Vercel o una base de datos en la nube.

## D-10. Alcance para la entrega

**Decisión:** un solo proceso (ventas), una tabla de hechos a nivel de línea de factura y cinco dimensiones. SCD Tipo 2 solo en cliente. Dos zonas de staging (raw y limpio). Dos reglas de alerta.

**Motivo:** el plazo de entrega es el domingo y el trabajo es individual. Se conservan todos los componentes que la rúbrica evalúa, en versión mínima. Lo que queda fuera se documenta como trabajo futuro.
