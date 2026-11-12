

IF DB_ID(N'WWI_Staging') IS NULL
    CREATE DATABASE WWI_Staging;
GO

IF DB_ID(N'WWI_DW') IS NULL
    CREATE DATABASE WWI_DW;
GO

SELECT name, state_desc, recovery_model_desc
FROM sys.databases
WHERE name IN (N'WideWorldImporters', N'WWI_Staging', N'WWI_DW');
GO
