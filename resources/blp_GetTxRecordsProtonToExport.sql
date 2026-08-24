CREATE proc [dbo].[blp_GetTxRecordsProtonToExport]
	(@FromDateTime	datetime = null)
 
as
 
declare @fromdate date
 
--If fromdate not given, get plans 6 month before
 
if (@FromDateTime is null) 
	select @FromDateTime = dateadd(month, -6, getdate())
 
select @fromdate = convert(date, @FromDateTime)
 
select distinct tr.PatientSer, tr.PlanUID, tr.TreatmentRecordUID, dm.DoseUID
from TreatmentRecord tr join Patient p on tr.PatientSer = p.PatientSer 
						join RTPlan rtp on tr.RTPlanSer = rtp.RTPlanSer
						join PlanSetup ps on rtp.PlanSetupSer = ps.PlanSetupSer
						left outer join DoseMatrix dm on ps.PlanSetupSer = dm.PlanSetupSer
where convert(date, tr.TreatmentRecordDateTime) > @fromdate
and tr.ActualMachineSer in (select distinct ResourceSer
					from Machine
					where lower(MachineId) like 'sb9_%' 
					or lower(MachineId) like 'sb10_%')
and p.PatientSer = tr.PatientSer
and lower(p.PatientId) not like 'z%'
 
return 0
 
GO
