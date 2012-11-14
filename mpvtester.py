#!/usr/bin/python
import argparse
import os
import pycurl
import re
import sys
import zipfile

from HTMLParser import HTMLParser

class ValidateFileDir(argparse.Action):
	def __call__(self, parser, namespace, values, option_string=None):
		for file in values:
			if not os.path.isfile(file) and not os.path.isdir(file) or not os.access(file, os.R_OK):
				raise argparse.ArgumentTypeError("File: {0} is not a valid file!".format(file))

		setattr(namespace, self.dest, values)

class CreateZip:
	def __init__(self, packageName, files):
		self.files			= files

		if len(files) == 1:
			try:
				zip = zipfile.ZipFile(files[0], mode='r')
				self.packageName = files[0]
				zip.close()
				return
			except IOError:
				pass

		self.packageName	= packageName + '.zip'

	def buildPackage(self):
		if os.path.isfile(self.packageName):
			return

		self.zip = zipfile.ZipFile(self.packageName, mode='w')
		try:
			for file in self.files:
				self.zip.write(file)
		finally:
			self.zip.close()

	def getPackageName(self):
		return self.packageName

class MPVResponceHTMLParser(HTMLParser):
	inType = 0

	notices		= []
	warnings	= []
	fails		= []

	def __init__(self):
		HTMLParser.__init__(self)
		self.matcher = re.compile('\[|\]|NOTICE|WARNING|FAIL')

	def handle_starttag(self, tag, attrs):
		if tag == 'span':
			for attr, value in attrs:
				if attr == 'style':
					if value == 'color:blue;':
						self.inType = 1
						break
					elif value == 'color:orange;':
						self.inType = 2
						break
					elif value == 'color:red;':
						self.inType = 3
						break

	def handle_endtag(self, tag):
		if tag == 'br':
			if self.inType == 1:
				self.notices.append(self._buf)
			elif self.inType == 2:
				self.warnings.append(self._buf)
			elif self.inType == 3:
				self.fails.append(self._buf)

			self.inType	= 0
			self._buf	= ''

	_buf = ''

	def handle_data(self, data):
		if self.inType > 0:
			_m = self.matcher.match(data.strip())
			if _m is not None:
				return;

			self._buf += data

	def getNotices(self):
		return self.notices

	def getWarnings(self):
		return self.warnings

	def getFails(self):
		return self.fails

class RequestMPVReport:
	def __init__(self):
		self.data = ''

		mpvAddress = 'https://www.phpbb.com/mods/mpv/index.php'

		self.curl = pycurl.Curl()
		self.curl.setopt(self.curl.POST, 1)
		self.curl.setopt(self.curl.URL, mpvAddress)

		self.parser = MPVResponceHTMLParser()

	def send(self, packageName):
		_values = [
			("submit", "True"),
			("url_request", (self.curl.FORM_FILE, packageName))
		]

		self.curl.setopt(self.curl.HTTPPOST, _values)
		#self.curl.setopt(self.curl.VERBOSE, 1)
		self.curl.setopt(self.curl.WRITEFUNCTION, self._setResponce)
		self.curl.perform()
		self.curl.close()

	def _setResponce(self, buf):
		self.data = self.data + buf

	def getResponce(self):
		self.parser.feed(self.data)
		self.parser.close()

	def getParser(self):
		return self.parser

if __name__ == '__main__' :
	# Setup the parser
	parser = argparse.ArgumentParser (description='Build package and run through MPV.')
	parser.add_argument('-m', '--mod', default='MPVValidation', help='The name of the MOD')
	parser.add_argument('files', metavar='F', action=ValidateFileDir, nargs='+', help='The files that are included')
	args = parser.parse_args()

	# Prepare the zip archive
	zip = CreateZip(args.mod, args.files)
	zip.buildPackage()

	# Send
	request = RequestMPVReport()
	request.send(zip.getPackageName())
	request.getResponce()

	parser = request.getParser()

	# Output result:

	print("# Validation notices\n####################")
	if (len(parser.getNotices()) == 0):
		print("No notices found")
	else:
		for l in parser.getNotices():
			print(l.strip())

	print("\n")
	
	print("# Validation errors\n###################")
	if (len(parser.getWarnings()) == 0):
		print("No errors found")
	else:
		for l in parser.getWarnings():
			print(l.strip())

	print("\n")

	print("# Validation errors\n###################")
	if (len(parser.getFails()) == 0):
		print("No errors found")
	else:
		for l in parser.getFails():
			print(l.strip())

		# Nuke the build
		sys.exit(1)

	sys.exit(0)
