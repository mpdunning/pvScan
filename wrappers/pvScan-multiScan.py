#!/usr/bin/env python

from __future__ import print_function
import subprocess
import sys
from time import sleep
from epics import PV, caput
import getpass
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/prod/modules/')
from elog import Elog

DEBUG = 0

args='PV_PREFIX'

def show_usage():
    "Prints usage"
    print('Usage: %s %s' % (sys.argv[0], args))

if len(sys.argv) < 2:
    show_usage()
    sys.exit(1)

pv_prefix = sys.argv[1]

script_pvname = pv_prefix + ':SCRIPT'
script_pv = PV(script_pvname)
script = script_pv.get(as_string=True)

filepath_pvname = pv_prefix + ':DATA:FILEPATH'
filepath_pv = PV(filepath_pvname)
filepath = filepath_pv.get(as_string=True)

n_runs_pvname = pv_prefix + ':NRUNS'
n_runs_pv = PV(n_runs_pvname)

run_pvname = pv_prefix + ':RUNFLAG'
run_pv = PV(run_pvname)

if len(sys.argv) == 3:
    n_runs = int(sys.argv[2])
else:
    n_runs = n_runs_pv.get()

if n_runs is None:
    print('*** Warning: N Runs was None, setting to 1 ***')
    n_runs = 1

if DEBUG:
    print('pv_prefix: ', pv_prefix)
    print('script: ', script)
    print('filepath: ', filepath)
    print('n_runs: ', n_runs)

elogFlag = PV(pv_prefix + ':ELOG:ENABLE').get()
if elogFlag:
    expname = PV(pv_prefix + ':SCAN:SAMPLE_NAME').get(as_string=True)
    username = getpass.getuser()
    elog = Elog(expname, username, password='testfac',
            url='https://testfac-lgbk.slac.stanford.edu/testfac_operator/')
    pvlist = ['ASTA:PV04:DATE', 'ASTA:PV04:TIME', 'ASTA:PV04:SCAN:TYPE', 'ASTA:PV04:SCANPV1:PVNAME',
              'GUN:AS01:1:ADES', 'MOTR:AS01:MC01:CH1:MOTOR', 'MOTR:AS01:MC03:CH7:MOTOR',
              'MOTR:AS01:MC03:CH8:MOTOR', 'MOTR:AS01:MC02:CH3:MOTOR', 'MOTR:AS01:MC02:CH5:MOTOR',
              'MOTR:AS01:MC02:CH6:MOTOR', 'MOTR:AS01:MC02:CH4:MOTOR.DESC', 'ASTA:AI:3314-3C-9:CH1',
              'ASTA:AI:3314-1C-9:CH4', 'ASTA:CALC:3162-9:CH1', 'VGXX:AS01:290:COMBO_P',
              'VGCC:AS01:275:PMONRAW', 'ASTA:PV04:SCANPV1:RAND_VALS', 'ANDOR1:cam1:AndorEMGain',
              'ANDOR1:cam1:AcquireTime', 'ASTA:PV04:DATA:FILEPATH', 'ASTA:PV04:SCAN:DATA_DEST',
              'ASTA:PV04:SCAN:ID', 'ASTA:PV04:SCAN:DATA_DEST', 'ASTA:PV04:SCAN:TYPE']

# Start Scan
run_pv.put(1)
if elogFlag:
    # Start elog entry
    print('Creating elog entry...')
    elog.start()
    elog.add_params(pvnamelist=pvlist if pvlist else [])
sleep(0.2)
if n_runs > 1:
    try:
        for i in range(n_runs): 
            if run_pv.get():
                print('*'*15 + ' Run %03d ' % (i+1) + '*'*15)
                if filepath.endswith('/'):
                    filepath_new = filepath.rstrip('/')
                else:
                    filepath_new = filepath
                filepath_new += '/run%03d' % (i+1)
                filepath_pv.put(filepath_new + '\0')
                sleep(0.5)
                subprocess.call([script, pv_prefix])
                print('')
    finally:
        filepath_pv.put(filepath + '\0')
        run_pv.put(0)
        sleep(0.2)
    print('*'*15 + ' All runs done. ' + '*'*15)
elif n_runs == 1:
    subprocess.call([script, pv_prefix])
    run_pv.put(0)
else:
    raise Exception('N Runs must be > 0')
if elogFlag:
    # End elog entry
    elog.end()

sys.exit(0)


