# -*- coding: utf-8 -*-

"""
Twitter OAuth Support for Google App Engine Apps.
 
Using this in your app should be relatively straightforward:
 
* Edit the configuration section below with the CONSUMER_KEY and CONSUMER_SECRET
from Twitter.
 
* Modify to reflect your App's domain and set the callback URL on Twitter to:
 
http://your-app-name.appspot.com/oauth/twitter/callback
 
* Use the demo in ``MainHandler`` as a starting guide to implementing your app.
 
Note: You need to be running at least version 1.1.9 of the App Engine SDK.
 
-- 
I hope you find this useful, tav
 
"""
 
# Released into the Public Domain by tav@espians.com
 
#import sys

from datetime import datetime, timedelta
from hashlib import sha1
from hmac import new as hmac
from random import getrandbits
from time import time
from urllib import urlencode, quote as urlquote
from uuid import uuid4
from wsgiref.handlers import CGIHandler
 
#sys.path.insert(0, join_path(dirname(__file__), 'lib')) # extend sys.path
 
from demjson import decode as decode_json
 
from google.appengine.api.urlfetch import fetch as urlfetch
from google.appengine.ext import db
from google.appengine.ext.webapp import RequestHandler, WSGIApplication
from google.appengine.api import users

from nemuio_db import OAuthStatusCodes
from nemuio_db import OAuthAccessToken
from nemuio_db import OAuthRequestToken
from nemuio_db import UserPrefs
 
# ------------------------------------------------------------------------------
# configuration -- SET THESE TO SUIT YOUR APP!!
# ------------------------------------------------------------------------------

OAUTH_APP_SETTINGS = {
    'twitter': {
 
        'consumer_key': 'key',
        'consumer_secret': 'secret_key',
 
        'request_token_url': 'https://twitter.com/oauth/request_token',
        'access_token_url': 'https://twitter.com/oauth/access_token',
        'user_auth_url': 'https://twitter.com/oauth/authorize',
 
        'default_api_prefix': 'http://twitter.com',
        'default_api_suffix': '.json',
 
        },
    }

CLEANUP_BATCH_SIZE = 100
EXPIRATION_WINDOW = timedelta(seconds=60*60*1) # 1 hour
 
try:
    from config import OAUTH_APP_SETTINGS
except:
    pass
 
STATIC_OAUTH_TIMESTAMP = 12345 # a workaround for clock skew/network lag

class TwitterOAuthError(Exception):
    '''Base class for Twitter errors'''
  
    @property
    def message(self):
        '''Returns the first argument used to construct this error.'''
        return self.args[0]

# ------------------------------------------------------------------------------
# utility functions
# ------------------------------------------------------------------------------
 
def get_service_key(service, cache={}):
    if service in cache: return cache[service]
    return cache.setdefault(
        service, "%s&" % encode(OAUTH_APP_SETTINGS[service]['consumer_secret'])
        )
 
def create_uuid():
    return 'id-%s' % uuid4()

def create_key(key):
    import hashlib
    str = '%s-%s' % (key, uuid4())
    return hashlib.sha256(str).hexdigest()
 
def encode(text):
    return urlquote(str(text), '')
 
def twitter_specifier_handler(client):
    return client.get('/account/verify_credentials')['screen_name']
 
OAUTH_APP_SETTINGS['twitter']['specifier_handler'] = twitter_specifier_handler
 
# ------------------------------------------------------------------------------
# oauth client
# ------------------------------------------------------------------------------
 
class OAuthClient(object):
 
    __public__ = ('callback', 'cleanup', 'login', 'logout')
 
    def __init__(self, service, handler, oauth_callback=None, **request_params):
        self.service = service
        self.service_info = OAUTH_APP_SETTINGS[service]
        self.service_key = None
        self.handler = handler
        self.request_params = request_params
        self.oauth_callback = oauth_callback
        self.token = None
 
    # public methods
 
    def get(self, api_method, http_method='GET', expected_status=(200,), **extra_params):
 
        if not (api_method.startswith('http://') or api_method.startswith('https://')):
            api_method = '%s%s%s' % (
                self.service_info['default_api_prefix'], api_method,
                self.service_info['default_api_suffix']
                )
 
        if self.token is None:
            #cookie = self.get_cookie()
            #self.token = OAuthAccessToken.get_by_key_name(cookie['key'])
            #self.token = self.get_access_token(self)
            #if not self.token:
            #    raise TwitterOAuthError("You need Login.")
            raise TwitterOAuthError("You need Login.")
            
        fetch = urlfetch(self.get_signed_url(
            api_method, self.token, http_method, **extra_params
            ))
        
        self.logging('GET', api_method, fetch.status_code, **extra_params)
 
        if fetch.status_code not in expected_status:
            raise ValueError(
                "Error calling... Got return status: %i [%r]" %
                (fetch.status_code, fetch.content)
                )
            
        return decode_json(fetch.content)
 
    def post(self, api_method, http_method='POST', expected_status=(200,), **extra_params):
 
        if not (api_method.startswith('http://') or api_method.startswith('https://')):
            api_method = '%s%s%s' % (
                self.service_info['default_api_prefix'], api_method,
                self.service_info['default_api_suffix']
                )
 
        if self.token is None:
            #cookie = self.get_cookie()
            #self.token = OAuthAccessToken.get_by_key_name(cookie['key'])
            raise TwitterOAuthError("You need Login.")
 
        fetch = urlfetch(url=api_method, payload=self.get_signed_body(
            api_method, self.token, http_method, **extra_params
            ), method=http_method)
        
        self.logging('POST', api_method, fetch.status_code, **extra_params)
 
        if fetch.status_code not in expected_status:
            raise ValueError(
                "Error calling... Got return status: %i [%r]" %
                (fetch.status_code, fetch.content)
                )
        
        return decode_json(fetch.content)
    
    def logging(self, method, api_method, status_code, **extra_params):
        oauth_status_codes = OAuthStatusCodes()
        oauth_status_codes.method = method
        oauth_status_codes.api_method = api_method
        oauth_status_codes.status_code = status_code
        if extra_params is not None:
            param_str = ''
            for key, item in extra_params.items():
                param_str += '%s : %s,' % (key, unicode(item, 'utf-8'))
                if key == 'status':
                    oauth_status_codes.tweet = unicode(item, 'utf-8')
            oauth_status_codes.extra_params = param_str
        oauth_status_codes.oauth_access_token_key = self.token.key()
        oauth_status_codes.put()
    
    def login(self):
        #FIX ME: IF Always Logged in,Error Print 'FOO'
        #proxy_id = self.get_cookie()
 
        #if proxy_id:
        #    return "FOO%rFF" % proxy_id
        #    self.expire_cookie()
        self.expire_cookie()
 
        return self.get_request_token()
 
    def logout(self, return_to='/'):
        self.expire_cookie()
        self.handler.redirect(self.handler.request.get("return_to", return_to))
 
    # oauth workflow
 
    def get_request_token(self):
 
        token_info = self.get_data_from_signed_url(
            self.service_info['request_token_url'], **self.request_params
            )
 
        token = OAuthRequestToken(
            service=self.service,
            **dict(token.split('=') for token in token_info.split('&'))
            )
 
        token.put()
 
        if self.oauth_callback:
            oauth_callback = {'oauth_callback': self.oauth_callback}
        else:
            oauth_callback = {}
            
        self.handler.redirect(self.get_signed_url(
            self.service_info['user_auth_url'], token, **oauth_callback
            ))
 
    def callback(self, return_to='/config'):
        oauth_token = self.handler.request.get("oauth_token")
 
        if not oauth_token:
            return self.get_request_token()
 
        oauth_token = OAuthRequestToken.all().filter(
            'oauth_token =', oauth_token).filter(
            'service =', self.service).fetch(1)[0]
 
        token_info = self.get_data_from_signed_url(
            self.service_info['access_token_url'], oauth_token
            )
        
        """
        key_name = create_uuid()

        self.token = OAuthAccessToken(
            key_name=key_name, service=self.service,
            **dict(token.split('=') for token in token_info.split('&'))
            )
 
        if 'specifier_handler' in self.service_info:
            specifier = self.token.specifier = self.service_info['specifier_handler'](self)
            old = OAuthAccessToken.all().filter(
                'specifier =', specifier).filter(
                'service =', self.service)
            db.delete(old)
 
        self.token.put()
        """
        
        #logging.error("token_info="+token_info)
        token_info_list = dict(token.split('=') for token in token_info.split('&'))
        
        token_query = OAuthAccessToken.all()
        token_query.filter("oauth_token =", token_info_list["oauth_token"])
        token_query.filter("oauth_token_secret =", token_info_list["oauth_token_secret"])
        token_query.filter("service =", self.service)
       
        #logging.error("oauth_token="+token_info_list["oauth_token"])
        #logging.error("service="+self.service)
        
        #remember_key = create_key(token_info_list["screen_name"])
        
        if not token_query.count():
            key_name = create_uuid()
            self.token = OAuthAccessToken(key_name=key_name)
            #self.token.key_name = create_uuid()
            self.token.oauth_token = token_info_list["oauth_token"]
            self.token.oauth_token_secret = token_info_list["oauth_token_secret"]
            self.token.service = self.service
            self.token.specifier = token_info_list["screen_name"]
            #self.token.remember_key = remember_key
            self.token.put()
            
        else:
            self.token = token_query.get()
            if self.token.specifier != token_info_list["screen_name"]:
                self.token.specifier = token_info_list["screen_name"]
                
            self.token.updated_at = datetime.now()
            self.token.put()
            
        user = users.get_current_user()
        user_prefs_query = UserPrefs.all()
        user_prefs_query.filter("google_id =", user)
        #user_prefs_query.filter("oauth_access_token_key =", self.token.key())
        user_prefs = user_prefs_query.get()
        if user_prefs is None:
            user_prefs = UserPrefs()
            user_prefs.google_id = user
            user_prefs.oauth_access_token_key = self.token.key()
            user_prefs.put()
        else:
            #user_prefs.google_id = user
            user_prefs.oauth_access_token_key = self.token.key()
            user_prefs.put()
        
        #cookie_value = {}
        #cookie_value['key'] = remember_key
        #cookie_value['specifier'] = self.token.specifier
        
        #memcache.add("twitter_token_" + remember_key, self.token, 3600)
        
        #self.set_cookie(cookie_value)
        self.handler.redirect(return_to)
 
    def cleanup(self):
        query = OAuthRequestToken.all().filter(
            'created <', datetime.now() - EXPIRATION_WINDOW
            )
        token_count = query.count(CLEANUP_BATCH_SIZE)
        db.delete(query.fetch(CLEANUP_BATCH_SIZE))
        
        EXPIRATION_STATUS_CODES = timedelta(seconds=60*60*24*3) # 3 days
        query = OAuthStatusCodes.all().filter(
            'date <', datetime.now() - EXPIRATION_STATUS_CODES
            )
        codes_count = query.count(CLEANUP_BATCH_SIZE)
        db.delete(query.fetch(CLEANUP_BATCH_SIZE))
        return "Cleaned Token:%i Codes:%i entries" % (token_count, codes_count)
 
    def logging_cleanup(self):
        EXPIRATION_WINDOW = timedelta(seconds=60*60*24) # 1 hour
        query = OAuthStatusCodes.all().filter(
            'date <', datetime.now() - EXPIRATION_WINDOW
            )
        count = query.count(CLEANUP_BATCH_SIZE)
        db.delete(query.fetch(CLEANUP_BATCH_SIZE))
        return "Cleaned %i entries" % count
 
    # request marshalling
    """
    def get_access_token(self):
        cookie = self.get_cookie()
        if cookie:
            token_cache = memcache.get("twitter_token_" + cookie['key'])
            if token_cache is not None:
                return token_cache
            else:
                #token = OAuthAccessToken.get_by_key_name(cookie['key'])
                token_query = OAuthAccessToken.all()
                token_query.filter('remember_key =', cookie['key'])
                token = token_query.get()
                if token is not None:
                    if not memcache.set("twitter_token_" + cookie['key'], token, 3600):
                        logging.error("Memcache set failed.")
                    
                    return token
                else:
                    return False
                
        else:
            return False
     """
 
    def get_data_from_signed_url(self, __url, __token=None, __meth='GET', **extra_params):
        return urlfetch(self.get_signed_url(
            __url, __token, __meth, **extra_params
            )).content
 
    def get_signed_url(self, __url, __token=None, __meth='GET',**extra_params):
        return '%s?%s'%(__url, self.get_signed_body(__url, __token, __meth, **extra_params))
 
    def get_signed_body(self, __url, __token=None, __meth='GET',**extra_params):
 
        service_info = self.service_info
 
        kwargs = {
            'oauth_consumer_key': service_info['consumer_key'],
            'oauth_signature_method': 'HMAC-SHA1',
            'oauth_version': '1.0',
            'oauth_timestamp': int(time()),
            'oauth_nonce': getrandbits(64),
            }
 
        kwargs.update(extra_params)
 
        if self.service_key is None:
            self.service_key = get_service_key(self.service)
 
        if __token is not None:
            kwargs['oauth_token'] = __token.oauth_token
            key = self.service_key + encode(__token.oauth_token_secret)
        else:
            key = self.service_key
 
        message = '&'.join(map(encode, [
            __meth.upper(), __url, '&'.join(
                '%s=%s' % (encode(k), encode(kwargs[k])) for k in sorted(kwargs)
                )
            ]))
 
        kwargs['oauth_signature'] = hmac(
            key, message, sha1
            ).digest().encode('base64')[:-1]
 
        return urlencode(kwargs)
 
    # who stole the cookie from the cookie jar?
 
    def get_cookie(self):
        import base64
        
        cookie = self.handler.request.cookies.get(
            'oauth.%s' % self.service, ''
            )
        if cookie == '':
            return False
        else:
            cookie = base64.b64decode(cookie)
            value = dict(var.split('=') for var in cookie.split('&'))
        
            return value
        
    def set_cookie(self, value, path='/'):
        import base64
        
        value_str = '&'.join('%s=%s' % (encode(k), encode(value[k])) for k in sorted(value))
        value_str = base64.b64encode(value_str)
        expires = datetime.now() + timedelta(+1) # exp 1 day
        self.handler.response.headers.add_header(
            'Set-Cookie',
            '%s=%s; path=%s; expires="%s"' %
            ('oauth.%s' % self.service, value_str, path, expires.strftime('%a, %d %b %Y %H:%M:%S %Z'))
            )
 
    def expire_cookie(self, path='/'):
        self.handler.response.headers.add_header(
            'Set-Cookie',
            '%s=; path=%s; expires="Fri, 31-Dec-1999 23:59:59 GMT"' %
            ('oauth.%s' % self.service, path)
            )
 
# ------------------------------------------------------------------------------
# oauth handler
# ------------------------------------------------------------------------------
 
class OAuthHandler(RequestHandler):
 
    def get(self, service, action=''):
 
        if service not in OAUTH_APP_SETTINGS:
            #return self.response.out.write(
            #    "Unknown OAuth Service Provider: %r" % service
            #  )
            self.redirect("/error?error=Unknown OAuth Service Provider: %r" % service)
            
        else:
            client = OAuthClient(service, self)
            
            try:
                if action in client.__public__:
                    self.response.out.write(getattr(client, action)())
                else:
                    self.response.out.write(client.login())
            except Exception, error:
                self.redirect('/error?error=%s' % error)
 
# ------------------------------------------------------------------------------
# self runner -- gae cached main() function
# ------------------------------------------------------------------------------
 
def main():
 
    application = WSGIApplication([
       ('/oauth/(.*)/(.*)', OAuthHandler),
       ], debug=True)
 
    CGIHandler().run(application)
 
if __name__ == '__main__':
    main()