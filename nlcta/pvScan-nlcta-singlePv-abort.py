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

# Import pvScan module
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/R2.0/modules/')
import pvScan2

# Get PID PV
pid=pvScan2.pidPV.get()

#--- Shutters -----------------------------------------
# Create Shutter objects. 
# First argument is shutter PV.
# Second arg (optional) is an RBV PV, for example an ADC channel.
shutter1=pvScan2.DummyShutter('ESB:GP01:VAL01') # (UED Drive laser)
shutter2=pvScan2.DummyShutter('ESB:GP01:VAL02') # (UED pump laser)
shutter3=pvScan2.DummyShutter('ESB:GP01:VAL03') # (UED HeNe laser)
#
# Create ShutterGroup object to use common functions on all shutters.
# Argument is a list of shutter objects.
shutterGroup1=pvScan2.ShutterGroup([shutter1,shutter2,shutter3])

##################################################################################################################            
def abortRoutine():
    "This is the abort routine"
    pvScan2.printMsg('Aborting')
    # Kill scan routine process
    pvScan2.printMsg('Killing process %d...' % (pid))
    os.kill(pid, signal.SIGKILL)
    # Disable shutters
    #pvScan2.printMsg('Disabling shutters')
    #pvScan2.shutterFunction(shutterGroup1.ttlInDisable,0)
    #sleep(0.5)
    # Close shutters
    pvScan2.printMsg('Closing shutters')
    pvScan2.shutterFunction(shutterGroup1.close,0)
    pvScan2.printMsg('Aborted')


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

