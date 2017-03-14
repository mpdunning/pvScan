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

exp = pvscan.Experiment(npvs=2, log=False, createDirs=False)
#fp = exp.filepath

#--- Shutters -----------------------------------------
shutter1=pvscan.DummyShutter('ESB:GP01:VAL01','ESB:GP01:VAL01',1) # (Drive laser)
shutter2=pvscan.DummyShutter('ESB:GP01:VAL02','ESB:GP01:VAL02',2) # (Pump laser)
shutter3=pvscan.DummyShutter('ESB:GP01:VAL03','ESB:GP01:VAL03',3) # (Shutter 3)
#
shutterGroup1=pvscan.ShutterGroup([shutter1,shutter2,shutter3])

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
    pvscan.printMsg('Stopping move(s)')
    try:
        exp.scanpvs[0].abort.put(1)
        exp.scanpvs[1].abort.put(1)
    except AttributeError:
        'Warning: abortRoutine: AttributeError'
    # Shutters
    pvscan.printMsg('Returning shutters to initial state')
    shutter1.open.put(1) if shutter1.initial.get() == 1 else shutter1.close.put(0)
    shutter2.open.put(1) if shutter2.initial.get() == 1 else shutter2.close.put(0)
    shutter3.open.put(1) if shutter3.initial.get() == 1 else shutter3.close.put(0)
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

