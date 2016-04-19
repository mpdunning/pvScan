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
import pvscan

# Get PID PV
pid=pvscan.pidPV.get()

#--- Scan PVs ------------------------------------------
# Create ScanPv objects, one for each PV you are scanning. 
# First argument is the scan PV, leave as empty string to get from pvScan IOC. 
# Second arg is an index which should be unique.
scanPv1=pvscan.ScanPv('',1)
scanPv2=pvscan.ScanPv('',2)

#--- Shutters -----------------------------------------
# Create Shutter objects. 
# First argument is shutter PV.
# Second arg (optional) is an RBV PV, for example an ADC channel.
shutter1=pvscan.LSCShutter('ASTA:LSC01','ADC:AS01:13:V',1)
shutter2=pvscan.LSCShutter('ASTA:LSC02','ADC:AS01:14:V',2)
shutter3=pvscan.LSCShutter('ASTA:LSC03','ADC:AS01:15:V',3)
#
# Create ShutterGroup object to use common functions on all shutters.
# Argument is a list of shutter objects.
shutterGroup1=pvscan.ShutterGroup([shutter1,shutter2,shutter3])

##################################################################################################################            
def abortRoutine():
    "This is the abort routine"
    # Kill scan routine process
    pvscan.printMsg('Killing process %d...' % (pid))
    os.kill(pid, signal.SIGKILL)
    # Stop move(s)
    pvscan.printMsg('Stopping move(s)')
    if scanPv1.scanpv:
        if scanPv1.scanpv.abort:
            scanPv1.scanpv.abort.put(1)
    if scanPv2.scanpv:
        if scanPv2.scanpv.abort:
            scanPv2.scanpv.abort.put(1)
    # Close shutters if enabled from PV
    pvscan.printMsg('Closing shutters')
    shutterGroup1.close(0)
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
