#!/usr/bin/env python
# For aborting scans.  
# mdunning 1/7/16

from epics import PV
from time import sleep
import os,sys,signal

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
import pvscan3

# Get PID PV
pid=pvscan3.pidPV.get()

# For stopping the wrapper script
runFlagPv=PV(pvPrefix + ':RUNFLAG')

exp = pvscan3.Experiment(2)

#--- Shutters -----------------------------------------
shutter1=pvscan3.DummyShutter('ESB:GP01:VAL01','ESB:GP01:VAL01',1) # (Drive laser)
shutter2=pvscan3.DummyShutter('ESB:GP01:VAL02','ESB:GP01:VAL02',2) # (Pump laser)
shutter3=pvscan3.DummyShutter('ESB:GP01:VAL03','ESB:GP01:VAL03',3) # (Shutter 3)
#
shutterGroup1=pvscan3.ShutterGroup([shutter1,shutter2,shutter3])

##################################################################################################################            
def abortRoutine():
    "This is the abort routine"
    # Kill scan routine process
    pvscan3.printMsg('Killing process %d...' % (pid))
    os.kill(pid, signal.SIGKILL)
    # Stop the wrapper script
    pvscan3.printMsg('Stopping wrapper script')
    runFlagPv.put(0)
    # Stop move(s)
    pvscan3.printMsg('Stopping move(s)')
    try:
        exp.scanpvs[0].abort.put(1)
        exp.scanpvs[1].abort.put(1)
    except AttributeError:
        'Warning: abortRoutine: AttributeError'
    #sleep(0.5)
    # Close shutters if enabled from PV
    pvscan3.printMsg('Closing shutters')
    shutterGroup1.close(0)
    pvscan3.printMsg('Aborted')


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

