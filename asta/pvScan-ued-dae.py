#!/usr/bin/env python
# For doing DAQ scans.  Logs PV data to a file while doing scan of an arbitrary PV. Uses a supporting IOC (pvScan).
# mdunning 1/7/16

from epics import PV
from time import sleep
import datetime,os,sys,math


# PV prefix for pvScan IOC; should be passed as an argument to this script.
pvPrefix=sys.argv[1]
# Set an environment variable for so pvscan module can use it
os.environ['PVSCAN_PVPREFIX']=pvPrefix

# For printing status messages to PV
msgPv=PV(pvPrefix + ':MSG')
msgPv.put('Initializing...')
print 'Initializing...'

# Import pvscan module
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/R3.1/modules/')
import pvscan

#--- Experiment ---------------------------------------
# Create Experiment object.  Sets default filepath and gets experiment name from PV.
# First argument (optional) is an experiment name.
# Second arg (optional) is a filepath.
exp1=pvscan.Experiment()

#--- Log file ------------------------------
# Create log file object.  Writes to stdout and to a log file.
# First arg (optional) is a filename, leave blank to get from pvScan IOC.
logFile1=pvscan.Tee()

#--- Scan PVs ------------------------------------------
# Create Motor objects, one for each PV you are scanning. 
# First argument is the scan PV, leave blank to get from pvScan IOC. 
# Second arg is an index which should be unique.
motor1=pvscan.PolluxMotor('ASTA:POLX01:AO:ABSMOV',1)  # (UED pitch motor)
motor2=pvscan.Motor('MOTR:AS01:MC02:CH8:MOTOR',2)  # (UED Y motor)
motor3=pvscan.Motor('MOTR:AS01:MC02:CH2:MOTOR',3)  # (UED Z motor)
motor4=pvscan.Motor('MOTR:AS01:MC02:CH7:MOTOR',4)  # (UED X motor)
motor5=pvscan.Motor('MOTR:AS01:MC01:CH8:MOTOR',5)  # (UED Delay motor)
#
#--- Shutters -----------------------------------------
# Create Shutter objects. 
# First argument is shutter PV.
# Second arg (optional) is an RBV PV, for example an ADC channel.
# Third arg (optional) is a unique shutter number index, which allows enabling/disabling from PVs.
shutter1=pvscan.LSCShutter('ASTA:LSC01','ADC:AS01:13:V',1) # (UED Drive laser)
shutter2=pvscan.LSCShutter('ASTA:LSC02','ADC:AS01:14:V',2) # (UED pump laser)
shutter3=pvscan.LSCShutter('ASTA:LSC03','ADC:AS01:15:V',3) # (UED HeNe laser)
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

# --- Experiment specifics  --------------------------
radius=PV(pvPrefix + ':RADIUS').get()
resetMotorPv=motor1
nResets=PV(pvPrefix + ':NRESETS').get()
radius2=PV(pvPrefix + ':RADIUS2').get()
#-------------------------------------------------------------

#---- Data logging --------------------------
# List of PV() objects to be monitored during scan.  
# Example: dataLogPvList=shutterGroup1.rbv + [motor1.rbv,lsrpwrPv,PV('MY:PV1')] + [PV('MY:PV2')]
dataLogPvList=[grab2.timestampRBVPv,grab2.captureRBVPv] + shutterGroup1.rbv + [motor1.rbv,motor2.rbv,motor3.rbv,motor4.rbv,motor5.rbv]
#
# Create DataLogger object.
# Argument is the list of PVs to monitor.
dataLog1=pvscan.DataLogger(dataLogPvList)
#-------------------------------------------------

### Define scan routine #####################################################

def resetLoop(grabObject='',resetMotorPv=''):
    "Does UED DAE reset routine."
    pvscan.printMsg('Starting reset loop')
    # Open drive laser shutter
    #shutter1.open.put(1)
    if shutter2.enabled:
        pvscan.printMsg('Enabling TTL In for pump shutter')
        shutter2.ttlInEnable.put(1)
    # Enable TTL In for HeNe shutter if enabled from PV. 
    if shutter3.enabled:
        pvscan.printMsg('Enabling TTL In for HeNe shutter')
        shutter3.ttlInEnable.put(1)
    pvscan.printSleep(0.5)
    if grabObject:
        if grabObject.grabFlag:
            grabObject.filenameExtras='_' + resetMotorPv.desc + '-' + '{0:08.4f}'.format(resetMotorPv.get())
            grabObject.grabImages()
    # Disable TTL In for pump shutter if enabled from PV. 
    if shutter2.enabled:
        pvscan.printMsg('Disabling TTL In for pump shutter')
        shutter2.ttlInDisable.put(1)
    # Disable TTL In for HeNe shutter if enabled from PV. 
    if shutter3.enabled:
        pvscan.printMsg('Disabling TTL In for HeNe shutter')
        shutter3.ttlInDisable.put(1)
    # Close pump and HeNe shutters, but only if enabled from PV.
    if shutter2.enabled:
        pvscan.printMsg('Closing pump shutter')
        shutter2.close.put(1)
    if shutter3.enabled:
        pvscan.printMsg('Closing HeNe shutter')
        shutter3.close.put(1)
    pvscan.printMsg('Reset loop done')

def motorScan(motor1,motor2,motor3,grabObject='',radius=0,radius2=0,resetMotorPv=''):
    "Scans motor1 from start to stop in n steps, moving motors 2 and 3 and doing a reset loop at each step."
    initialPos1=motor1.get()
    initialPos2=motor2.get()
    initialPos3=motor3.get()
    pvscan.printMsg('Starting scan')
    inc=(motor1.stop-motor1.start)/(motor1.nsteps-1)


    if not exp1.scanflag:
        nsteps = 1
    else:
        nsteps = motor1.nsteps

    for i in range(nsteps):

        if exp1.scanflag:
            # Move motor 1
            newPos0=motor1.start + i*inc
            newPos1=newPos0 + motor1.offset
            pvscan.printMsg('Moving %s to %f' % (motor1.pvname,newPos1))
            motor1.move(newPos1,timeout=30)
            # Move motor 2
            newPos2=motor2.offset + radius*math.cos(newPos0*math.pi/180) - radius2*math.sin(newPos0*math.pi/180)
            pvscan.printMsg('Moving %s to %f' % (motor2.pvname,newPos2))
            motor2.move(newPos2)
            # Move motor 3
            newPos3=motor3.offset + radius*math.sin(newPos0*math.pi/180) + radius2*(1-math.cos(newPos0*math.pi/180))
            pvscan.printMsg('Moving %s to %f' % (motor3.pvname,newPos3))
            motor3.move(newPos3)
            pvscan.printSleep(motor1.settletime,'Settling')

        resetLoop(grabObject,resetMotorPv)

    if exp1.scanflag:
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
        grab0.grabImages(5)
    # Close pump and HeNe shutters, but only if enabled from PV.
    if shutter2.enabled:
        pvscan.printMsg('Closing pump shutter')
        shutter2.close.put(1)
    if shutter3.enabled:
        pvscan.printMsg('Closing HeNe shutter')
        shutter3.close.put(1)
    # Set all shutters to fast mode
    pvscan.shutterFunction(shutterGroup1.fast,1)
    sleep(0.5)
    # Make sure shutters are closed
    #pvscan.shutterCheck(shutterRBVPVList)
    # Do motor scan
    motorScan(motor1,motor2,motor3,grab1,radius,radius2,resetMotorPv)
    # Close pump and HeNe shutters, but only if enabled from PV.
    if shutter2.enabled:
        pvscan.printMsg('Closing pump shutter')
        shutter2.close.put(1)
    if shutter3.enabled:
        pvscan.printMsg('Closing HeNe shutter')
        shutter3.close.put(1)

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

