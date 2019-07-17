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
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/dev/modules/')
import pvscan

# Get PID PV
pid=pvscan.pidPV.get()

# For stopping the wrapper script
runFlagPv=PV(pvPrefix + ':RUNFLAG')

exp = pvscan.Experiment(npvs=2, nshutters=3, log=False, createDirs=False)

##################################################################################################################            
def abortRoutine():
    "This is the abort routine"
    # Kill scan routine process
    pvscan.printMsg('Killing process %d...' % (pid))
    os.kill(pid, signal.SIGKILL)
    # Stop the wrapper script
    pvscan.printMsg('Stopping wrapper script')
    runFlagPv.put(0)
    # Stop move(s)
    pvscan.printMsg('Stopping scan')
    try:
        for pv in exp.scanpvs:
            pv.abort.put(1)
    except AttributeError:
        'Warning: abortRoutine: AttributeError'
    # Shutters
    pvscan.printMsg('Returning shutters to initial state')
    for shutter in exp.shutters:
        shutter.open.put(1) if shutter.initial.get() == 1 else shutter.close.put(0)
    pvscan.printMsg('Aborting image grabbing')
    exp.grabber.abort()
    pvscan.printMsg('Aborted')


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

