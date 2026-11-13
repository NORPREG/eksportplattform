-- Creates the export logger tables in an existing database; this is not a migration.
-- Nullability follows the explicit SQLAlchemy Column definitions in export_logger_dataclass.py.
-- Timestamp defaults are supplied by the application, not by SQL Server.
USE [ProtonRegister];
GO

SET XACT_ABORT ON;
GO

BEGIN TRY
    BEGIN TRANSACTION;

    CREATE TABLE [dbo].[DicomTransfer] (
        [DicomTransferId] int IDENTITY(1,1) NOT NULL,
        [PatientSer] nvarchar(max) NULL,
        [SentDt] datetime2 NULL,

        CONSTRAINT [PK_DicomTransfer] PRIMARY KEY ([DicomTransferId])
    );

    CREATE TABLE [dbo].[RTPlan] (
        [RtPlanId] int IDENTITY(1,1) NOT NULL,
        [DicomTransferId] int NULL,
        [PlanSopUid] nvarchar(max) NULL,
        [PlanLabel] nvarchar(max) NULL,
        [Apprec] nvarchar(max) NULL,

        CONSTRAINT [PK_RTPlan] PRIMARY KEY ([RtPlanId]),
        CONSTRAINT [FK_RTPlan_DicomTransfer]
            FOREIGN KEY ([DicomTransferId])
            REFERENCES [dbo].[DicomTransfer] ([DicomTransferId])
    );

    CREATE TABLE [dbo].[DicomObject] (
        [DicomObjectId] int IDENTITY(1,1) NOT NULL,
        [RtPlanId] int NULL,
        [ReferenceUid] nvarchar(max) NULL,
        [TypeUid] nvarchar(max) NULL,
        [Modality] varchar(8) NULL,
        [BytesStored] bigint NULL,
        [TransferStatus] int NULL,
        [TransferMessage] nvarchar(max) NULL,
        [CreatedDt] datetime2 NULL,

        CONSTRAINT [PK_DicomObject] PRIMARY KEY ([DicomObjectId]),
        CONSTRAINT [CK_DicomObject_TransferStatus]
            CHECK ([TransferStatus] IN (0, 1)),
        CONSTRAINT [FK_DicomObject_RTPlan]
            FOREIGN KEY ([RtPlanId])
            REFERENCES [dbo].[RTPlan] ([RtPlanId]),
        CONSTRAINT [CK_DicomObject_Modality]
            CHECK ([Modality] IN (
                'RTDOSE',
                'RTSTRUCT',
                'RTRECORD',
                'RTPLAN',
                'CT',
                'CBCT',
                'MR',
                'SR'
            ))
    );

    CREATE TABLE [dbo].[NPRFile] (
        [FileId] int IDENTITY(1,1) NOT NULL,
        [FileName] nvarchar(max) NULL,
        [Bytes] bigint NULL,
        [Md5Hash] nvarchar(max) NULL,
        [DicomUid] nvarchar(max) NULL,
        [SentDt] datetime2 NULL,

        CONSTRAINT [PK_NPRFile] PRIMARY KEY ([FileId])
    );

    CREATE TABLE [dbo].[Apprec] (
        [ApprecId] int IDENTITY(1,1) NOT NULL,
        [RtPlanId] int NULL,
        [DicomUid] nvarchar(max) NULL,
        [ReceivedDt] datetime2 NULL,
        [MessageContents] nvarchar(max) NULL,
        [MessageStatus] int NULL,

        CONSTRAINT [PK_Apprec] PRIMARY KEY ([ApprecId]),
        CONSTRAINT [FK_Apprec_RTPlan]
            FOREIGN KEY ([RtPlanId])
            REFERENCES [dbo].[RTPlan] ([RtPlanId])
    );

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0
        ROLLBACK TRANSACTION;

    THROW;
END CATCH;
