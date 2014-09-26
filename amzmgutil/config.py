from __future__ import print_function
import sys
import os
import os.path
import stat
import json
import re
from datetime import tzinfo, timedelta, datetime
from getpass import getpass


def load_configuration(file_path, force_update):
    if (file_path == None):
        file_path = os.path.expanduser('~') + '/.amzmg'

    if (not os.path.exists(file_path)):
        print("No config file found at {}\nSetting up a new configuration...\n".format(file_path))
        defaultConfig = default_config_prompts()
        save_configuration(file_path, defaultConfig)
        return defaultConfig
    else:
        with open(file_path, 'r') as h_cfg:
            try:
                config = json.loads(h_cfg.read())
            except ValueError as e:
                print("Syntax error in configuraiton file:\n{}\n".format(e), file=sys.stderr)
                nowWhat = prompt("Retry loading configuration, or start over with a new one? (retry/new)", 'retry',
                                 r'^(retry|new)$')
                if (nowWhat == "new"):
                    os.unlink(file_path)
                return load_configuration(file_path)

    if (force_update):
        config = default_config_prompts(config)
        save_configuration(file_path, config)
        return config

    requiredKeys = ['username', 'download_root', 'lastDownloadedPurchase', 'newFilePollSeconds']
    haveKeys = config.keys()
    if len(set(requiredKeys) - set(haveKeys)) > 0:
        print("Saved configuration is incomplete; re-running setup")
        config = default_config_prompts(config)
        save_configuration(file_path, config)

    return config


def save_configuration(file_path, configuration):
    if (file_path == None):
        file_path = os.path.expanduser('~') + '/.amzmg'

    touch = open(file_path, 'w')
    touch.close()
    os.chmod(file_path, stat.S_IRUSR | stat.S_IWUSR)

    with open(file_path, 'w') as h_cfg:
        h_cfg.write(json.dumps(configuration, sort_keys=True, indent=4, separators=(',', ': ')))


def default_config_prompts(config={}):
    config['username'] = prompt("Email address you use to log on to amazon", config.get('username'))

    print("\nWould you like to enable unattended startup?")
    print("With unattended startup, your amazon account password will be saved in plain text in the configuration")
    print("file, but amzmg can be launched automatically, ie at system startup.")
    choice = prompt('Enable unattended startup (y/n)?', 'y', r'^[YyNn]$')
    if (choice.lower() == 'y'):
        config['password'] = getpass('Password you use to log on to amazon: ')
    else:
        config.pop('password', '')

    config['download_root'] = prompt("Directory to download files into", config.get('download_root'))
    while (not os.path.isdir(config[
        'download_root'])):  # might be nice to check writable directory too, but os.access not in older pythons, too much trouble
        print("{}: not a directory".format(config['download_root']))
        config['download_root'] = prompt("Directory to download files into")

    print("\nHow many days of previous purchases should amzmg initially download?")
    print("0 will result in no past purchases being downloaded; amzmg will start with the")
    print("next purchase you make.")
    days = int(prompt("Days?", 0, r'^[0-9]+$'))
    dt = datetime.utcnow()
    dt = dt - timedelta(days=days)
    config['lastDownloadedPurchase'] = dt.isoformat() + "Z"

    config['newFilePollSeconds'] = 120

    return config


def prompt(msg, default=None, pattern=None):
    if (not default == None):
        msg = msg + " [{}]".format(default)
    match = 0
    while not match:
        inval = raw_input(msg + ": ")
        if (inval == "" and not default == None):
            inval = str(default)

        if pattern:
            match = re.match(pattern, inval)
        else:
            match = 1

    if (inval == ""):
        if (default == None):
            return prompt(msg, default, pattern)
        else:
            return default
    else:
        return inval
