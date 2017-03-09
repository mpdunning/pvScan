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
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/dev/modules/')
import pvscan2
pvscan2.loggingConfig()

### Set up scan #####################################################
#--- Experiment ---------------------------------------
print_lock = threading.Lock()
exp = pvscan2.Experiment(npvs=2, mutex=print_lock)
#exp.grabber.dataStartStopPv = PV('ESB:GP01:VAL07')
#exp.grabber.dataStatusPv = PV('ESB:GP01:VAL08')
#exp.grabber.dataFilenamePv = PV('13PS7:TIFF1:FilePath')
#-------------------------------------------------

#grabber2 = pvscan2.ADGrabber('13PS7')
#motor2 = pvscan2.Motor('ESB:XPS1:m6:MOTR')
#pv2 = pvscan2.BasePv('13PS7:cam1:MaxSizeY_RBV')

#--- Shutters -----------------------------------------
shutter1 = pvscan2.DummyShutter('ESB:GP01:VAL01', 'ESB:GP01:VAL01', 1) # (Drive laser)
shutter2 = pvscan2.DummyShutter('ESB:GP01:VAL02', 'ESB:GP01:VAL02', 2) # (Pump laser)
shutter3 = pvscan2.DummyShutter('ESB:GP01:VAL03', 'ESB:GP01:VAL03', 3) # (Shutter 3)
# Save initial shutter states
shutter1.initial.put(shutter1.OCStatus.get())
shutter2.initial.put(shutter2.OCStatus.get())
#
shutterGroup1 = pvscan2.ShutterGroup([shutter1, shutter2, shutter3])  
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
    pvscan2.printScanInfo(exp, exp.scanpvs)
    pvscan2.printMsg('Starting')
    sleep(0.5) # Collect some initial data first
    # Open all shutters, but only if enabled from PV.
    #shutterGroup1.open(1)
    #shutter1.openCheck()
    # Scan delay stage and grab images...
    pvscan2.pvNDScan(exp, exp.scanpvs, exp.grabber, shutter1, shutter2, shutter3)
    #motor2.move(2.6)
    #print 'pv2 val:', pv2.get() 
    #if exp.scanmode: grabber2.grabImages(3)
    # Close all shutters, but only if enabled from PV.
    #shutterGroup1.close(0)
    #shutterGroup1.closeCheck()

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
        pvscan2.pidPV.put(pid)
        if exp.dataLog.dataEnable:
            # Start logging data
            exp.dataLog.start()
        scanRoutine()
        sleep(1) # Log data for a little longer
    finally:
        # Stop logging data
        exp.dataLog.stop()
        pvscan2.printMsg('Done')

        
### End ##########################################################################
        

sys.exit(0)

