from module.dataclasses.custom_exceptions import TerminologyNotFoundException

class Region:
	def __init__(self):
		self.Region = dict()
		with open("terminologies/regionskoder.csv", "r", encoding="utf-8") as csv:
			for line in csv.readlines():
				lineparsed = line.replace("\n", "").split(";")
				self.Region[lineparsed[0]] = lineparsed[1]

	def getRegionDefinition(self, code: str) -> str:
		code = str(code)
		if code not in self.Region:
			raise TerminologyNotFoundException(f"Regionskode not found: {code}")

		return self.Region.get(code)
