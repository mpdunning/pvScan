#!/usr/bin/env python
# For doing DAQ scans.  Logs PV data to a file while doing scan of an arbitrary PV. Uses a supporting IOC (pvScan).
# mdunning 1/7/16

from epics import PV
from time import sleep
import datetime,os,sys
from threading import Thread
import subprocess

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
import pvscan

#--- Experiment ---------------------------------------
# Create Experiment object.  Sets default filepath and gets experiment name from PV.
# First argument (optional) is an experiment name, leave blank to get from pvScan IOC.
# Second arg (optional) is a filepath, leave blank to get from pvScan IOC.
# Third arg (optional) is a scan name, leave blank to get from pvScan IOC.
exp1=pvscan.Experiment()
exp1.targetname=PV(pvPrefix + ':SCAN:TARGETNAME').get()
if ' ' in exp1.targetname: exp1.targetname=exp1.targetname.replace(' ','_')

#--- Log file ------------------------------
# Create log file object.  Writes to stdout and to a log file.
# First arg (optional) is a filename, leave blank to get from pvScan IOC.
logFile1=pvscan.Tee()
 
#--- Scan PVs ------------------------------------------
# Create ScanPv objects, one for each PV you are scanning. 
# First argument (required) is the scan PV, leave as empty string to get from pvScan IOC. 
# Second arg (required) is an index which should be unique.
# Third arg (optional) is an RBV pv name.
scanPv1=pvscan.ScanPv('', 1)
scanPv2=pvscan.ScanPv('', 2)
scanPv3=pvscan.ScanPv('MOTR:AS01:MC02:CH2:MOTOR', 3, pvtype=1)  # UED Z Motor
scanPv4=pvscan.ScanPv('MOTR:AS01:MC02:CH8:MOTOR', 4, pvtype=1)  # UED Y Motor

#--- Shutters -----------------------------------------
# Create Shutter objects.
# Create Shutter objects. 
# First argument (required) is the shutter control PV.
# Second arg (optional) is an RBV PV, for example an ADC channel.
# Third arg (optional) is a unique shutter number index, which allows enabling/disabling from PVs.
shutter1=pvscan.LSCShutter('ASTA:LSC01','ADC:AS01:13:V',1)
shutter2=pvscan.LSCShutter('ASTA:LSC02','ADC:AS01:14:V',2)
shutter3=pvscan.LSCShutter('ASTA:LSC03','ADC:AS01:15:V',3)
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

# --- Image grabbing --------------------------
# Override saved camera settings here. Leave empty list to use the default; otherwise add PVs with single quotes.
grabImagesSettingsPvList=[]
#
# Create ImageGrabber object.
# 1st arg (required) is the camera PV prefix, leave as empty string to get from pvScan IOC.  
# 2nd arg (optional) is the number of images.
# 3rd arg (optional) is a list of camera setting PVs to be dumped to a file.
# 4th arg (optional [TIFF1]) is the image grabbing plugin.
grab1=pvscan.ImageGrabber('ASPS03',3)  # Sample camera
grab2=pvscan.ImageGrabber('')  # Get camera from PV
#-------------------------------------------------------------

#--- Experiment specifics ------------------------------------------
LedPv=PV('ASTA:BO:2114-9:BIT3')  # PV for sample LED
beamRate=PV(pvPrefix + ':BEAMRATE').get()  # Beam rate input parameter; for timing image grabbing
nImages=grab2.nImages  # N images for sample camera
grabSampleImagesFlag=PV(pvPrefix + ':GRABIMAGES:SAMPLE').get()
ssBeamFlag=PV(pvPrefix + ':SCAN:SSBEAM').get()  # Single-shot beam flag
ssBeamPumpFlag=PV(pvPrefix + ':SCAN:SSBEAMPUMP').get()  # Single-shot beam/pump flag
waitTime=nImages/beamRate  
grab1.fileNamePrefix=exp1.targetname  # Add target name to image file prefix
grab2.fileNamePrefix=exp1.targetname
zLockFlag=PV(pvPrefix + ':Z:LOCK:ENABLE').get()  # Lock Z stage to Scan PV 1
zSlope=PV(pvPrefix + ':Z:LOCK:SLOPE').get()  # Slope for Z-lock
zIntercept=PV(pvPrefix + ':Z:LOCK:INT').get()  # Intercept for Z-lock
yLockFlag=PV(pvPrefix + ':Y:LOCK:ENABLE').get()  # Lock Y stage to Scan PV 1
ySlope=PV(pvPrefix + ':Y:LOCK:SLOPE').get()  # Slope for Y-lock
yIntercept=PV(pvPrefix + ':Y:LOCK:INT').get()  # Intercept for Y-lock
#delta=0.01  # Custom move/wait threshold; passed to move() commands
delta=PV(pvPrefix + ':SCANPV1:DELTA').get()  # Custom move/wait threshold; passed to move() commands
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
dataLogPvList=[grab2.timestampRBVPv,grab2.captureRBVPv,grab1.captureRBVPv,LedPv,scanPv3.scanpv.rbv] + dataLogPvList
#
# Create DataLogger object.
# First argument (required) is the list of PVs to monitor.
dataLog1=pvscan.DataLogger(dataLogPvList)
#-------------------------------------------------

def grabSampleImages(filenameExtras, when=''):
    # Turn LED on
    pvscan.printMsg('Turning LED on')
    LedPv.put(1)
    sleep(0.5)
    # Grab some images
    grab1.filenameExtras=filenameExtras + when
    grab1.grabImages()
    # Turn LED off
    pvscan.printMsg('Turning LED off')
    LedPv.put(0)
    sleep(0.5)

def wdmGrabRoutine(filenameExtras=''):
    # Grab sample images if enabled from PV
    if grabSampleImagesFlag:
        grabSampleImages(filenameExtras, when='_before')
    # Grab images of beam in separate thread, if enabled from PV
    if ssBeamFlag:
        grab2.filenameExtras=filenameExtras + '_beam'
        grab2Thread=Thread(target=grab2.grabImages,args=())
        grab2Thread.start()
        #sleep(waitTime/2.0)
        #sleep(waitTime/16.0)
        # Single shot of beam only
        pvscan.printMsg('Getting single shot of beam')
        subprocess.call('/afs/slac/g/testfac/extras/scripts/asta/singleShotUED.py ' + pvPrefix + ' beam', shell=True)
        # Wait for image grabbing to finish
        grab2Thread.join()
        # Wait for capturing to finish
        while grab2.captureRBVPv.get() or grab2.writingRBVPv.get():
            sleep(0.1)
    # Grab images of pump in separate thread, if enabled from PV
    if ssBeamPumpFlag:
        grab2.filenameExtras=filenameExtras + '_beam_pump'
        grab2Thread=Thread(target=grab2.grabImages,args=())
        grab2Thread.start()
        #sleep(waitTime/2.0)
        #sleep(waitTime/16.0)
        # Single shot of beam and pump
        pvscan.printMsg('Getting single shot of beam and pump')
        subprocess.call('/afs/slac/g/testfac/extras/scripts/asta/singleShotUED.py ' + pvPrefix + ' beam-pump', shell=True)
        grab2Thread.join()
        while grab2.captureRBVPv.get() or grab2.writingRBVPv.get():
            sleep(0.1)
        #sleep(grab2.nImages*0.5)
    # Grab sample images if enabled from PV
    if grabSampleImagesFlag:
        grabSampleImages(filenameExtras, when='_after')

def wdmScan(exp,pv1,pv2,pv3,pv4,grabObject=''):
    if 1 <= exp.scanmode <= 2 and pv2.scanpv and not pv1.scanpv:
        pv1=pv2
        exp.scanmode=1
    if 1 <= exp.scanmode <= 2 and pv1.scanpv:
        initialPos1=pv1.scanpv.get()
        inc1=(pv1.scanpv.stop-pv1.scanpv.start)/(pv1.scanpv.nsteps-1)
        if zLockFlag:
            initialPos3=pv3.scanpv.get()
        if yLockFlag:
            initialPos4=pv4.scanpv.get()
        if exp.scanmode==2 and pv2.scanpv:
            initialPos2=pv2.scanpv.get()
            inc2=(pv2.scanpv.stop-pv2.scanpv.start)/(pv2.scanpv.nsteps-1)
        pvscan.printMsg('Scanning %s from %f to %f in %d steps' % (pv1.scanpv.pvname,pv1.scanpv.start,pv1.scanpv.stop,pv1.scanpv.nsteps))
        for i in range(pv1.scanpv.nsteps):
            newPos1=pv1.scanpv.start + i*inc1
            pvscan.printMsg('Setting %s to %f' % (pv1.scanpv.pvname,newPos1))
            pv1.scanpv.move(newPos1, delta=delta)
            if zLockFlag:
                newPos3=zSlope*newPos1 + zIntercept
                pvscan.printMsg('Setting %s to %f' % (pv3.scanpv.pvname,newPos3))
                pv3.scanpv.move(newPos3, delta=delta)
            if yLockFlag:
                newPos4=ySlope*newPos1 + yIntercept
                pvscan.printMsg('Setting %s to %f' % (pv4.scanpv.pvname,newPos4))
                pv4.scanpv.move(newPos4, delta=delta)
            pvscan.printSleep(pv1.scanpv.settletime,'Settling')
            if exp.scanmode==2 and pv2.scanpv:
                pvscan.printMsg('Scanning %s from %f to %f in %d steps' % (pv2.scanpv.pvname,pv2.scanpv.start,pv2.scanpv.stop,pv2.scanpv.nsteps))
                for j in range(pv2.scanpv.nsteps):
                    newPos2=pv2.scanpv.start + j*inc2
                    pvscan.printMsg('Setting %s to %f' % (pv2.scanpv.pvname,newPos2))
                    pv2.scanpv.move(newPos2, delta=delta)
                    pvscan.printSleep(pv2.scanpv.settletime,'Settling')
                    if grabObject:
                        if grabObject.grabFlag:
                            if grabObject.stepFlag:
                                grabObject.filenameExtras= '_' + pv1.scanpv.desc + '-' + '{0:03d}'.format(i+1) + '-' + '{0:08.4f}'.format(pv1.scanpv.get()) + '_' + pv2.scanpv.desc + '-' + '{0:03d}'.format(j+1) + '-' + '{0:08.4f}'.format(pv2.scanpv.get())
                            else:
                                grabObject.filenameExtras= '_' + pv1.scanpv.desc + '-' + '{0:08.4f}'.format(pv1.scanpv.get()) + '_' + pv2.scanpv.desc + '-' + '{0:08.4f}'.format(pv2.scanpv.get())
                            wdmGrabRoutine(grabObject.filenameExtras)
            else:
                if grabObject:
                    if grabObject.grabFlag:
                        if grabObject.stepFlag:
                            grabObject.filenameExtras= '_' + pv1.scanpv.desc + '-' + '{0:03d}'.format(i+1) + '-' + '{0:08.4f}'.format(pv1.scanpv.get())
                        else:
                            grabObject.filenameExtras= '_' + pv1.scanpv.desc + '-' + '{0:08.4f}'.format(pv1.scanpv.get())
                        wdmGrabRoutine(grabObject.filenameExtras)
        # Move back to initial positions
        pvscan.printMsg('Setting %s back to initial position: %f' %(pv1.scanpv.pvname,initialPos1))
        pv1.scanpv.move(initialPos1, delta=delta)
        if zLockFlag:
            pvscan.printMsg('Setting %s back to initial position: %f' %(pv3.scanpv.pvname,initialPos3))
            pv3.scanpv.move(initialPos3, delta=delta)
        if yLockFlag:
            pvscan.printMsg('Setting %s back to initial position: %f' %(pv4.scanpv.pvname,initialPos4))
            pv4.scanpv.move(initialPos4, delta=delta)
        if exp.scanmode==2 and pv2.scanpv:
            pvscan.printMsg('Setting %s back to initial position: %f' %(pv2.scanpv.pvname,initialPos2))
            pv2.scanpv.move(initialPos2, delta=delta)
    elif exp.scanmode==3:  # Grab images only
        if grabObject:
            if grabObject.grabFlag:
                grab1.grabImages()
                grab2.grabImages()
    elif exp.scanmode==4:  # WDM grab routine only
        wdmGrabRoutine()
    else:
        pvscan.printMsg('Scan mode "None" selected or no PVs entered, continuing...')
        sleep(1)



### Define scan routine #####################################################

def scanRoutine():
    "This is the scan routine"
    # Print scan info
    pvscan.printScanInfo(exp1,scanPv1,scanPv2)
    pvscan.printMsg('Starting')
    # Open all shutters, but only if enabled from PV.
    shutterGroup1.open() 
    # Do WDM PV Scan
    wdmScan(exp1,scanPv1,scanPv2,scanPv3,scanPv4,grab2)
    # Close all shutters, but only if enabled from PV.
    shutterGroup1.close(0)

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
        if dataLog1.dataEnable:
            # Start logging data
            dataLog1.start()
        scanRoutine()
        sleep(1) # Log data for a little longer
    finally:
        # Stop logging data
        dataLog1.stop()
        pvscan.printMsg('Done')

        
### End ##########################################################################
        

exit

