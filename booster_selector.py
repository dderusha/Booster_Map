#!/usr/bin/env python

"""
Find and set local booster based on client IP address.

Searches booster_map.json to find boosters for client's subnet.
"""

import fileinput
import json
import logging
import subprocess
from os import path
from socket import create_connection, gaierror

try:
    import _winreg as wreg
    WIN = True
except ImportError:
    WIN = False

BASE_PATH = path.normpath('/usr/local/sbin/matw_scripts/booster_selector')
IP_FILE = path.join(BASE_PATH, 'local_ip.txt')
MAP_PATH = path.join(BASE_PATH, 'booster_map.json')
FWCLD_PLIST = '/usr/local/etc/fwcld.plist'

logging.basicConfig(filename='/var/log/booster_selector.log',
                    level=logging.DEBUG)


def get_ip():
    """Return local IP address."""
    server = 'filewave-admin.matw.matthewsintl.com'
    port = 20015
    try:
        filewave_socket = create_connection((server, port))
    except gaierror:
        return 'Unable to reach {} on port {}'.format(server, port)
    return filewave_socket.getsockname()[0]  # pylint: disable=no-member


def check_ip_change(current_ip):
    """Compare current_ip to ip stored in local_ip.txt."""
    for line in fileinput.input(IP_FILE, inplace=True):
        if current_ip in line:
            print line.rstrip()
            fileinput.close()
            return False

        line = str(current_ip)
        print line.rstrip()
        fileinput.close()
        return True


def get_map():
    """Get dict from booster_map.json."""
    # map_path = "booster_map.json"
    map_handle = open(MAP_PATH, "r")
    return json.loads(map_handle.read())


def select_booster(current_ip):
    """Return booster IP string for matching subnet."""
    booster_map = get_map()
    for location in booster_map:
        for subnet in booster_map[location]['subnets']:
            if current_ip.startswith(subnet):
                return booster_map[location]['boosters']


def clear_prefs():
    """Return a dict of unset booster prefs."""
    booster_prefs = {}
    for i in range(1, 6):
        booster_prefs['booster{}'.format(i)] = 'no.booster.set'
        booster_prefs['booster{}Port'.format(i)] = 0
        if i == 1:
            booster_prefs['booster{}PublishPort'.format(i)] = 0
    booster_prefs['boosterRouting'] = '<true/>'
    return booster_prefs


def configure_prefs(boosters):
    """Return a dict of booster prefs for the location."""
    booster_prefs = clear_prefs()
    i = 1
    try:
        for booster in boosters:
            booster_prefs['booster{}'.format(i)] = booster
            booster_prefs['booster{}Port'.format(i)] = 20013
            if i == 1:
                booster_prefs['booster{}PublishPort'.format(i)] = 20003
            i += 1
    except TypeError:
        logging.info('No mapped boosters')
    return booster_prefs


def edit_registry(booster_prefs):
    """Update registry keys with booster_prefs."""
    reg_key = wreg.OpenKey(wreg.HKEY_LOCAL_MACHINE,
                           r'Software\Wow6432Node\FileWave\WinClient',
                           0, wreg.KEY_ALL_ACCESS)
    for key, value in booster_prefs.iteritems():
        if 'P' not in key:
            wreg.SetValueEx(reg_key, key, 0, wreg.REG_SZ, value)
        else:
            wreg.SetValueEx(reg_key, key, 0, wreg.REG_DWORD, value)


def edit_plist(booster_prefs):
    """Update fwcld.plist with booster_prefs."""
    # for key, value in booster_prefs.iteritems():
    #     output = subprocess.check_output(['defaults', 'write',
    #                                       FWCLD_PLIST, key, value])
    #     logging.info(output)
    replace_next_value = False
    for key, value in booster_prefs.iteritems():
        for line in fileinput.input(FWCLD_PLIST, inplace=True):
            if not replace_next_value:
                if '<key>{}</key>'.format(key) in line:
                    replace_next_value = True
            else:
                if '<string>' in line:
                    line = '\t<string>{}</string>'.format(value)
                elif '<integer>' in line:
                    line = '\t<integer>{}</integer>'.format(value)
                elif '<false/>' in line:
                    line = '\t{}'.format(value)
                replace_next_value = False
            print line.rstrip()


def main():
    """Main."""
    logging.info('Checking current IP address')
    local_ip = get_ip()
    logging.info('Current IP address is:\n%s', local_ip)
    if check_ip_change(local_ip):
        booster_prefs = configure_prefs(select_booster(local_ip))
        if WIN:
            edit_registry(booster_prefs)
            subprocess.call(['net', 'stop', 'FileWave Client'])
            subprocess.Popen(['net', 'start', 'FileWave Client'])
        else:
            logging.info('Updating %s', FWCLD_PLIST)
            edit_plist(booster_prefs)
            logging.info('Restarting Client')
            output = subprocess.check_output(['/usr/local/bin/fwcontrol',
                                              'client', 'restart'])
            logging.info('Client restart status:\n%s', output)
    else:
        logging.info("IP hasn't changed. Exiting")


if __name__ == '__main__':
    main()
