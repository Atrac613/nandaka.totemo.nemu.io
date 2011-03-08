# -*- coding: utf-8 -*-

import hashlib
import re

from config import CSRF_SECRET_KEY

class CSRFFilter(object):
    def __init__(self, handler, google_id):
        self.handler = handler
        self.google_id = google_id
        
    def insertCSRFToken(self, html):
        if self.google_id.user_id() is not None:
            csrf_token = hashlib.sha256(self.google_id.user_id() + CSRF_SECRET_KEY).hexdigest()
            form = re.compile(r'(<form\W[^>]*\bmethod=(\'|"|)POST(\'|"|)\b[^>]*>)', re.IGNORECASE)
            # Modify any POST forms
            extra_field = "<input type='hidden' name='_csrf_token' value='" + \
                csrf_token + "' />"
            return form.sub('\\1' + extra_field, html)
        
    def checkCSRFToken(self):
        if self.google_id.user_id() is not None:
            _csrf_token = self.handler.request.get('_csrf_token')
            csrf_token = hashlib.sha256(self.google_id.user_id() + CSRF_SECRET_KEY).hexdigest()
            if _csrf_token != csrf_token:
                return False
            else:
                return True
            
    def redirectCSRFWarning(self):
        return self.handler.redirect('/error?error=csrf')