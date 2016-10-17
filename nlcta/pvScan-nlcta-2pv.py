#!/usr/bin/env python
# For doing DAQ scans.  Logs PV data to a file while doing scan of an arbitrary PV. Uses a supporting IOC (pvScan).
# mdunning 1/7/16

from epics import PV
from time import sleep
import datetime,os,sys


# PV prefix for pvScan IOC; should be passed as an argument to this script.
pvPrefix=sys.argv[1]
# Set an environment variable for so pvScan module can use it
os.environ['PVSCAN_PVPREFIX']=pvPrefix

# For printing status messages to PV
msgPv=PV(pvPrefix + ':MSG')
msgPv.put('Initializing...')
print 'Initializing...'

# Import pvScan module
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/prod/modules/')
import pvscan2

#***** Skipped arguments must use 'None' before a non-zero argument. *****

#--- Experiment ---------------------------------------
# Create Experiment object.  Sets experiment name and filepath.
# 1st arg (optional) is an experiment name, is skipped will get from pvScan IOC.
# 2nd arg (optional) is a filepath, use default.
# 3rd arg (optional) is a scan name, if skipped will get from pvScan IOC.
exp1=pvscan2.Experiment()

#--- Log file ------------------------------
# Create log file object.  Writes to stdout and to a log file.
# 1st arg (optional) is a filename, if skipped will use default.
logFile1=pvscan2.Tee()

#--- Scan PVs ------------------------------------------
# Create ScanPv objects, one for each PV you are scanning. 
# 1st arg (required) is the scan PV, use 'None' to get from pvScan IOC. 
# 2nd arg (required) is an index which should be unique.
# 3rd arg (optional) is an RBV pv name.
scanPv1=pvscan2.ScanPv(None, 1)
scanPv2=pvscan2.ScanPv(None, 2)

#--- Shutters -----------------------------------------
# Create Shutter objects. 
# 1st arg (required) is the shutter control PV.
# 2nd arg (optional) is an RBV PV, for example an ADC channel.
# 3rd arg (optional) is a unique shutter number index, which allows enabling/disabling from PVs.
shutter1=pvscan2.DummyShutter('ESB:GP01:VAL01','ESB:GP01:VAL01',1) # (UED Drive laser)
shutter2=pvscan2.DummyShutter('ESB:GP01:VAL02','ESB:GP01:VAL02',2) # (UED pump laser)
shutter3=pvscan2.DummyShutter('ESB:GP01:VAL03','ESB:GP01:VAL03',3) # (UED HeNe laser)
#
# Create ShutterGroup object to use common functions on all shutters.
# Argument is a list of shutter objects.
shutterGroup1=pvscan2.ShutterGroup([shutter1,shutter2,shutter3])  
#
#--- Other PVs -----------------
# Define as PV objects.  Example PV('MY:RANDOM:PV')
#lsrpwrPv=PV('ESB:A01:ADC1:AI:CH3')
#toroid0355Pv=PV('ESB:A01:ADC1:AI:CH4')
#toroid2150Pv=PV('ESB:A01:ADC1:AI:CH5')

# --- Image grabbing --------------------------
# Override saved camera settings here. Leave empty list to use the default; otherwise add PVs with single quotes.
grabImagesSettingsPvList=[]
#
# Create ImageGrabber object.
# 1st arg (optional) is the camera PV prefix, if skipped will get from pvScan IOC. 
# 2nd arg (optional) is the number of images, if skipped will get from pvScan IOC.
# 3rd arg (optional) is a list of camera setting PVs to be dumped to a file, if skipped will use default.
# 4th arg (optional) is the image grabbing plugin, if skipped will use default [TIFF1].
grab1=pvscan2.ImageGrabber()  # Get camera from PV
#-------------------------------------------------------------

#---- Data logging --------------------------
# List of PV() objects to be monitored during scan.  
# Example: dataLogPvList=shutterGroup1.rbv + [scanPv1,lsrpwrPv,PV('MY:PV1')] + [PV('MY:PV2')]
if exp1.scanmode==1 and scanPv1.pvname:  # 1-pv scan
    if scanPv1.scanpv.rbv:
        dataLogPvList=shutterGroup1.rbv + [scanPv1.scanpv.rbv]
    else:
        dataLogPvList=shutterGroup1.rbv + [scanPv1.scanpv]
elif exp1.scanmode==2 and scanPv1.pvname and scanPv2.pvname:  # 2-pv scan
    if scanPv1.scanpv.rbv and scanPv2.scanpv.rbv:
        dataLogPvList=shutterGroup1.rbv + [scanPv1.scanpv.rbv,scanPv2.scanpv.rbv]
    else:
        dataLogPvList=shutterGroup1.rbv + [scanPv1.scanpv,scanPv2.scanpv]
else:
    dataLogPvList=shutterGroup1.rbv
dataLogPvList=[grab1.grabber.timestampRBVPv,grab1.grabber.captureRBVPv] + dataLogPvList
#
# Create DataLogger object.
# First argument (required) is the list of PVs to monitor.
dataLog1=pvscan2.DataLogger(dataLogPvList)
#-------------------------------------------------

### Define scan routine #####################################################

def scanRoutine():
    "This is the scan routine"
    # Print scan info
    pvscan2.printScanInfo(exp1,scanPv1,scanPv2)
    pvscan2.printMsg('Starting')
    sleep(0.5) # Collect some initial data first
    # Open all shutters, but only if enabled from PV.
    shutterGroup1.open(1)
    #shutter1.openCheck()
    # Scan delay stage and grab images...
    pvscan2.pvNDScan(exp1,scanPv1,scanPv2,grab1,shutter1,shutter2,shutter3)
    # Close all shutters, but only if enabled from PV.
    shutterGroup1.close(0)
    #shutterGroup1.closeCheck()

### Main program ##########################################################3

if __name__ == "__main__":
    "Do scan routine; log PV data to file as a separate thread if enabled"
    try:
        args='PV_PREFIX'
        def show_usage():
            "Prints usage"
            print 'Usage: %s %s' %(sys.argv[0], args)
        if len(sys.argv) != 2:
            show_usage()
            sys.exit(1)
        pid=os.getpid()
        pvscan2.pidPV.put(pid)
        if dataLog1.dataEnable:
            # Start logging data
            dataLog1.start()
        scanRoutine()
        sleep(1) # Log data for a little longer
    finally:
        # Stop logging data
        dataLog1.stop()
        pvscan2.printMsg('Done')

        
### End ##########################################################################
        

exit

