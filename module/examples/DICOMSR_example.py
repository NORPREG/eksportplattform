from module.interfaces.NPR_ident_interface import NPRIdentInterface
from module.interfaces.NPR_interface import NPRInterface

from module.interfaces.DICOM_interface import DICOMInterface, makeDataset
from module.interfaces.ConquestInterface import ConquestInterface

from pydicom.uid import generate_uid
import pathlib
import argparse
import os

import rich


class NothingToOutputException(Exception):
	 pass


class NPRVersionNotSupportedException(Exception):
	 pass

class NoInputException(Exception):
	pass

parser = argparse.ArgumentParser(
	 description="NPR-XML to DICOM SR encapsulation program")
parser.add_argument("-f", "--inputFile", type=str, help="Input NPR XML file")
parser.add_argument("-o", "--outputFile", type=str,
						  help="Output DICOM SR file name")
parser.add_argument("-c", "--outputConquest",
						  action="store_true", help="Send directly to Conquest")
parser.add_argument("-v", "--NPRVersion",
						  help="Define NPR version (default 57)")
parser.add_argument("-p", "--parentUID", type=str, 
						  help="Study UID of parent DICOM dataset")
parser.add_argument("-d", "--dummy", action="store_true",
						  help="Make polyfactory dummy data instead of input file")
parser.add_argument("-n", "--name", type=str, help="Patient name")
parser.add_argument("-i", "--id", type=str, help="Patient ID")
parser.add_argument("--print", action="store_true", help="Print/dump NPR file")

# NPR ident file PID <-> fnr

args = parser.parse_args()

if not args.inputFile and not args.dummy:
	parser.print_help()
	raise NoInputException(
		"Please assign either input file or dummy data generation.")

if args.inputFile and args.dummy:
	parser.print_help()
	print("Both input file and dummy generation selected, using input file.")

if args.NPRVersion and args.NPRVersion != "57":
	ver = args.NPRVersion
	raise NPRVersionNotSupportedException(f"NPR version {ver} not supported.")

if not args.outputFile:
	if not args.outputConquest and not args.print:
		parser.print_help()
		raise NothingToOutputException("Need an actual output destination (outputFile OR outputConquest).")

	output = generate_uid() + ".dcm"

else:
	 output = args.outputFile

if args.inputFile:
	print(f"Opening file {args.inputFile}.")
	NPRObject = NPRInterface(args.inputFile)
else:
	print("Using dummy data generation.")
	NPRObject = NPRInterface()
	NPRObject.fillWithDummy()

# Validate XML before encapsulating to ensure it can be read again

XMLString = NPRObject.getXML()

parentUID = args.parentUID or generate_uid()
patients = NPRObject.getPatients()
if len(patients) == 1:
	patientName = args.name or str(patients[0].pasientNr)
	patientID = args.id or str(patients[0].pasientNr)
else:
	patientName = "Many"
	patientID = "123"

if args.print:
	rich.print(NPRObject.npr)

# Returns DicomInterface object
basicSR = makeDataset(parentUID, patientID, patientName, XMLString)
basicSR.saveFile(output)

if args.outputConquest:
	# Which Conquest to send to here? Provide list? Local / registry?
	# the config.py settings are used for connection.

	conquest = ConquestInterface()
	response, config = conquest.sendDS(basicSR.ds)
	print(f"File {output} sent to Conquest at {config['conquestIP']}:{config['conquestPort']}.")

if not args.outputFile:
	os.remove(output)