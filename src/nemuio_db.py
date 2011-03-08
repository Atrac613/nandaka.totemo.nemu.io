# -*- coding: utf-8 -*-

# ------------------------------------------------------------------------------
# db entities
# ------------------------------------------------------------------------------

from google.appengine.ext import db

class OAuthAccessToken(db.Model):
    service = db.StringProperty()
    specifier = db.StringProperty()
    oauth_token = db.StringProperty()
    oauth_token_secret = db.StringProperty()
    created_at = db.DateTimeProperty(auto_now_add=True)
    updated_at = db.DateTimeProperty(auto_now_add=True)
    
class OAuthRequestToken(db.Model):
    service = db.StringProperty()
    oauth_token = db.StringProperty()
    oauth_token_secret = db.StringProperty()
    created_at = db.DateTimeProperty(auto_now_add=True)
    
class OAuthStatusCodes(db.Model):
    method = db.StringProperty()
    api_method = db.StringProperty()
    tweet = db.StringProperty()
    status_code = db.IntegerProperty()
    extra_params = db.TextProperty()
    oauth_access_token_key = db.ReferenceProperty(OAuthAccessToken)
    created_at = db.DateTimeProperty(auto_now_add=True)
    
class UserPrefs(db.Model):
    google_id = db.UserProperty()
    oauth_access_token_key = db.ReferenceProperty(OAuthAccessToken)
    created_at = db.DateTimeProperty(auto_now_add=True)
    updated_at = db.DateTimeProperty(auto_now_add=True)
    
class SearchKeywords(db.Model):
    user_id = db.ReferenceProperty(UserPrefs)
    keyword = db.StringProperty()
    created_at = db.DateTimeProperty(auto_now_add=True)
    updated_at = db.DateTimeProperty(auto_now_add=True)
    
class SearchCache(db.Model):
    keyword_key = db.ReferenceProperty(SearchKeywords)
    tweet_id = db.IntegerProperty()
    screen_name = db.StringProperty()
    name = db.StringProperty()
    text = db.TextProperty()
    profile_image_url = db.StringProperty()
    tweeted_at = db.DateTimeProperty(auto_now_add=True)
    created_at = db.DateTimeProperty(auto_now_add=True)
    updated_at = db.DateTimeProperty(auto_now_add=True)
    