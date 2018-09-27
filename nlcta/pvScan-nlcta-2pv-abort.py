#!/usr/bin/env python
# For aborting scans.  
# mdunning 1/7/16

import os
import shutil
import signal
import sys
from time import sleep
from epics import PV

# PV prefix for pvScan IOC; should be passed as an argument to this script.
pvPrefix=sys.argv[1]
# Set an environment variable for so pvScan module can use it
os.environ['PVSCAN_PVPREFIX']=pvPrefix

# For printing status messages to PV
msgPv=PV(pvPrefix + ':MSG')
msgPv.put('Aborting...')
print 'Aborting...'

# Import pvScan module
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/prod/modules/')
import pvscan2
pvscan2.loggingConfig('abort script')

# Get PID PV
pid=pvscan2.pidPV.get()

# For stopping the wrapper script
runFlagPv=PV(pvPrefix + ':RUNFLAG')

exp = pvscan2.Experiment(npvs=2, nshutters=3, log=False, createDirs=False)

##################################################################################################################            
def abortRoutine():
    "This is the abort routine"
    # Kill scan routine process
    pvscan2.printMsg('Killing process %d...' % (pid))
    os.kill(pid, signal.SIGKILL)
    # Stop the wrapper script
    pvscan2.printMsg('Stopping wrapper script')
    runFlagPv.put(0)
    # Stop move(s)
    pvscan2.printMsg('Stopping move(s)')
    try:
        for pv in exp.scanpvs:
            pv.abort()
    except AttributeError:
        'Warning: abortRoutine: AttributeError'
    # Shutters
    pvscan2.printMsg('Returning shutters to initial state')
    for shutter in exp.shutters:
        shutter.open.put(1) if shutter.initial.get() == 1 else shutter.close.put(0)
    pvscan2.printMsg('Aborting image grabbing')
    exp.grabber.abort()
    pvscan2.printMsg('Aborted')


if __name__ == "__main__":
    "Do abort routine"
    args='PV_PREFIX'
    def show_usage():
        "Prints usage"
        print 'Usage: %s %s' %(sys.argv[0], args)
    if len(sys.argv) != 2:
        show_usage()
        sys.exit(1)
    abortRoutine()

##################################################################################################################
        

exit

