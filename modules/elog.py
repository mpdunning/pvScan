#!/usr/bin/env python
# elog module

from __future__ import print_function
import argparse
import json
import logging
import os
import requests
import sys
from time import sleep
from epics import PV, ca, caget, caput

##################################################################################################################

def loggingConfig():
    """Configure logging."""
    logLevel = logging.WARNING
    logging.basicConfig(format='%(levelname)s [%(asctime)s]: %(message)s', datefmt='%I:%M:%S', level=logLevel)


class Elog():
    """Post an elog..."""
    def __init__(self, expname, user, password, url):
#    def __init__(self, expname, user, password, url, message):
        self.className = self.__class__.__name__
        functionName = '__init__'
        logging.info('%s.%s' % (self.className, functionName))
        self._expname = expname
        self._user = user
        self._password = password
        self._url = url
#        self._message = message
#        self._payload = {
#            #'run_num': args.run_num,
#            'log_text': args.message
#        }
        self._serverURLPrefix = "{0}run_control/{1}/ws/".format(self._url
                + "/" if not self._url.endswith("/") else self._url, self._expname)

    def start(self):
        """Start run..."""
        functionName = 'start'
        resp = requests.post(self._serverURLPrefix + "start_run",
                auth=requests.auth.HTTPBasicAuth(self._user, self._password))
#        resp = requests.post(self._serverURLPrefix + "start_run", data=self._payload,
#                auth=requests.auth.HTTPBasicAuth(self._user, self._password))
#        print(resp.text)
        sleep(0.5)
        if resp.status_code != requests.codes.ok:
            logging.warning('{0}.{1}: Failed to start elog entry, response={2}'
                    .format(self.className, functionName, resp))

    def _set_params(self):
        """Set run params..."""
        functionName = '_set_params'
        pvdata = {}
        for name in self._pvnamelist:
            pv = PV(name)
            pvdata[pv.pvname] = pv.get(as_string=True)
        return pvdata

    def _set_params2(self):
        """Set run params..."""
        functionName = '_set_params'
        pvdata = {}
        for name in self._pvnamelist:
            chid = ca.create_channel(name, connect=False, auto_cb=False) # note 1
            pvdata[name] = [chid, None]
        for name, data in pvdata.items():
            ca.connect_channel(data[0])
        ca.poll()
        for name, data in pvdata.items():
            ca.get(data[0], wait=False)  # note 2
        ca.poll()
        for name, data in pvdata.items():
            val = ca.get_complete(data[0])
            pvdata[name][1] = val
        #return { name: data[1] for name, data in pvdata.items()}
        ret = dict((name, data[1]) for name, data in pvdata.items())
        print(ret)
        return ret

    def add_params(self, pvnamelist=None):
        """Add run params..."""
        functionName = 'add_params'
        if pvnamelist is None: pvnamelist = []
        self._pvnamelist = pvnamelist
        resp = requests.post(self._serverURLPrefix + "add_run_params", json=self._set_params(), 
                auth=requests.auth.HTTPBasicAuth(self._user, self._password))
        sleep(0.5)
        if resp.status_code != requests.codes.ok:
            logging.warning('{0}.{1}: Failed to add elog params, response={2}'
                    .format(self.className, functionName, resp))

    def end(self):
        """End run..."""
        functionName = 'end'
        resp = requests.post(self._serverURLPrefix + "end_run", 
                auth=requests.auth.HTTPBasicAuth(self._user, self._password))
        if resp.status_code != requests.codes.ok:
            logging.warning('{0}.{1}: Failed to end elog entry, response={2}'
                    .format(self.className, functionName, resp))



#--- Self-test code -------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
#    parser.add_argument("message", help="Log message")
    requiredNamed = parser.add_argument_group('Required named arguments')
    requiredNamed.add_argument("--experiment", help="The name of the experiment", required=True)
    requiredNamed.add_argument("--user", help="The operator userid", required=True)
    requiredNamed.add_argument("--password", help="The operator password", required=True)
    parser.add_argument("--url", help="URL to post to; this is only the prefix. \
            For example, https://testfac-lgbk.slac.stanford.edu/testfac_operator/",
            default="https://testfac-lgbk.slac.stanford.edu/testfac_operator/")
    args = parser.parse_args()

    pvlist = ['GUN:AS01:1:3:S_PA', 'KLYS:AS01:K1:1:WACTUAL', 'KLYS:AS01:K1:3:WACTUAL', 'ASTA:PV04:SCAN:ID']
    elog = Elog(args.experiment, args.user, args.password, args.url)
#    elog = Elog(args.experiment, args.user, args.password, args.url, args.message)
    print('Creating elog entry...')
    elog.start()
    elog.add_params(pvnamelist=pvlist)
    elog.end()
    
    sys.exit(0)
    

##################################################################################################################
        


