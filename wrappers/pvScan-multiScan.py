#!/usr/bin/env python

import subprocess
import sys
from time import sleep
from epics import PV, caput

DEBUG = 0

args='PV_PREFIX'

def show_usage():
    "Prints usage"
    print 'Usage: %s %s' %(sys.argv[0], args)

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
    print '*** Warning: N Runs was None, setting to 1 ***'
    n_runs = 1

if DEBUG:
    print 'pv_prefix: ', pv_prefix
    print 'script: ', script
    print 'filepath: ', filepath
    print 'n_runs: ', n_runs

run_pv.put(1)
sleep(0.2)
if n_runs > 1:
    try:
        for i in range(n_runs): 
            if run_pv.get():
                print '*'*15 + ' Run %03d ' % (i+1) + '*'*15
                if filepath.endswith('/'):
                    filepath_new = filepath.rstrip('/')
                else:
                    filepath_new = filepath
                filepath_new += '/run%03d' % (i+1)
                filepath_pv.put(filepath_new + '\0')
                sleep(0.5)
                subprocess.call([script, pv_prefix])
                print ''
    finally:
        filepath_pv.put(filepath + '\0')
        run_pv.put(0)
        sleep(0.2)
    print '*'*15 + ' All runs done. ' + '*'*15
elif n_runs == 1:
    subprocess.call([script, pv_prefix])
    run_pv.put(0)
else:
    raise Exception('N Runs must be > 0')

sys.exit(0)


