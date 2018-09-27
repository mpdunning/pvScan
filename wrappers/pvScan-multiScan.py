#!/usr/bin/env python

from __future__ import print_function
import datetime
import os
import subprocess
import sys
from time import sleep
from epics import PV, caput
import argparse
import getpass
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/prod/modules/')
from elog import Elog


# Command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('pv_prefix', help='PV prefix of the DAQ IOC, e.g. ASTA:PV01')
parser.add_argument('n_scans', nargs='?', default=0, help="Number of scans per run")
args = parser.parse_args()
#
pv_prefix = args.pv_prefix
try:
    n_scans = int(args.n_scans)
except ValueError as e:
    print(e)
    print('--> Setting n_scans to 1')
    n_scans = 1

# Global timestamps
NOW = datetime.datetime.now().strftime('%Y%m%d_%H%M')
TODAY = datetime.datetime.now().strftime('%Y%m%d')

## Get/Set some PVs
msgPv = PV(pv_prefix + ':MSG')
msgPv.put('Initializing run...')
print('Initializing run...')
DEBUG = PV(pv_prefix + ':WDEBUG:ENABLE').get()
script_pv = PV(pv_prefix + ':SCRIPT')
script = script_pv.get(as_string=True)
filepath_autoset = PV(pv_prefix + ':DATA:FILEPATH:AUTOSET').get()
filepath_pv = PV(pv_prefix + ':DATA:FILEPATH')
n_scans_pv = PV(pv_prefix + ':N_SCANS')
scan_count_pv = PV(pv_prefix + ':SCAN:COUNT')
scan_count_pv.put(0)
run_pv = PV(pv_prefix + ':RUNFLAG')
expname = PV(pv_prefix + ':EXP:NAME').get(as_string=True)
sample_name = PV(pv_prefix + ':SCAN:SAMPLE_NAME').get(as_string=True)
scantype = PV(pv_prefix + ':SCAN:TYPE').get(as_string=True)
scan_id_pv = PV(pv_prefix + ':SCAN:ID')
run_id_pv = PV(pv_prefix + ':RUN:ID')
run_id = '{0}_{1}'.format(sample_name, NOW)
run_id_pv.put(run_id)
elogFlag = PV(pv_prefix + ':ELOG:ENABLE').get()


# Validate n_scans
if not n_scans:
    n_scans = n_scans_pv.get()
if n_scans is None:
    print('*** Warning: n_scans was None, setting to 1 ***')
    n_scans = 1

# Set filepath
if filepath_autoset:
    default_filepath = '/data/data/'
    if os.path.exists(default_filepath):
        root_filepath = default_filepath
    elif os.environ['NFSHOME']:
        root_filepath = os.environ['NFSHOME']
        print('Filepath {0} does not exist, defaulting to NFS...'.format(default_filepath))
    else:
        root_filepath = '~'
    filepath = ('{0}{1}/{2}/{3}/{4}/'.format(root_filepath, sample_name, TODAY, scantype, NOW))
    PV(pv_prefix + ':DATA:FILEPATH').put(filepath)  # Write filepath to PV
else:
    filepath = PV(pv_prefix + ':DATA:FILEPATH').get(as_string=True)

# Configure elog
if elogFlag:
    username = getpass.getuser()
    elog = Elog(expname, username, password='testfac',
            url='https://testfac-lgbk.slac.stanford.edu/testfac_operator/')
    pvfile = os.environ['NFSHOME'] + '/pvScan/elog/elog_pvlist-' + pv_prefix.replace(':','_')
    if os.path.isfile(pvfile):
        with open(pvfile, 'r') as f:
            pvlist = [line.strip() for line in f if not line.startswith('#')]
            pvlist = [line for line in pvlist if line]
    else:
        pvlist = []

if DEBUG:
    print('+++++ DEBUG info +++++')
    print('pv_prefix: ', pv_prefix)
    print('script: ', script)
    print('filepath: ', filepath)
    print('n_scans: ', n_scans)
    print('expname: {0}'.format(expname))
    print('sample_name: {0}'.format(sample_name))
    print('run ID: {0}'.format(run_id))
    if elogFlag:
        print('username: {0}'.format(username))
    print('++++++++++++++++++++++')


# Start Scan
run_pv.put(1)
if elogFlag:
    # Start elog entry
    print('Creating elog entry...')
    try:
        elog.start()
    except requests.exceptions.RequestException as e:
        print(e)
        print('--> Failed to start elog...continuing scan')
    else:
        elogSuccess = True
        try:
            elog.add_params(pvnamelist=pvlist if pvlist else [])
        except requests.exceptions.RequestException as e:
            print(e)
            print('--> Failed to add elog parameters...continuing scan')
sleep(0.2)
if n_scans == 1:
    scan_count_pv.put(1)
    scan_id_pv.put('{0}_{1}_{2:03}'.format(sample_name, NOW, 1))
    subprocess.call([script, pv_prefix])
    run_pv.put(0)
elif n_scans > 1:
    try:
        for i in range(n_scans): 
            if run_pv.get():
                print('{0} Scan {1:03}/{2:03} {3}'.format('*'*15, i+1, n_scans, '*'*15))
                if filepath.endswith('/'):
                    filepath_new = filepath.rstrip('/')
                else:
                    filepath_new = filepath
                filepath_new += '/scan%03d' % (i+1)
                if DEBUG: print('filepath_new:', filepath_new)
                filepath_pv.put(filepath_new + '\0')
                scan_count_pv.put(i+1)
                scan_id_pv.put('{0}_{1}_{2:03}'.format(expname, NOW, i+1))
                sleep(0.5)
                subprocess.call([script, pv_prefix])
                print('')
    finally:
        filepath_pv.put(filepath + '\0')
        run_pv.put(0)
        sleep(0.2)
    print('*'*15 + ' All scans done. ' + '*'*15)
else:
    raise ValueError('Error: n_scans must be > 0')
if elogFlag and elogSuccess:
    # End elog entry
    try:
        elog.end()
    except requests.exceptions.RequestException as e:
        print(e)
        print('--> Failed to end elog')
sys.exit(0)


