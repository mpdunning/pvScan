#!/usr/bin/env python
# For doing DAQ scans.  Logs PV data to a file while doing scan of an arbitrary PV. Uses a supporting IOC (pvScan).
# mdunning 1/7/16

import os
import sys
import threading
from time import sleep
from epics import PV


# PV prefix for pvScan IOC; should be passed as an argument to this script.
pvPrefix = sys.argv[1]
# Set an environment variable for so pvScan module can use it
os.environ['PVSCAN_PVPREFIX'] = pvPrefix

# For printing status messages to PV
msgPv = PV(pvPrefix + ':MSG')
msgPv.put('Initializing...')
print 'Initializing...'

# Import pvScan module
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/prod/modules/')
import pvscan

### Set up scan #####################################################
#--- Experiment ---------------------------------------
print_lock = threading.Lock()
exp = pvscan.Experiment(npvs=2, mutex=print_lock)
#-------------------------------------------------

#grabber2 = pvscan.ADGrabber('13PS7')
#motor2 = pvscan.Motor('ESB:XPS1:m6:MOTR')
#pv2 = pvscan.BasePv('13PS7:cam1:MaxSizeY_RBV')

#--- Shutters -----------------------------------------
shutter1=pvscan.LSCShutter('ASTA:LSC01', 'ADC:AS01:13:V', 1)
shutter2=pvscan.LSCShutter('ASTA:LSC02', 'ADC:AS01:14:V', 2)
shutter3=pvscan.LSCShutter('ASTA:LSC03', 'ADC:AS01:15:V', 3)
# Save initial shutter states
shutter1.initial.put(shutter1.OCStatus.get())
shutter2.initial.put(shutter2.OCStatus.get())
#
shutterGroup1 = pvscan.ShutterGroup([shutter1, shutter2, shutter3])  
#-------------------------------------------------

#--- Data logging --------------------------
# Add shutter RBVs to PV monitor list
#exp.dataLog.pvlist += shutterGroup1.rbv + [pv2]
exp.dataLog.pvlist += shutterGroup1.rbv
#-------------------------------------------------

### Define scan routine #####################################################
def scanRoutine():
    "This is the scan routine"
    # Print scan info
    pvscan.printScanInfo(exp, exp.scanpvs)
    pvscan.printMsg('Starting')
    sleep(0.5) # Collect some initial data first
    # Scan delay stage and grab images...
    pvscan.pvNDScan(exp, exp.scanpvs, exp.grabber, shutter1, shutter2, shutter3)

### Main program ##########################################################3
if __name__ == "__main__":
    "Do scan routine; log PV data to file as a separate thread if enabled"
    try:
        args = 'PV_PREFIX'
        def show_usage():
            "Prints usage"
            print 'Usage: %s %s' %(sys.argv[0], args)
        if len(sys.argv) != 2:
            show_usage()
            sys.exit(1)
        pid = os.getpid()
        pvscan.pidPV.put(pid)
        if exp.dataLog.dataEnable:
            # Start logging data
            exp.dataLog.start()
        scanRoutine()
        sleep(1) # Log data for a little longer
    finally:
        # Stop logging data
        exp.dataLog.stop()
        pvscan.printMsg('Done')

        
### End ##########################################################################
        

sys.exit(0)

