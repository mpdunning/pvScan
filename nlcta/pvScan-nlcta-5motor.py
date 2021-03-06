#!/usr/bin/env python
# For doing DAQ scans.  Logs PV data to a file while doing scan of an arbitrary PV. Uses a supporting IOC (pvScan).
# mdunning 1/7/16

from epics import PV
from time import sleep
import datetime,os,sys,math
from threading import Thread


# PV prefix for pvScan IOC; should be passed as an argument to this script.
pvPrefix=sys.argv[1]
# Set an environment variable for so pvscan module can use it
os.environ['PVSCAN_PVPREFIX']=pvPrefix

# For printing status messages to PV
msgPv=PV(pvPrefix + ':MSG')
msgPv.put('Initializing...')
print 'Initializing...'

# Import pvscan module
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/prod/modules/')
import pvscan

#--- Experiment ---------------------------------------
# Create Experiment object.  Sets default filepath and gets experiment name from PV.
# First argument (optional) is an experiment name, leave blank to get from pvScan IOC.
# Second arg (optional) is a filepath, leave blank to get from pvScan IOC.
# Third arg (optional) is a scan name, leave blank to get from pvScan IOC.
exp1=pvscan.Experiment()

#--- Scan PVs ------------------------------------------
# Create Motor objects, one for each PV you are scanning. 
# First argument is the scan PV.
# Second arg is an index which should be unique.
motor1=pvscan.Motor('ESB:XPS1:m3:MOTR',1)  # (UED pitch motor)
motor2=pvscan.Motor('ESB:XPS1:m6:MOTR',2)  # (UED Y motor)
motor3=pvscan.Motor('ESB:XPS1:m7:MOTR',3)  # (UED Z motor)
motor4=pvscan.Motor('ESB:XPS1:m4:MOTR',4)  # (UED X motor)
motor5=pvscan.Motor('ESB:XPS2:m1:MOTR',5)  # (UED Delay motor)

#--- Shutters -----------------------------------------
# Create Shutter objects. 
# First argument (required) is the shutter control PV.
# Second arg (optional) is an RBV PV, for example an ADC channel.
# Third arg (optional) is a unique shutter number index, which allows enabling/disabling from PVs.
shutter1=pvscan.DummyShutter('ESB:GP01:VAL01','ESB:GP01:VAL01',1) # (UED Drive laser)
shutter2=pvscan.DummyShutter('ESB:GP01:VAL02','ESB:GP01:VAL02',2) # (UED pump laser)
shutter3=pvscan.DummyShutter('ESB:GP01:VAL03','ESB:GP01:VAL03',3) # (UED HeNe laser)
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
# Example: dataLogPvList=shutterGroup1.rbv + [motor1,lsrpwrPv,PV('MY:PV1')] + [PV('MY:PV2')]
dataLogPvList=shutterGroup1.rbv + [motor1.rbv,motor2.rbv,motor3.rbv,motor4.rbv,motor5.rbv]
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
grab0=pvscan.ImageGrabber('13PS7')
grab1=pvscan.ImageGrabber('13PS10')
#-------------------------------------------------------------

# --- For UED  --------------------------
resetFlag=PV(pvPrefix + ':RESET:ENABLE').get()
radius=PV(pvPrefix + ':RADIUS').get()
resetMotorPv=motor1
nResets=PV(pvPrefix + ':NRESETS').get()
#-------------------------------------------------------------

### Define scan routine #####################################################

def resetLoop(grabObject='',resetMotorPv=''):
    "Does UED DAE reset routine."
    pvscan.printMsg('Starting reset loop')
    # Open drive laser shutter
    #shutter1.open.put(1)
    if shutter2.enabled:
        pvscan.printMsg('Opening pump shutter')
        shutter2.open.put(1)
    # Enable TTL In for HeNe shutter if enabled from PV. 
    if shutter3.enabled:
        pvscan.printMsg('Enabling TTL In for HeNe shutter')
        shutter3.ttlInEnable.put(1)
    pvscan.printSleep(0.5)
    if grabObject:
        if grabObject.grabFlag:
            grabObject.filenameExtras='_' + resetMotorPv.desc + '-' + '{0:08.4f}'.format(resetMotorPv.get())
            grabObject.grabImages()
    # Disable TTL In for HeNe shutter if enabled from PV. 
    if shutter3.enabled:
        pvscan.printMsg('Disabling TTL In for HeNe shutter')
        shutter3.ttlInDisable.put(0)
    # Close pump and HeNe shutters, but only if enabled from PV.
    if shutter2.enabled:
        pvscan.printMsg('Closing pump shutter')
        shutter2.close.put(0)
    if shutter3.enabled:
        pvscan.printMsg('Closing HeNe shutter')
        shutter3.close.put(0)
    pvscan.printMsg('Reset loop done')

def motorScan(motor1,motor2,motor3,grabObject='',radius=0,resetFlag=0,resetMotorPv=''):
    "Scans motor1 from start to stop in n steps, moving motors 2 and 3 and doing a reset loop at each step."
    initialPos1=motor1.get()
    initialPos2=motor2.get()
    initialPos3=motor3.get()
    pvscan.printMsg('Starting motor scan')
    inc=(motor1.stop-motor1.start)/(motor1.nsteps-1)
    for i in range(motor1.nsteps):
        # Move motor 1
        newPos0=motor1.start + i*inc
        newPos1=newPos0 + motor1.offset
        pvscan.printMsg('Moving %s to %f' % (motor1.pvname,newPos1))
        motor1.move(newPos1,timeout=300)
        # Move motor 2
        newPos2=motor2.offset + radius*math.cos(newPos0*math.pi/180)
        pvscan.printMsg('Moving %s to %f' % (motor2.pvname,newPos2))
        motor2.move(newPos2)
        # Move motor 3
        newPos3=motor3.offset + radius*math.sin(newPos0*math.pi/180)
        pvscan.printMsg('Moving %s to %f' % (motor3.pvname,newPos3))
        motor3.move(newPos3)
        pvscan.printSleep(motor1.settletime,'Settling')
        # Do reset loop if resetFlag==1
        if resetFlag:
            resetLoop(grabObject,resetMotorPv)
    # Move motors back to initial positions
    pvscan.printMsg('Moving %s back to initial position: %f' %(motor1.pvname,initialPos1))
    motor1.move(initialPos1)
    pvscan.printMsg('Moving %s back to initial position: %f' %(motor2.pvname,initialPos2))
    motor2.move(initialPos2)
    pvscan.printMsg('Moving %s back to initial position: %f' %(motor3.pvname,initialPos3))
    motor3.move(initialPos3)

def scanRoutine():
    "This is the scan routine"
    pvscan.printMsg('Starting')
    sleep(0.5) # Collect some initial data first
    # Grab images of the sample
    if grab0.grabFlag: 
        grab0.grabImages(2)
    # Close pump and HeNe shutters, but only if enabled from PV.
    if shutter2.enabled:
        pvscan.printMsg('Closing pump shutter')
        shutter2.close.put(0)
    if shutter3.enabled:
        pvscan.printMsg('Closing HeNe shutter')
        shutter3.close.put(0)
    # Set all shutters to fast mode
    shutterGroup1.fast()
    # Do motor scan
    if exp1.scanflag:
        motorScan(motor1,motor2,motor3,grab1,radius,resetFlag,resetMotorPv)
    else:
        sleep(2)
    # Close pump and HeNe shutters, but only if enabled from PV.
    if shutter2.enabled:
        pvscan.printMsg('Closing pump shutter')
        shutter2.close.put(0)
    if shutter3.enabled:
        pvscan.printMsg('Closing HeNe shutter')
        shutter3.close.put(0)
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
        if dataLog1.dataEnable:
            pvscan.Tee(dataLog1.logFilename, 'w')
            pvscan.dataFlag=1  # Start logging data when thread starts
            datalogthread=Thread(target=dataLog1.datalog,args=())
            datalogthread.start()
        scanRoutine()
        sleep(2) # Log data for a little longer
    finally:
        pvscan.dataFlag=0  # Stop logging data 

        
### End ##########################################################################
        

exit

