#!/usr/bin/env python
from __future__ import print_function
import sys
import argparse
import requests
import json
import os.path
import time
import signal
import logging
import daemon
import pwd
from daemon import pidlockfile
from amzmgutil import config
from amzmgutil import functions
from lxml import etree
from getpass import getpass
from pprint import pprint
from datetime import tzinfo, timedelta, datetime

parser = argparse.ArgumentParser(description='amzmg: Amazon MP3 getter for Linux')
parser.add_argument('-c', '--config-file', help='Path to alternate configuration file (default ~/.amzmg)')
parser.add_argument('-d', '--daemonize', action='store_true', help='Become a daemon, periodically checking for new music')
parser.add_argument('-u', '--update-config', action='store_const', const=1, default=0,
                    help='Interactively update all saved configuration settings')
opts = parser.parse_args()

configuration = config.load_configuration(opts.config_file, opts.update_config)

logger = logging.getLogger("DaemonLog")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s: %(message)s")
handler = logging.FileHandler(configuration['logfile'])
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.warn("Amzmg starting up")

pollInterval = max(10, configuration['newFilePollSeconds'])

auth_form_url = """https://www.amazon.com/gp/dmusic/cloud/mp3/webapp"""
authn_endpoint = """https://www.amazon.com/ap/signin"""

session = requests.Session()
session.headers = {'User-Agent': "amzmg/0.8"}

response = session.get(auth_form_url)

if response.status_code == 200:
    dom = etree.HTML(response.content)
    inputs = dom.xpath("//form[@action='" + authn_endpoint + "']//input")
    postfields = {}
    for elem in inputs:
        postfields[elem.attrib.get('name')] = elem.attrib.get('value')

    if not ("email" in postfields and "password" in postfields):
        print("Amazon's login form not understood. Cannot log in.")
        logger.error("Amazon's login form not understood. Cannot log in.")
    else:
        authn_status = 0
        while authn_status != 302:
            if configuration.get('password', '') != '':
                postfields['email'] = configuration['username']
                postfields['password'] = configuration['password']
            else:
                if sys.stdout.isatty() and sys.stdin.isatty():
                    postfields['email'] = config.prompt("Username", configuration['username'])
                    postfields['password'] = getpass("Password: ")
                else:
                    print ('Cannot start: not attached to a tty and unattended startup is not configured.', file=sys.stderr)
                    logger.error('Cannot start: not attached to a tty and unattended startup is not configured.')
                    exit(1)

            authn_response = session.post(authn_endpoint, data=postfields, allow_redirects=False)
            authn_status = authn_response.status_code
            if authn_status != 302:
                if (configuration.get('password', '') != ''):
                    print('Authentication failed; supply new credentials with amzmg -u', file=sys.stderr)
                    logger.warn("Authentication to amazon failed; supply new credentials with amzmg -u")
                    sys.exit(1)
                else:
                    print("Authentication failed, try again")
                    logger.warn("Authentication to amazon failed; prompting for credentials again.")

            app_data_response = session.get('https://www.amazon.com/gp/dmusic/mp3/player?ie=UTF8&ref_=dm_cp_m_redirect',
                                            headers={
                                            'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; Touch; rv:11.0) like Gecko'})
            dom = etree.HTML(app_data_response.content)
            scripts = dom.xpath("//script[not(@src)]")
            app_data = None
            for elem in scripts:
                script_code = elem.text
                config_pos = script_code.find('amznMusic.appConfig =')
                if config_pos != -1:
                    # print(script_code)
                    jparser = json.JSONDecoder()
                    app_data = jparser.raw_decode(script_code[config_pos + 22:])
                    app_data = app_data[0]

            if app_data is None:
                print("Failed to mine amznMusic.appConfig", file=sys.stderr)
                logger.error("Failed to mine amznMusic.appConfig")
                sys.exit(1)


            logger.info("Startup good, polling for new purchases every %d seconds." % pollInterval)
            if opts.daemonize:
                dcontext = daemon.DaemonContext()
                dcontext.files_preserve=[handler.stream]
                dcontext.umask = configuration['umask']
                pidfile = configuration['daemonPidfile'].replace('{username}', pwd.getpwuid(os.geteuid()).pw_name)
                dcontext.pidfile = pidlockfile.TimeoutPIDLockFile(pidfile)
                logger.info("Daemonizing...")

                try:
                    with dcontext:
                        functions.main_dl_loop(configuration, app_data, opts, session, pollInterval, logger)
                except pidlockfile.LockFailed as ex:
                    # good chance we're detached from a tty at this point, but maybe print to stderr too anyway?
                    logger.error("Could not acquire pidfile lock: " + ex.message)
                    logger.error("Check that you have permission to create and write to the pidfile, and that another instance is not already running.")
                    sys.exit(1)
                except Exception as ex:
                    logger.error("Fatal error: " + ex.message)
                    sys.exit(1)
            else:
                functions.main_dl_loop(configuration, app_data, opts, session, pollInterval, logger)

else:
    print("%s: GET response not 200" % auth_form_url)


