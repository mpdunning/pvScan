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
# Set an environment variable for pvScan module
os.environ['PVSCAN_PVPREFIX'] = pvPrefix

# For printing status messages to PV
msgPv = PV(pvPrefix + ':MSG')
msgPv.put('Initializing scan...')
print('Initializing scan...')

# Import pvScan module
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/prod/modules/')
import pvscan

# Configure logging
pvscan.loggingConfig()

# For thread-safe printing
print_lock = threading.Lock()

# Set up a scan with 2 Scan PVs, 3 shutters
exp = pvscan.Experiment(npvs=2, nshutters=3, mutex=print_lock)

# Add extra monitor PVs here.  Yuo can also add them to the "Monitor PV list" in the GUI.
# For example: 
# exp.dataLog.pvlist += [PV('ASTA:AO:BK05:V0079'), PV('ASTA:AO:BK05:V0080')]
#print([pv.pvname for pv in exp.dataLog.pvlist])

### Define scan routine #####################################################
def scanRoutine():
    "This is the scan routine"
    # Print scan info
    pvscan.printScanInfo(exp, exp.scanpvs)
    pvscan.printMsg('Starting')
    sleep(0.5) # Collect some initial data first
    # Scan delay stage and grab images...
    pvscan.pvNDScan(exp, exp.scanpvs, exp.grabber, exp.shutters)

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
        pvscan.pidPV.put(pid)
        if exp.dataLog.dataEnable:
            # Start logging data
            exp.dataLog.start()
        # Do scan
        scanRoutine()
        sleep(0.5) # Log data for a little longer
        pvscan.printMsg('Done')
    finally:
        # Stop logging data
        exp.dataLog.stop()

        
### End ##########################################################################
        

sys.exit(0)

