import sqlalchemy
import pyodbc
import pandas as pd
import os
import subprocess

print("Current user: ", os.getlogin())

pwd = os.getenv("pwd")
hostip = "VIR-APP5338"
username = "rttn"
domain = "HS"

connstring = f"mssql+pyodbc://{hostip}/localrtdb?driver=SQL+Server"

engine = sqlalchemy.create_engine(connstring)
sql = "SET NOCOUNT ON; EXEC blp_GetStudiesToKrest"
data = pd.read_sql_query(sql, engine)

study_uids = list(data.StudyUID)

print(study_uids)

#os.chdir("D:/Conquest/MEDFYSHUS6666-1/")
#app_exe = "dgate64.exe"
#arg = f"--movestudy:VMSDBD,MEDFYSHUS6666-1,:{study_uid}"
#arg = f"--moveseries:VMSDBD,MEDFYSHUS6666-1,:{series_uid}"
#subprocess.run([app_exe, arg])

for study_uid in study_uids:
	print(study_uid)

	app_exe = R"D:\Conquest\MEDFYSHUS6666-1\dgate64.exe"
	args = [
		f"--movestudy:VMSDBD,MEDFYSHUS6666-1,:{study_uid}"
	]
	command = [app_exe, *args]
	subprocess.run(command)
	print()
	print(f"Moved patient with study UID {study_uid}")