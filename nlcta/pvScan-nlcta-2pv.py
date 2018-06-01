#!/usr/bin/env python
# For doing DAQ scans.  Logs PV data to a file while doing scan of an arbitrary PV. Uses a supporting IOC (pvScan).
# mdunning 1/7/16

from __future__ import print_function
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
msgPv.put('Initializing scan...')
print('Initializing scan...')

# Import pvScan module
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/prod/modules/')
import pvscan2

### Set up scan #####################################################
pvscan2.loggingConfig()
print_lock = threading.Lock()  # For thread-safe printing

# Set up a scan with 2 Scan PVs, 3 shutters
#-------------------------------------------------
exp = pvscan2.Experiment(npvs=2, nshutters=3, mutex=print_lock)

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
    pvscan2.pvNDScan(exp, exp.scanpvs, exp.grabber, exp.shutters)
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
            print('Usage: %s %s' %(sys.argv[0], args))
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
        pvscan2.printMsg('Done')
    finally:
        # Stop logging data
        exp.dataLog.stop()

        
### End ##########################################################################
        

sys.exit(0)

