
import pycurl
import six
import re
from future.standard_library import install_aliases
install_aliases()

from urllib.response import addinfourl


from threading import Lock
from http_headers import HTTPHeaders
import io

import certifi

__all__ = ['pycurlResponseHeaders', 'pycurlResponse', 'pycurlClient']

class pycurlResponseHeaders(HTTPHeaders):

	def handle_headerline(self, header_line):
		header_line = header_line.decode('iso-8859-1')
		if ':' in header_line:
			name, value = header_line.split(':', 1)
			name = name.strip()
			value = value.strip()
			name = name.lower()
			self.add_header(name, value)

	@property
	def encoding(self):
		if 'content-type' in self:
			content_type = self['content-type'].lower()
			match = re.search(r'charset=(\S+)', content_type)
			if match:
				return match.group(1)
		return 'iso-8859-1'

	@property
	def content_length(self):
		try:
			return int(self.get('content-length'))
		except (KeyError, TypeError):
			pass

	@property
	def last_modified(self):
		try:
			return self['last-modified']
		except KeyError:
			pass


class pycurlBase(object):
	'''
	simple holder of curl object
	and a simple interface of setting options
	'''

	def __init__(self):
		self.handle = pycurl.Curl()
		self.handle_lock = Lock()

	def __del__(self):
		self.handle.close()

	def __setopt__(self, opt_mapping):
		for key, value in six.iteritems(opt_mapping):
			self.handle.setopt(key, value)

	def setopt(self, opt_mapping):
		with self.handle_lock:
			self.__setopt__(opt_mapping)

	def __unsetopt__(self, opt):
		for key in opt:
			try:
				self.handle.unsetopt(key)
			except TypeError:
				continue

	def unsetopt(self, opt):
		with self.handle_lock:
			self.__unsetopt__(opt)

	def perform(self, options):
		with self.handle_lock:
			self.__setopt__(options)
			code = None
			try:
				self.handle.perform()
				code = self.handle.getinfo(pycurl.RESPONSE_CODE)
			finally:
				self.handle.reset()
			return code

	def is_performing(self):
		return self.handle_lock.locked()


class pycurlResponse(addinfourl):

	def __init__(self, fp, headers, url, code=None):
		assert isinstance(headers, pycurlResponseHeaders)
		addinfourl.__init__(self, fp=fp, headers=headers, url=url, code=code)

	# compat with 3.9+
	@property
	def status(self):
		return self.code

	@property
	def text(self):
		return self.content.decode(self.encoding)

	@property
	def cookies(self):
		pass


class pycurlClient(pycurlBase):
	'''
	stateless interface under HTTP context
	'''

	def __init__(self, options_for_all=None):
		super(pycurlClient, self).__init__()
		self.options_for_all = options_for_all or {}

	def get(self, url, headers=None, cookies=None, body_fd=None, proxy=None, verify=True, cert=None):
		body_fd = body_fd or io.BytesIO()
		resp_headers = pycurlResponseHeaders()
		opt_mapping = {
			pycurl.HTTPGET: 1,
			pycurl.HEADERFUNCTION: resp_headers.handle_headerline,
			pycurl.WRITEFUNCTION: body_fd.write
		}
		opt_mapping.update(self.general_options(url, headers=headers, cookies=cookies, proxy=proxy, verify=verify, cert=cert))
		code = self.perform(opt_mapping)

		body_fd.seek(io.SEEK_SET)

		return pycurlResponse(fp=body_fd, headers=resp_headers, url=url, code=code)

	def post(self, url, read_fd, headers=None, cookies=None, body_fd=None, proxy=None, verify=True, cert=None):
		body_fd = body_fd or io.BytesIO()
		resp_headers = pycurlResponseHeaders()
		opt_mapping = {
			pycurl.POST: 1,
			pycurl.HEADERFUNCTION: resp_headers.handle_headerline,
			pycurl.WRITEFUNCTION: body_fd.write,
			pycurl.READFUNCTION: read_fd.read
		}
		opt_mapping.update(self.general_options(url, headers=headers, cookies=cookies, proxy=proxy, verify=verify, cert=cert))
		code = self.perform(opt_mapping)
		body_fd.seek(io.SEEK_SET)
		return pycurlResponse(fp=body_fd, headers=resp_headers, url=url, code=code)

	def head(self, url, headers=None, cookies=None, proxy=None, verify=True, cert=None):
		resp_headers = pycurlResponseHeaders()
		opt_mapping = {
			pycurl.NOBODY: 1,
			pycurl.HEADERFUNCTION: resp_headers.handle_headerline
		}
		opt_mapping.update(self.general_options(url, headers=headers, cookies=cookies, proxy=proxy, verify=verify, cert=cert))
		code = self.perform(opt_mapping)
		return pycurlResponse(fp=io.BytesIO(), headers=resp_headers, url=url, code=code)

	def ssl_option(self, verify=True, cert=None):
		opt_mapping = {
			pycurl.CAINFO: cert or certifi.where()
		}
		if not verify:
			opt_mapping[pycurl.SSL_VERIFYHOST] = 0
			opt_mapping[pycurl.SSL_VERIFYPEER] = 0
		return opt_mapping

	def header_option(self, headers_mapping=None):
		if headers_mapping:
			hdr_str = ['{k}: {v}'.format(k=k, v=v) for k, v in six.iteritems(headers_mapping)]
			return {pycurl.HTTPHEADER: hdr_str}
		else:
			return {}

	def general_options(self, url, headers=None, cookies=None, proxy=None, verify=True, cert=None):
		opt_mapping = {
			pycurl.ACCEPT_ENCODING: '',
			pycurl.FOLLOWLOCATION: 0,
			pycurl.IPRESOLVE: pycurl.IPRESOLVE_V4
		}
		opt_mapping.update(self.options_for_all)
		opt_mapping[pycurl.URL] = url
		if proxy:
			opt_mapping[pycurl.PROXY] = proxy
		opt_mapping.update(self.ssl_option(verify=verify, cert=cert))
		opt_mapping.update(self.header_option(headers))
		return opt_mapping

