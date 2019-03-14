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

#################################################################################################################

class Elog():
    """Post an elog..."""
    def __init__(self, expname, user, password, url, samplename=None):
        self.className = self.__class__.__name__
        functionName = '__init__'
        logging.debug('%s.%s' % (self.className, functionName))
        self._user = user
        self._password = password
        self._url = url + '/' if not url.endswith('/') else url
        if expname is None:
            expname, samplename = self._get_exp_info()
        self.expname = expname
        self.samplename = samplename
        self._serverURLPrefix = '{0}run_control/{1}/ws/'.format(self._url, self.expname)

    def _get_exp_info(self):
        functionName = '_get_exp_info'
        resp = requests.get('{0}lgbk/ws/activeexperiments'.format(self._url), 
                auth=requests.auth.HTTPBasicAuth(self._user, self._password))
        if resp.status_code != requests.codes.ok:
            logging.warning('{0}.{1}: Failed to get experiment name, response={2}'
                    .format(self.className, functionName, resp))
            return ('TestExp0', 'TestSample')
        exp_name = resp.json()['value'][0]['name']
        sample_name = resp.json()['value'][0]['current_sample']
        return (exp_name, sample_name)

    def start(self):
        """Start run..."""
        functionName = 'start'
        resp = requests.post(self._serverURLPrefix + "start_run",
                auth=requests.auth.HTTPBasicAuth(self._user, self._password))
        sleep(0.5)
        if resp.status_code != requests.codes.ok:
            logging.warning('{0}.{1}: Failed to start elog entry, response={2}'
                    .format(self.className, functionName, resp))
            return False
        else:
            return True

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
    requiredNamed = parser.add_argument_group('Required named arguments')
    requiredNamed.add_argument("--user", help="The operator userid", required=True)
    requiredNamed.add_argument("--password", help="The operator password", required=True)
    parser.add_argument("--experiment", help="The name of the experiment")
    parser.add_argument("--url", help="URL to post to; this is only the prefix. \
            For example, https://testfac-lgbk.slac.stanford.edu/testfac_operator/",
            default="https://testfac-lgbk.slac.stanford.edu/testfac_operator/")
    args = parser.parse_args()

    #pvlist = ['GUN:AS01:1:3:S_PA', 'KLYS:AS01:K1:1:WACTUAL', 'KLYS:AS01:K1:3:WACTUAL', 'ASTA:PV04:SCAN:ID']
    pvlist = ['ASTA:AO:BK05:V0079', 'ASTA:AO:BK05:V0080']
    elog = Elog(args.experiment, args.user, args.password, args.url)
    print('Creating elog entry...')
    try:
        elog.start()
        elog.add_params(pvnamelist=pvlist)
        print('Experiment name: {0}, Sample name: {1}'.format(elog.expname, elog.samplename))
    finally:
        elog.end()
    
    sys.exit(0)
    

##################################################################################################################
        


