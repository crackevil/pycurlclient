import pycurl
from pycurlclient import pycurlClient
import six
import io
from requests.adapters import BaseAdapter
from requests.utils import select_proxy
from requests.models import Response
from requests.cookies import extract_cookies_to_jar
from requests.structures import CaseInsensitiveDict


class pycurlAdapter(BaseAdapter):

	def __init__(self, http2=False, verbose=False):
		super(pycurlAdapter, self).__init__()
		opt = {}
		if http2:
			opt[pycurl.HTTP_VERSION] = pycurl.CURL_HTTP_VERSION_2_0
		if verbose:
			opt[pycurl.VERBOSE] = 1
		self.client = pycurlClient(opt)

	def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
		if stream:
			raise RuntimeError('not suppoert stream')
		url = request.url
		proxy = select_proxy(url, proxies)
		headers = dict(request.headers)
		enc = 'Accept-Encoding'
		if enc in headers:
			headers[enc] = 'gzip, deflate'
		method = request.method.upper()
		if 'GET' == method:
			resp = self.client.get(url=url, headers=headers, proxy=proxy, verify=verify)
		elif 'POST' == method:
			body = io.BytesIO(request.body) if request.body else io.BytesIO()
			resp = self.client.post(url=url, read_fd=body, headers=headers, proxy=proxy, verify=verify)
		elif 'HEAD' == method:
			resp = self.client.head(url=url, headers=headers, proxy=proxy, verify=verify)
		else:
			raise RuntimeError('unsupport method')
		response = Response()
		response.status_code = resp.status
		response.headers = CaseInsensitiveDict()
		for k, v in six.iteritems(resp.headers):
			response.headers[k.capitalize()] = v
		response.encoding = resp.headers.encoding
		response.raw = resp
		response.raw._original_response = resp	# not matters
		response.raw._original_response.msg = resp.headers	# headers obj
		response.url = url
		extract_cookies_to_jar(response.cookies, request, resp)

		response.request = request

		return response

