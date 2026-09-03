CREATE TABLE ProtonRegister.dbo.Course (
    CourseId		int IDENTITY(1,1) PRIMARY KEY,
    PatientSer 		nvarchar(50) NOT NULL,
    SentDt			datetime2 NOT NULL DEFAULT sysdatetime()
);

CREATE TABLE ProtonRegister.dbo.RTPlan (
    RTPlanId           int IDENTITY(1,1) PRIMARY KEY,
    CourseId           int NOT NULL,

    PlanSopUid         nvarchar(128) NOT NULL,
    PlanLabel          nvarchar(100) NULL,
  	Apprec			   nvarchar(255) NULL,

    CONSTRAINT UQ_RTPlan_PlanSopUid UNIQUE (PlanSopUid),

    CONSTRAINT FK_RTPlan_Course
        FOREIGN KEY (CourseId)
        REFERENCES Course(CourseId)
);

CREATE TABLE ProtonRegister.dbo.DicomObject (
    DicomObjectId      int IDENTITY(1,1) PRIMARY KEY,

    RTPlanId           int NOT NULL,

    ReferenceUid 	   nvarchar(128) NOT NULL,
    TypeUid 		   nvarchar(32) NOT NULL,

    Modality	       varchar(20) NOT NULL,
    BytesStored		   bigint,

    CreatedDt          datetime2 NOT NULL DEFAULT sysdatetime(),

    CONSTRAINT FK_DicomObject_RTPlan
        FOREIGN KEY (RTPlanId)
        REFERENCES RTPlan(RTPlanId),

    CONSTRAINT CK_DicomObject_Modality
        CHECK (Modality IN (
            'RTDOSE',
            'RTSTRUCT',
            'RTRECORD',
			'RTPLAN',
            'CT',
            'CBCT',
            'MR'
    )),

    CONSTRAINT CK_DicomObject_TypeUid
    	CHECK (TypeUid IN (
    		'SOP_INSTANCE',
    		'SERIES_INSTANCE',
    		'STUDY_INSTANCE'
   	))
);