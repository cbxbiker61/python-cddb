""" Python CDDB-Access
Access gnudb service from Python.
"""

import getpass, os, re, socket, subprocess, sys, urllib.parse, urllib.request

__version__ = "1.1.0"

class CommandException(RuntimeError):
	status = None
	text = None

	def __init__(self, status, text):
		super().__init__()
		self.status = status
		self.text = text

def runCommand(args):
	p = subprocess.Popen(args,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				universal_newlines=True)
	com = p.communicate()
	rc = p.wait()

	if rc:
		raise CommandException(rc, " ".join(args) + ": " + com[1])

	return com[0]

class CddbDisc:
	category = None
	discid = None
	artist = None
	title = None

	def __init__(self, category, discid, artist, title):
		self.category = category
		self.discid = discid
		self.artist = artist
		self.title = title

class CddbDiscInfo:
	discid = None
	artist = None
	title = None
	year = None
	genre = None
	tracks = None

	def __init__(self, discid, artist, title, year, genre, tracks):
		self.discid = discid
		self.artist = artist
		self.title = title
		self.year = year
		self.genre = genre
		self.tracks = tracks

class CddbServer:
	def __init__(self, device = None, cddbServer = 'http://gnudb.gnudb.org/~cddb/cddb.cgi',
			app = "PythonCddbServer", version = __version__):
		self.device = "/dev/cdrom" if os.path.exists("/dev/cdrom") else "/dev/sr0"

		if device:
			self.device = device

		self.cddbServer = cddbServer
		self.host = socket.gethostname()
		self.app = app
		self.version = version
		self.protocol = 5
		self.code = 0
		self.user = getpass.getuser()

		if " " in self.user:
			self.user = self.user.replace(" ","")

		self.reArtistTitle = re.compile('(?P<Artist>[^\/]*)\/(?P<Title>[^\/]*)')
		self.reCode = re.compile("[0-9]+.*")
		self.reDISCID = re.compile("DISCID=(?P<DiscId>.*)")
		self.reDTITLE = re.compile("DTITLE=(?P<DiscTitle>.*)")
		self.reDYEAR = re.compile("DYEAR=(?P<DiscYear>.*)")
		self.reDGENRE = re.compile("DGENRE=(?P<DiscGenre>.*)")
		self.reTTITLE = re.compile("TTITLE(?P<TrackNum>[^=]*)=(?P<TrackTitle>.*)")

	def getDiscs(self, discid = None):
		discs = None

		if not discid:
			discid = runCommand(['discid', self.device])

		if discid:
			self.track_offset = map(int, discid.split()[2:-1])
			self.disc_length = int(discid.split()[-1:][0]) * 75
			query = urllib.parse.quote_plus(discid.rstrip())
			url = "%s?cmd=cddb+query+%s&hello=%s+%s+%s+%s&proto=%d" % \
				(self.cddbServer, query, self.user, self.host,
					self.app, self.version, self.protocol)
			res = urllib.request.urlopen(url)
			header = res.readline().decode('latin-1').rstrip()

			if self.reCode.match(header):
				self.code = int(header.split(' ', 1)[0])

				artist = ""
				title = ""

				if self.code == 200: # Exact match
					info = header.split(' ', 3)
					m = self.reArtistTitle.match(info[3])

					if m:
						artist = m.group('Artist').rstrip()
						title = m.group('Title').lstrip()

					if not discs: discs = []

					discs.append( CddbDisc(info[1], info[2], artist, title) )
				elif self.code == 210 or self.code == 211: # Multiple exact matches or inexact match
					line = res.readline().decode('latin-1').rstrip()

					while line != ".":
						info = line.split(' ', 2)
						m = self.reArtistTitle.match(info[2])

						if m:
							artist = m.group('Artist').rstrip()
							title = m.group('Title').lstrip()

						if not discs: discs = []

						discs.append( CddbDisc(info[0], info[1], artist, title) )
						line = res.readline().decode('latin-1').rstrip()

		return discs

	def getDiscInfo(self, disc):
		discInfo = None
		url = "%s?cmd=cddb+read+%s+%s&hello=%s+%s+%s+%s&proto=%d" % \
				(self.cddbServer, disc.category, disc.discid,
				self.user, self.host, self.app, self.version, self.protocol)
		res = urllib.request.urlopen(url)
		header = res.readline().decode('latin-1').rstrip()
		self.code = int(header.split(' ', 1)[0])

		if self.code == 210:
			discid = None
			title = None
			year = None
			genre = None
			tracks = []
			for line in res.readlines():
				line = line.decode('latin-1').rstrip()

				m = self.reDISCID.match(line)
				if m:
					discid = m.group("DiscId")

				m = self.reDTITLE.match(line)
				if m:
					m = self.reArtistTitle.match(m.group("DiscTitle"))

					if m:
						artist = m.group('Artist').rstrip()
						title = m.group('Title').lstrip()

				m = self.reDYEAR.match(line)
				if m:
					year = m.group("DiscYear")

				m = self.reDGENRE.match(line)
				if m:
					genre = m.group("DiscGenre")

				m = self.reTTITLE.match(line)
				if m:
					if not tracks: tracks = []
					tracks.append(m.group("TrackTitle"))

			return CddbDiscInfo(discid, artist, title, year, genre, tracks)

		return None

	def status(self):
		return self.code

	def message(self):
		if self.code == 0:
			return ""
		elif self.code == 200:
			return "Found exact match"
		elif self.code == 202:
			return "No match found"
		elif self.code == 210:
			return "Ok"
		elif self.code == 211:
			return "Found inexact matches"
		elif self.code == 401:
			return "Specified CDDB entry not found"
		elif self.code == 402:
			return "Server error"
		elif self.code == 403:
			return "Database entry is corrupt"
		elif self.code == 409:
			return "No handshake"
		else:
			return "Unknown code %s" % self.code

