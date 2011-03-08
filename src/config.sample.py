# -*- coding: utf-8 -*-

CSRF_SECRET_KEY = 'csrf_secret_key'

OAUTH_APP_SETTINGS = {
    'twitter': {
        'consumer_key': 'consumer_key',
        'consumer_secret': 'consumer_secret',
 
        'request_token_url': 'https://twitter.com/oauth/request_token',
        'access_token_url': 'https://twitter.com/oauth/access_token',
        'user_auth_url': 'https://twitter.com/oauth/authorize',
 
        'default_api_prefix': 'http://twitter.com',
        'default_api_suffix': '.json',
    },
}