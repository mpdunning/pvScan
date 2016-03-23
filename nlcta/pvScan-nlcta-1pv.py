#!/usr/bin/env python
# For doing DAQ scans.  Logs PV data to a file while doing scan of an arbitrary PV. Uses a supporting IOC (pvScan).
# mdunning 1/7/16

from epics import PV
from time import sleep,time
import datetime,os,sys
from threading import Thread


# PV prefix for pvScan IOC; should be passed as an argument to this script.
pvPrefix=sys.argv[1]
# Set an environment variable for so pvScan module can use it
os.environ['PVSCAN_PVPREFIX']=pvPrefix

# Import pvScan module
start=time()
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/prod/modules/')
import pvscan2
end=time()
print 'Import: ', end-start

#--- Experiment ---------------------------------------
# Create Experiment object.  Sets default filepath and gets experiment name from PV.
# First argument (optional) is an experiment name.
# Second arg (optional) is a filepath.
start=time()
exp1=pvscan2.Experiment()
end=time()
print 'Exp.: ', end-start
#sleep(2)

#--- Scan PVs ------------------------------------------
# Create ScanPv objects, one for each PV you are scanning. 
# First argument is the scan PV, leave as empty string to get from pvScan IOC. 
# Second arg is an index which should be unique.
start=time()
scanPv1=pvscan2.ScanPv('',1)
end=time()
print 'scanPv: ', end-start

#--- Shutters -----------------------------------------
# Create Shutter objects. 
# First argument is shutter PV.
# Second arg (optional) is an RBV PV, for example an ADC channel.
# Third arg (optional) is a unique shutter number index, which allows enabling/disabling from PVs.
shutter1=pvscan2.DummyShutter('ESB:GP01:VAL01','ESB:GP01:VAL01',1) # (UED Drive laser)
shutter2=pvscan2.DummyShutter('ESB:GP01:VAL02','ESB:GP01:VAL02',2) # (UED pump laser)
shutter3=pvscan2.DummyShutter('ESB:GP01:VAL03','ESB:GP01:VAL03',3) # (UED HeNe laser)
#
# Create ShutterGroup object to use common functions on all shutters.
# Argument is a list of shutter objects.
shutterGroup1=pvscan2.ShutterGroup([shutter1,shutter2,shutter3])  

#--- Other PVs -----------------
# Define as PV objects.  Example PV('MY:RANDOM:PV')
#lsrpwrPv=PV('ESB:A01:ADC1:AI:CH3')
#toroid0355Pv=PV('ESB:A01:ADC1:AI:CH4')
#toroid2150Pv=PV('ESB:A01:ADC1:AI:CH5')
#structureChargePv=PV('ESB:A01:ADC1:CALC:CH1:CONV')

#---- Data logging --------------------------
# List of PV() objects to be monitored during scan.  
# Example: dataLogPvList=shutterGroup1.rbv + [scanPv1,lsrpwrPv,PV('MY:PV1')] + [PV('MY:PV2')]
dataLogPvList=shutterGroup1.rbv + [scanPv1.scanpv]
#
# Create DataLogger object.
# Argument is the list of PVs to monitor.
start=time()
dataLog1=pvscan2.DataLogger(dataLogPvList)
end=time()
print 'dataLog: ', end-start
#-------------------------------------------------

# --- Image grabbing --------------------------
# Override saved camera settings here. Leave empty list to use the default; otherwise add PVs with single quotes.
grabImagesSettingsPvList=[]
#
# Create ImageGrabber object.
# First arg is the camera PV prefix, leave as empty string to get from pvScan IOC.  
# Second arg (optional) is a list of camera setting PVs to be dumped to a file.
# Third arg (optional) is the image grabbing plugin.
start=time()
grab1=pvscan2.ImageGrabber('')
end=time()
print 'grab: ', end-start
#-------------------------------------------------------------

### Define scan routine #####################################################

def scanRoutine():
    "This is the scan routine"
    pvscan2.printMsg('Starting')
    sleep(0.5) # Collect some initial data first
    # Open all shutters, but only if enabled from PV.
    if shutter1.enabled:
        pvscan2.printMsg('Opening drive shutter')
        shutter1.open.put(1)
    if shutter2.enabled:
        pvscan2.printMsg('Opening pump shutter')
        shutter2.open.put(1)
    if shutter3.enabled:
        pvscan2.printMsg('Opening shutter 3')
        shutter3.open.put(1)
    # Scan delay stage and grab images...
    pvscan2.pv1DScan(scanPv1.scanpv,grab1)
    # Close all shutters, but only if enabled from PV.
    if shutter1.enabled:
        pvscan2.printMsg('Closing drive shutter')
        shutter1.close.put(0)
    if shutter2.enabled:
        pvscan2.printMsg('Closing pump shutter')
        shutter2.close.put(0)
    if shutter3.enabled:
        pvscan2.printMsg('Closing shutter 3')
        shutter3.close.put(0)
    pvscan2.printMsg('Done')

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
        pvscan2.Tee(dataLog1.logFilename, 'w')
        pvscan2.dataFlag=1  # Start logging data when thread starts
        if dataLog1.dataEnable==1:
            datalogthread=Thread(target=dataLog1.datalog,args=())
            datalogthread.start()
        scanRoutine()
        sleep(2) # Log data for a little longer
    finally:
        pvscan2.dataFlag=0  # Stop logging data 

        
### End ##########################################################################
        

exit

