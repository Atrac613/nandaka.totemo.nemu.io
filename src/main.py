# -*- coding: utf-8 -*-

import os
import logging
import datetime

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import memcache
from google.appengine.api.labs import taskqueue
from google.appengine.runtime import apiproxy_errors
            
from twitter_oauth_handler import OAuthClient

from nemuio_db import OAuthAccessToken
from nemuio_db import UserPrefs
from nemuio_db import SearchKeywords
from nemuio_db import SearchCache

#MainPage
class MainPage(webapp.RequestHandler):
    def get(self):
            
        template_values = {
            }
        
        path = os.path.join(os.path.dirname(__file__), 'templates/index.html')
        self.response.out.write(template.render(path, template_values))

#HomePage
class HomePage(webapp.RequestHandler):
    def get(self):
        
        user = users.get_current_user()
        nickname = user.nickname()
        logout_url = users.create_logout_url('/')
        
        template_values = {
            'nickname' : nickname,
            'logout_url' : logout_url
            }
        
        path = os.path.join(os.path.dirname(__file__), 'templates/home.html')
        self.response.out.write(template.render(path, template_values))

#Config Page
class ConfigPage(webapp.RequestHandler):
    def get(self):
        from csrffilter import CSRFFilter
        
        user = users.get_current_user()
        
        user_prefs_query = UserPrefs.all()
        user_prefs_query.filter("google_id =", user)
        user_prefs = user_prefs_query.get()
        
        mode = self.request.get('mode')
        
        if mode == 'add_twitter_account':
            self.redirect('/oauth/twitter/login')
            
        elif mode == 'delete_twitter_account':
            if user_prefs.oauth_access_token_key:
                oauth_access_token_query = OAuthAccessToken.get_by_key_name(user_prefs.oauth_access_token_key.key().name())
                oauth_access_token_query.delete()
                user_prefs.oauth_access_token_key = None
                user_prefs.put()
        
        keywords = []    
        if user_prefs is not None:
            search_keywords_query = SearchKeywords.all()
            search_keywords_query.filter('user_id =', user_prefs.key())
            search_keywords = search_keywords_query.fetch(30)
            
            for search_keyword in search_keywords:
                keywords.append({'id': search_keyword.key().id(), 'keyword': search_keyword.keyword})
                    
        template_values = {
            'nickname' : user.nickname(),
            'user_prefs': user_prefs,
            'keywords': keywords
            }
        
        path = os.path.join(os.path.dirname(__file__), 'templates/config.html')
        html = template.render(path, template_values)
        self.response.out.write(CSRFFilter(self, user).insertCSRFToken(html))
            
    def post(self):
        from csrffilter import CSRFFilter
        
        user = users.get_current_user()
        mode = self.request.get('mode')

        #CSRF Protection
        filter = CSRFFilter(self, user)
        if not filter.checkCSRFToken():
            return filter.redirectCSRFWarning()

        user_prefs_query = UserPrefs.all()
        user_prefs_query.filter("google_id =", user)
        user_prefs = user_prefs_query.get()
        
        if user_prefs is not None:
            logging.info('Mode: %s' % mode)
            if mode == 'add':
                keyword = self.request.get('keyword')
                search_keywords = SearchKeywords()
                search_keywords.user_id = user_prefs.key()
                search_keywords.keyword = keyword
                search_keywords.put()
                
            elif mode == 'delete':
                deletes = self.request.get_all('deletes[]')
                for delete in deletes:
                    search_keywords = SearchKeywords.get_by_id(int(delete))
                    logging.info('Delete keyword: %s' % search_keywords.keyword)
                    if search_keywords is not None:
                        if search_keywords.user_id.key() == user_prefs.key():
                            search_keywords.delete()
        
        self.redirect('/config')
        
class AddTaskCron(webapp.RequestHandler):
    def get(self):
        search_keywords_query = SearchKeywords().all()
        search_keywords = search_keywords_query.fetch(30)
        for search_keyword in search_keywords:
            try:
                logging.info('Add taskqueue. keyword: %s' % search_keyword.keyword)
                taskqueue.add(url='/feed', method='GET', params={'keyword_id' : search_keyword.key().id()})
            except (taskqueue.Error, apiproxy_errors.Error):
                logging.exception('Failed to add taskqueue.')

class DeleteOldCacheCron(webapp.RequestHandler):
    def get(self):
        date = datetime.datetime.now() - datetime.timedelta(days=1)
        search_cache_query = SearchCache().all()
        search_cache_query.filter('tweeted_at <', date)
        search_cache_query.order('tweeted_at')
        search_cache = search_cache_query.fetch(100)
        
        logging.info('Delete old cache. count: %d' % len(search_cache))
        
        for cache in search_cache:
            cache.delete()
        
class FeedPage(webapp.RequestHandler):
    def get(self):
        keyword_id = self.request.get('keyword_id')
        
        search_keywords = SearchKeywords.get_by_id(int(keyword_id))
        if search_keywords is not None:
            logging.info('Feed: %s' % search_keywords.keyword)
            
            user_prefs = UserPrefs().get_by_id(search_keywords.user_id.key().id())
            if user_prefs is not None:
                logging.info('Keyword owner name: %s' % user_prefs.google_id.nickname())
                if user_prefs.oauth_access_token_key is not None:
                    oauth_access_token = OAuthAccessToken.get_by_key_name(user_prefs.oauth_access_token_key.key().name())
                    if oauth_access_token is not None:
                        logging.info('Twitter Account: %s' % user_prefs.oauth_access_token_key.specifier)
                        try:
                            client = OAuthClient('twitter', self)
                            client.token = oauth_access_token
                            results = client.get('/search', q=search_keywords.keyword.encode('utf-8'))
                            for tweet_id in results['statuses']:
                                search_cache_query = SearchCache().all()
                                search_cache_query.filter('tweet_id =', tweet_id)
                                search_cache_query.filter('keyword_key =', search_keywords.key())
                                if search_cache_query.get() is None:
                                    tweet = client.get('/statuses/show/%d' % tweet_id)
                                    logging.info('Tweet: (%s) %s' % (tweet['user']['name'], tweet['text']))
                                    logging.info(tweet['created_at'])
                                    search_cache = SearchCache()
                                    search_cache.tweet_id = tweet_id
                                    search_cache.keyword_key = search_keywords.key()
                                    search_cache.name = tweet['user']['name']
                                    search_cache.screen_name = tweet['user']['screen_name']
                                    search_cache.profile_image_url = tweet['user']['profile_image_url']
                                    search_cache.text = tweet['text']
                                    search_cache.tweeted_at = datetime.datetime.strptime(tweet['created_at'], "%a %b %d %H:%M:%S +0000 %Y")
                                    search_cache.put()
                                else:
                                    logging.info('Skip. tweet_id: %d' % tweet_id)
                                
                        except Exception, error:
                            logging.error('Cache Failed: %s' % error)
            
        else:
            logging.error('keyword_id is invalid.')

class GetTweetAPI(webapp.RequestHandler):
    def get(self):
        import random
        from django.utils import simplejson
        
        cache_ids = memcache.get('cache_ids')
        if cache_ids is None:
            search_cache_query = SearchCache().all()
            search_cache_query.order('-tweeted_at')
            search_cache = search_cache_query.fetch(200)
            
            cache_ids = []
            for tweet in search_cache:
                cache_ids.append(tweet.key().id())
            
            memcache.Client().add('cache_ids', cache_ids, 60)
            logging.info('cache_ids from datastore.')
        else:
            logging.info('cache_ids from memcache.')
        
        if len(cache_ids) > 0:
            cache_id = cache_ids[random.randint(0, len(cache_ids))]
            logging.info('Random cache_id: %d' % cache_id)
            
            data = memcache.get('cache_%d' % cache_id)
            if data is None:
                logging.info('Tweet cache from datastore.')
                search_cache = SearchCache().get_by_id(int(cache_id))
                if search_cache is not None:
                    delta = datetime.datetime.now() - search_cache.tweeted_at
                    if delta.seconds < 120:
                        delta_str = int(delta.seconds)
                    else:
                        delta_str = '-'
                        
                    if len(search_cache.text) < 60:
                        data = {'id': search_cache.key().id(),
                                'name': search_cache.name,
                                'screen_name': search_cache.screen_name,
                                'text': search_cache.text,
                                'profile_image_url': search_cache.profile_image_url,
                                'delta':delta_str,
                                'created_at': search_cache.tweeted_at.strftime('%a %b %d %H:%M:%S +0000 %Y')}
                        
                        memcache.Client().add('cache_%d' % cache_id, data, 3600)
                        
                        json = simplejson.dumps(data, ensure_ascii=False)
                        self.response.content_type = 'application/json'
                        self.response.out.write(json)
            else:
                logging.info('Tweet cache from memcache.')
                json = simplejson.dumps(data, ensure_ascii=False)
                self.response.content_type = 'application/json'
                self.response.out.write(json)
                

#Logout Page
class LogoutPage(webapp.RequestHandler):
    def get(self):
        logout_url = users.create_logout_url('/')
        
        self.redirect(logout_url)

#Error Page
class ErrorPage(webapp.RequestHandler):
    def get(self):
        from stripper import Stripper
        
        stripper = Stripper()
        
        error = stripper.strip(self.request.get('error'))

        template_values = {
            'error': error
            }
            
        if error == 'csrf':
            template_path = 'templates/error_csrf.html'
        else:
            template_path = 'templates/error.html'
            
        path = os.path.join(os.path.dirname(__file__), template_path)
        self.response.out.write(template.render(path, template_values))
    
application = webapp.WSGIApplication(
                                     [('/', MainPage),
                                      ('/home', HomePage),
                                      ('/config', ConfigPage),
                                      ('/logout', LogoutPage),
                                      ('/api/get_tweet', GetTweetAPI),
                                      ('/feed', FeedPage),
                                      ('/cron/add', AddTaskCron),
                                      ('/cron/delete', DeleteOldCacheCron),
                                      ('/error', ErrorPage)],
                                     debug=False)

def main():
    run_wsgi_app(application)
    
if __name__ == "__main__":
    main()
