#!/usr/bin/env python
# For doing DAQ scans.  Logs PV data to a file while doing scan of an arbitrary PV. Uses a supporting IOC (pvScan).
# mdunning 1/7/16

from epics import PV
from time import sleep
import datetime,os,sys
from threading import Thread


# PV prefix for pvScan IOC; should be passed as an argument to this script.
pvPrefix=sys.argv[1]
# Set an environment variable for so pvScan module can use it
os.environ['PVSCAN_PVPREFIX']=pvPrefix

# Import pvScan module
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/prod/modules/')
import pvscan

#--- Experiment ---------------------------------------
# Create Experiment object.  Sets default filepath and gets experiment name from PV.
# First argument (optional) is an experiment name.
# Second arg (optional) is a filepath.
exp1=pvscan.Experiment()
sleep(2)

#--- Scan PVs ------------------------------------------
# Create ScanPv objects, one for each PV you are scanning. 
# First argument is the scan PV, leave blank to get from pvScan IOC. 
# Second arg is an index which should be unique.
scanPv1=pvscan.ScanPv('',1)

#--- Shutters -----------------------------------------
# Create Shutter objects. 
# First argument is shutter PV.
# Second arg (optional) is an RBV PV, for example an ADC channel.
shutter1=pvscan.LSCShutter('ASTA:LSC01','ADC:AS01:13:V') # (UED Drive laser)
shutter2=pvscan.LSCShutter('ASTA:LSC02','ADC:AS01:14:V') # (UED pump laser)
shutter3=pvscan.LSCShutter('ASTA:LSC03','ADC:AS01:15:V') # (UED HeNe laser)
#
# Create ShutterGroup object to use common functions on all shutters.
# Argument is a list of shutter objects.
shutterGroup1=pvscan.ShutterGroup([shutter1,shutter2,shutter3])  
#
#--- Other PVs -----------------
# Define as PV objects.  Example PV('MY:RANDOM:PV')
#lsrpwrPv=PV('ESB:A01:ADC1:AI:CH3')
#toroid0355Pv=PV('ESB:A01:ADC1:AI:CH4')
#toroid2150Pv=PV('ESB:A01:ADC1:AI:CH5')
#structureChargePv=PV('ESB:A01:ADC1:CALC:CH1:CONV')

#---- Data logging --------------------------
# List of PV() objects to be monitored during scan.  
# Example: dataLogPvList=shutterGroup1.rbv + [scanPv1,lsrpwrPv,PV('MY:PV1')] + [PV('MY:PV2')]
dataLogPvList=shutterGroup1.rbv + [scanPv1]
#
# Create DataLogger object.
# Argument is the list of PVs to monitor.
dataLog1=pvscan.DataLogger(dataLogPvList)
#-------------------------------------------------

# --- Image grabbing --------------------------
# Override saved camera settings here. Leave empty list to use the default; otherwise add PVs with single quotes.
grabImagesSettingsPvList=[]
#
# Create ImageGrabber object.
# First arg is the camera PV prefix.
# Second arg (optional) is a list of camera setting PVs to be dumped to a file.
# Third arg (optional) is the image grabbing plugin.
grab1=pvscan.ImageGrabber('ANDOR1')
#-------------------------------------------------------------

### Define scan routine #####################################################

def scanRoutine():
    "This is the scan routine"
    pvscan.printMsg('Starting')
    sleep(0.5) # Collect some initial data first
    # Open shutters
    #pvscan.printMsg('Opening shutters')
    #pvscan.shutterFunction(shutterGroup1.open,1)
    # Scan delay stage and grab images...
    pvscan.ScanPv.pv1DScan(scanPv1,grab1)
    # Close shutters
    #pvscan.printMsg('Closing shutters')
    #pvscan.shutterFunction(shutterGroup1.close,0)
    pvscan.printMsg('Done')

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
        pvscan.pidPV.put(pid)
        pvscan.Tee(dataLog1.logFilename, 'w')
        pvscan.dataFlag=1  # Start logging data when thread starts
        if dataLog1.dataEnable==1:
            datalogthread=Thread(target=dataLog1.datalog,args=())
            datalogthread.start()
        scanRoutine()
        sleep(2) # Log data for a little longer
    finally:
        pvscan.dataFlag=0  # Stop logging data 

        
### End ##########################################################################
        

exit

