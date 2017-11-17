try:
    import urllib.parse as urllib
except ImportError:
    import urllib
from six.moves.urllib.parse import urlsplit, urlunsplit, quote, unquote
import re
import logging
import six

from weblib.encoding import make_str, make_unicode, decode_pairs

from weblib.py3k_support import *

# I do not know, what the hell is going on, but sometimes
# when IDN url should be requested grab fails with error
# LookupError: unknown encoding: punycode
# That happens in grab/base.py near by 347 line on the line::
# kwargs['url'] = normalize_url(kwargs['url'])
# If you try to catch the error with except and import pdb; pdb.set_trace()
# then you'll get "no pdb module" error. WTF??
# But if you import pdb at the top of the module then you can use it
# So.... I import here this module and I hope that will helps
# My idea is that some mystical shit does some thing that breaks python
# environment,, breaks sys.path So, when special case occurs and some new module
# is need to be imported then that can't be done due to the unknown magical influence
import encodings.punycode

# From RFC 3986
# reserved    = gen-delims / sub-delims
# gen-delims  = ":" / "/" / "?" / "#" / "[" / "]" / "@"
# sub-delims  = "!" / "$" / "&" / "'" / "(" / ")"
#               / "*" / "+" / "," / ";" / "="
# unreserved  = ALPHA / DIGIT / "-" / "." / "_" / "~"
GEN_DELIMS = r':/?#[]@'
SUB_DELIMS = r'!$&\'()*+,;='
RESERVED_CHARS = GEN_DELIMS + SUB_DELIMS + '%'
UNRESERVED_CHARS = r'-._~a-zA-Z0-9'
RE_NOT_SAFE_CHAR = re.compile(r'[^' +
                              UNRESERVED_CHARS + 
                              re.escape(RESERVED_CHARS) + ']')
RE_NON_ALPHA_DIGIT_NETLOC = re.compile(r'[^-.:@a-zA-Z0-9]')
logger = logging.getLogger('weblib.http')


def urlencode(*args, **kwargs):
    logger.debug('Method weblib.http.urlencode is deprecated. '
                 'Please use weblib.http.smart_urlencode')
    return smart_urlencode(*args, **kwargs)


def smart_urlencode(items, charset='utf-8'):
    """
    Convert sequence of items into bytestring which could be submitted
    in POST or GET request.

    It differs from ``urllib.urlencode`` in that it can process unicode
    and some special values.

    ``items`` could dict or tuple or list.
    """

    if isinstance(items, dict):
        items = items.items()
    return urllib.urlencode(normalize_http_values(items, charset=charset))


def encode_cookies(items, join=True, charset='utf-8'):
    """
    Serialize dict or sequence of two-element items into string suitable
    for sending in Cookie http header.
    """

    def encode(val):
        """
        URL-encode special characters in the text.

        In cookie value only ",", " ", "\t" and ";" should be encoded
        """

        return val.replace(b' ', b'%20').replace(b'\t', b'%09')\
                  .replace(b';', b'%3B').replace(b',', b'%2C')

    if isinstance(items, dict):
        items = items.items()
    items = normalize_http_values(items, charset=charset)

    # py3 hack
    #if PY3K:
    #    items = decode_pairs(items, charset)

    tokens = []
    for key, value in items:
        tokens.append(b'='.join((encode(key), encode(value))))
    if join:
        return b'; '.join(tokens)
    else:
        return tokens


def normalize_http_values(items, charset='utf-8', ignore_classes=None):
    """
    Accept sequence of (key, value) paris or dict and convert each
    value into bytestring.

    Unicode is converted into bytestring using charset of previous response
    (or utf-8, if no requests were performed)

    None is converted into empty string. 

    If `ignore_classes` is not None and the value is instance of
    any classes from the `ignore_classes` then the value is not
    processed and returned as-is.
    """

    if isinstance(items, dict):
        items = items.items()

    def process(item):
        key, value = item

        if ignore_classes and isinstance(value, ignore_classes):
            pass
        elif isinstance(value, unicode):
            value = normalize_unicode(value, charset=charset)
        elif value is None:
            value = ''
        else:
            value = str(value)

        if isinstance(key, unicode):
            key = normalize_unicode(key, charset=charset)

        return key, value

    items =  list(map(process, items))
    #items = sorted(items, key=lambda x: x[0])
    return items


def normalize_unicode(value, charset='utf-8'):
    """
    Convert unicode into byte-string using detected charset (default or from
    previous response)

    By default, charset from previous response is used to encode unicode into
    byte-string but you can enforce charset with ``charset`` option
    """

    if not isinstance(value, unicode):
        return value
    else:
        return value.encode(charset, 'ignore')


def normalize_url(url):
    # https://tools.ietf.org/html/rfc3986
    url = make_unicode(url)
    if RE_NOT_SAFE_CHAR.search(url):
        parts = list(urlsplit(url))
        # Scheme
        pass
        # Network location (user:pass@hostname)
        if RE_NON_ALPHA_DIGIT_NETLOC.search(parts[1]):
            parts[1] = parts[1].encode('idna')
        # Path
        parts[2] = quote(make_str(parts[2]), safe=RESERVED_CHARS)
        # Query
        parts[3] = quote(make_str(parts[3]), safe=RESERVED_CHARS)
        # Fragment
        parts[4] = quote(make_str(parts[4]), safe=RESERVED_CHARS)
        return urlunsplit(map(make_unicode, parts))
    return url


def normalize_post_data(data, charset):
    if isinstance(data, (six.binary_type, six.text_type)):
        # bytes-string should be posted as-is
        # unicode should be converted into byte-string
        if isinstance(data, unicode):
            return normalize_unicode(data, charset)
        else:
            return data
    else:
        # dict, tuple, list should be serialized into byte-string
        return smart_urlencode(data, charset)
