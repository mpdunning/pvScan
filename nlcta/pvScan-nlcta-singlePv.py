#!/usr/bin/env python
# For doing DAQ scans.  Logs PV data to a file while doing scan of an arbitrary PV. Uses a supporting IOC (pvScan).
# mdunning 1/7/16

from epics import caget,caput,PV
from time import sleep
import datetime,os,sys
from threading import Thread

args='PV_PREFIX'

def show_usage():
    "Prints usage"
    print 'Usage: %s %s' %(sys.argv[0], args)

if len(sys.argv) != 2:
    show_usage()
    sys.exit(1)

# PV prefix for pvScan IOC; should be passed as an argument to this script.
pvPrefix=sys.argv[1]
# Set an environment variable for so pvScan module can use it
os.environ['PVSCAN_PVPREFIX']=pvPrefix

# Import pvScan module
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/R2.0/modules/')
import pvScan2

#--- Experiment ---------------------------------------
# Create Experiment object.  Sets default filepath and gets experiment name from PV.
# First argument (optional) is an experiment name.
# Second arg (optional) is a filepath.
exp1=pvScan2.Experiment()
sleep(2)

#--- Scan PVs ------------------------------------------
# Create ScanPv objects, one for each PV you are scanning. 
# First argument is the scan PV, leave blank to get from pvScan IOC. 
# Second arg is an index which should be unique.
scanPv1=pvScan2.ScanPv('',1) # (UED Solenoid)

#--- Shutters -----------------------------------------
# Create Shutter objects. 
# First argument is shutter PV.
# Second arg is RBV PV, for example an ADC channel.
shutter1=pvScan2.DummyShutter('ESB:GP01:VAL01','ESB:GP01:VAL01') # (UED Drive laser)
shutter2=pvScan2.DummyShutter('ESB:GP01:VAL02','ESB:GP01:VAL02') # (UED pump laser)
shutter3=pvScan2.DummyShutter('ESB:GP01:VAL03','ESB:GP01:VAL03') # (UED HeNe laser)
#
# Create ShutterGroup object to use common functions on all shutters.
# Argument is a list of shutter objects.
shutterGroup1=pvScan2.ShutterGroup([shutter1,shutter2,shutter3])  
#
#--- Other PVs -----------------
# Define as PV objects.  Example PV('MY:RANDOM:PV')
#lsrpwrPv=PV('ESB:A01:ADC1:AI:CH3')
#toroid0355Pv=PV('ESB:A01:ADC1:AI:CH4')
#toroid2150Pv=PV('ESB:A01:ADC1:AI:CH5')
#structureChargePv=PV('ESB:A01:ADC1:CALC:CH1:CONV')

#---- Data logging --------------------------
# List of PV() objects to be monitored during scan.  
dataLogPvList=shutterGroup1.rbv + [scanPv1]
#
# Create DataLogger object.
# Argument is the list of PVs to monitor.
dataLog1=pvScan2.DataLogger(dataLogPvList)
#-------------------------------------------------

# --- Image grabbing --------------------------
# Override saved camera settings here. Leave empty list to use the default; otherwise add PVs with single quotes.
grabImagesSettingsPvList=['13PS10:cam1:Manufacturer_RBV']
#
# Create ImageGrabber object.
# First arg is the camera PV prefix.
# Second arg (optional) is a list of camera setting PVs to be dumped to a file.
# Third arg (optional) is the image grabbing plugin.
grab1=pvScan2.ImageGrabber('13PS10')
#-------------------------------------------------------------

### Define scan routine #####################################################

def scanRoutine():
    "This is the scan routine"
    pvScan2.printMsg('Starting')
    sleep(0.5) # Collect some initial data first
    # Open shutters
    pvScan2.printMsg('Opening shutters')
    pvScan2.shutterFunction(shutterGroup1.open,1)
    # Scan delay stage and grab images...
    pvScan2.ScanPv.pv1DScan(scanPv1,grab1)
    # Close shutters
    pvScan2.printMsg('Closing shutters')
    pvScan2.shutterFunction(shutterGroup1.close,0)
    pvScan2.printMsg('Done')

### Main program ##########################################################3

if __name__ == "__main__":
    "Do scan routine; log PV data to file as a separate thread if enabled"
    pvScan2.Tee(dataLog1.logFilename, 'w')
    pvScan2.dataFlag=1  # Start logging data when thread starts
    if dataLog1.dataEnable==1:
        datalogthread=Thread(target=pvScan2.DataLogger.datalog,args=(dataLog1,))
        datalogthread.start()
    try:
        scanRoutine()
        sleep(2) # Log data for a little longer
    finally:
        pvScan2.dataFlag=0  # Stop logging data 

        
### End ##########################################################################
        

exit

