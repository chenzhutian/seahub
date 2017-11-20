import logging
from threading import Thread, Event

from .ldap_settings import Settings

class LdapSyncer(object):
    def __init__(self):
        self.settings = Settings()

    def enable_sync(self):
        return self.settings.enable_sync()

    def start(self):
        LdapSyncTimer(self.settings).start()

class LdapSyncTimer(Thread):
    def __init__(self, settings):
        Thread.__init__(self)
        self.settings = settings
        self.fininsh = Event()

    def run(self):
        from .run_ldap_sync import run_ldap_sync
        while not self.fininsh.is_set():
            self.fininsh.wait(self.settings.sync_interval*60)
            if not self.fininsh.is_set():
               run_ldap_sync(self.settings)

    def cancel(self):
        self.fininsh.set()

ldap_syncer = None
if not ldap_syncer:
    print 'ready to begin ldap syncer'
    ldap_syncer = LdapSyncer()
    ldap_syncer.start()
print 'ldap syncer running'