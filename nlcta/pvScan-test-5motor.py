#!/usr/bin/env python
# For doing DAQ scans.  Logs PV data to a file while doing beam scan. Uses a supporting IOC (pvScan).
# mdunning 1/7/16

from epics import caget,caput,PV
from time import sleep
import datetime,os,sys,math
from threading import Thread

args='PV_PREFIX'

def show_usage():
    "Prints usage"
    print 'Usage: %s %s' %(sys.argv[0], args)

if len(sys.argv) != 2:
    show_usage()
    sys.exit(1)

# PV prefix for pvScan IOC; should be passed as an argument
pvPrefix=sys.argv[1]
# Set an environment variable for so pvScan module can use it
os.environ['PVSCAN_PVPREFIX']=pvPrefix

# Import pvScan module
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/prod/modules/')
import pvScan

# Motors
motor1=pvScan.Motor(1,'ESB:XPS1:m3:MOTR')  # Motor 1 class instance (UED pitch motor)
motor2=pvScan.Motor(2,'ESB:XPS1:m6:MOTR')  # Motor 2 class instance (UED Y motor)
motor3=pvScan.Motor(3,'ESB:XPS1:m7:MOTR')  # Motor 3 class instance (UED Z motor)
motor4=pvScan.Motor(4,'ESB:XPS1:m4:MOTR')  # Motor 4 class instance (UED X motor)
motor5=pvScan.Motor(5,'ESB:XPS2:m1:MOTR')  # Motor 5 class instance (UED Delay motor)
#
# Shutters.  Make a list for each group, to use shutterFunction()
shutter1TTLEnablePv=PV('ESB:GP01:VAL01')
shutter2TTLEnablePv=PV('ESB:GP01:VAL02')
shutter3TTLEnablePv=PV('ESB:GP01:VAL03')
shutterTTLEnablePVList=[shutter1TTLEnablePv,shutter2TTLEnablePv,shutter3TTLEnablePv]
shutter1TTLDisablePv=PV('ESB:GP01:VAL01')
shutter2TTLDisablePv=PV('ESB:GP01:VAL02')
shutter3TTLDisablePv=PV('ESB:GP01:VAL03')
shutterTTLDisablePVList=[shutter1TTLDisablePv,shutter2TTLDisablePv,shutter3TTLDisablePv]
shutter1OpenPv=PV('ESB:GP01:VAL01')
shutter2OpenPv=PV('ESB:GP01:VAL02')
shutter3OpenPv=PV('ESB:GP01:VAL03')
shutterOpenPVList=[shutter1OpenPv,shutter2OpenPv,shutter3OpenPv]
shutter1ClosePv=PV('ESB:GP01:VAL01')
shutter2ClosePv=PV('ESB:GP01:VAL02')
shutter3ClosePv=PV('ESB:GP01:VAL03')
shutterClosePVList=[shutter1ClosePv,shutter2ClosePv,shutter3ClosePv]
shutter1RBVPv=PV('ESB:GP01:VAL01')
shutter2RBVPv=PV('ESB:GP01:VAL02')
shutter3RBVPv=PV('ESB:GP01:VAL03')
shutterRBVPVList=[shutter1RBVPv,shutter2RBVPv,shutter3RBVPv]
shutter1FastPv=PV('ESB:GP01:VAL01')
shutter2FastPv=PV('ESB:GP01:VAL02')
shutter3FastPv=PV('ESB:GP01:VAL03')
shutterFastPVList=[shutter1FastPv,shutter2FastPv,shutter3FastPv]
shutter1SoftPv=PV('ESB:GP01:VAL01')
shutter2SoftPv=PV('ESB:GP01:VAL02')
shutter3SoftPv=PV('ESB:GP01:VAL03')
shutterSoftPVList=[shutter1SoftPv,shutter2SoftPv,shutter3SoftPv]
#
# ADC values
#lsrpwrPv=PV('ESB:A01:ADC1:AI:CH3')
#toroid0355Pv=PV('ESB:A01:ADC1:AI:CH4')
#toroid2150Pv=PV('ESB:A01:ADC1:AI:CH5')
#structureChargePv=PV('ESB:A01:ADC1:CALC:CH1:CONV')

pause1=1.0  # sec

#---- For data logging --------------------------
pvList=[shutter1TTLEnablePv,shutter2TTLEnablePv,shutter3TTLEnablePv,motor1.rbv,motor2.rbv,motor3.rbv,motor4.rbv,motor5.rbv] # list of PVs to be monitored during scan
expName=PV(pvPrefix + ':IOC.DESC').get()
if ' ' in expName: expName=expName.replace(' ','_')
now=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
filepath=os.environ['NFSHOME'] + '/pvScan/' + expName + '/' + now + '/'
if not os.path.exists(filepath): os.makedirs(filepath)
filepathPv=PV(pvPrefix + ':DATA:FILEPATH')
filepathPv.put(filepath)  # Write filepath to PV for display
dataFilename=filepath + now + '.dat'
dataFilenamePv=PV(pvPrefix + ':DATA:FILENAME')
dataFilenamePv.put(dataFilename)
logFilename=filepath + now + '.log'
logFilenamePv=PV(pvPrefix + ':LOG:FILENAME')
logFilenamePv.put(logFilename)
dataEnable=PV(pvPrefix + ':DATA:ENABLE').get()  # Enable/Disable data logging
dataInt=PV(pvPrefix + ':DATA:INT').get()  # Interval between PV data log points
nPtsMax=100000  # limits number of data points
#-------------------------------------------------

# --- For grabbing images --------------------------
grabImagesFlag=PV(pvPrefix + ':GRABIMAGES:ENABLE').get()
grabImagesN=PV(pvPrefix + ':GRABIMAGES:N').get()
grabImagesFilepath=filepath + 'images/'
grabImagesPlugin='TIFF1'
grabImagesSource='13PS10'
#-------------------------------------------------------------

# --- For UED  --------------------------
resetFlag=PV(pvPrefix + ':RESET:ENABLE').get()
radius=PV(pvPrefix + ':RADIUS').get()
resetMotorPv=motor1
nResets=PV(pvPrefix + ':NRESETS').get()
#-------------------------------------------------------------

####################################################################################################

def uedDAEReset(resetMotorPv='',grabImagesFlag=0,grabImagesN=0,grabImagesSource='',grabImagesFilepath='~/pvScan/images/',grabImagesPlugin='TIFF1',grabImagesFilenameExtras='',pause=1.0):
    "Does UED DAE reset routine."
    print pvScan.timestamp(1), 'Starting reset loop'
    pvScan.msgPv.put('Starting reset loop')
    # Enable shutters 
    print pvScan.timestamp(1), 'Enabling shutters'
    pvScan.msgPv.put('Enabling shutters')
    pvScan.shutterFunction(shutterTTLEnablePVList,1)
    pvScan.printSleep(pause)
    if grabImagesFlag:
        if resetMotorPv:
            grabImagesFilenameExtras='_Pitch-' + str(resetMotorPv.get())
        pvScan.grabImages(grabImagesN,grabImagesSource,grabImagesFilepath,grabImagesPlugin,grabImagesFilenameExtras,pause)
    #printSleep(pause)
    # Disable shutters 
    print pvScan.timestamp(1), 'Disabling shutters'
    pvScan.msgPv.put('Disabling shutters')
    pvScan.shutterFunction(shutterTTLDisablePVList,0)
    # Close shutters
    print pvScan.timestamp(1), 'Closing shutters'
    pvScan.msgPv.put('Closing shutters')
    pvScan.shutterFunction(shutterClosePVList,0)
    print pvScan.timestamp(1), 'Reset loop done'
    pvScan.msgPv.put('Reset loop done')

def uedDAEMotorScan(motor1,motor2,motor3,radius=0,resetFlag=0,resetMotorPv='',grabImagesFlag=0,grabImagesN=0,grabImagesSource='',grabImagesFilepath='~/pvScan/images/',grabImagesPlugin='TIFF1',grabImagesFilenameExtras='',settleTime=0.5):
    "Scans motor1 from start to stop in n steps, moving motors 2 and 3 and doing a reset loop at each step."
    initialPos1=motor1.get()
    initialPos2=motor2.get()
    initialPos3=motor3.get()
    print pvScan.timestamp(1), 'Starting motor scan'
    pvScan.msgPv.put('Starting motor scan')
    inc=(motor1.stop-motor1.start)/(motor1.nsteps-1)
    for i in range(motor1.nsteps):
        # Move motor 1
        newPos0=motor1.start + i*inc
        newPos1=newPos0 + motor1.offset
        print pvScan.timestamp(1), 'Moving %s to %f' % (motor1.pvname,newPos1)
        pvScan.msgPv.put('Moving motor 1')
        motor1.put(newPos1,timeout=30)
        # Move motor 2
        newPos2=motor2.offset + radius*math.cos(newPos0*math.pi/180)
        print pvScan.timestamp(1), 'Moving %s to %f' % (motor2.pvname,newPos2)
        pvScan.msgPv.put('Moving motor 2')
        motor2.put(newPos2)
        # Move motor 3
        newPos3=motor3.offset + radius*math.sin(newPos0*math.pi/180)
        print pvScan.timestamp(1), 'Moving %s to %f' % (motor3.pvname,newPos3)
        pvScan.msgPv.put('Moving motor 3')
        motor3.put(newPos3)
        pvScan.printSleep(settleTime,'Settling')
        # Do reset loop if resetFlag==1
        if resetFlag:
            uedDAEReset(resetMotorPv,grabImagesFlag,grabImagesN,grabImagesSource,grabImagesFilepath,grabImagesPlugin,grabImagesFilenameExtras,pause=1.0)
    # Move motors back to initial positions
    print pvScan.timestamp(1), 'Moving %s back to initial position: %f' %(motor1.pvname,initialPos1)
    pvScan.msgPv.put('Moving motor 1 back to initial position')
    motor1.put(initialPos1)
    print pvScan.timestamp(1), 'Moving %s back to initial position: %f' %(motor2.pvname,initialPos2)
    pvScan.msgPv.put('Moving motor 2 back to initial position')
    motor2.put(initialPos2)
    print pvScan.timestamp(1), 'Moving %s back to initial position: %f' %(motor3.pvname,initialPos3)
    pvScan.msgPv.put('Moving motor 3 back to initial position')
    motor3.put(initialPos3)

def scanRoutine():
    "This is the scan routine"
    print pvScan.timestamp(1), 'Starting'
    pvScan.msgPv.put('Starting')
    # Close shutters and set to Fast Mode
    print pvScan.timestamp(1), 'Closing shutters'
    pvScan.msgPv.put('Closing shutters')
    pvScan.shutterFunction(shutterClosePVList,0)
    pvScan.shutterFunction(shutterFastPVList,0)
    sleep(0.5)
    pvScan.shutterCheck(shutterRBVPVList)
    # Do motor scan 
    uedDAEMotorScan(motor1,motor2,motor3,radius,resetFlag,resetMotorPv,grabImagesFlag,nResets,grabImagesSource,grabImagesFilepath,grabImagesPlugin,grabImagesFilenameExtras='',settleTime=0.5)
    print pvScan.timestamp(1), 'Closing shutters'
    pvScan.msgPv.put('Closing shutters')
    # Close shutters and set back to Soft Mode
    pvScan.shutterFunction(shutterClosePVList,0)
    pvScan.shutterFunction(shutterSoftPVList,0)
    print pvScan.timestamp(1), 'Done'
    pvScan.msgPv.put('Done')

    
    

if __name__ == "__main__":
    "Do scan routine; log PV data to file as a separate thread if enabled"
    pvScan.Tee(logFilename, 'w')
    pvScan.dataFlag=1  # Start logging data
    if dataEnable==1:
        datalogthread=Thread(target=pvScan.datalog,args=(dataInt,dataFilename,pvList,nPtsMax))
        datalogthread.start()
    try:
        scanRoutine()
        sleep(pause1) # Log data for a little longer
    finally:
        pvScan.dataFlag=0  # Stop logging data

        
##################################################################################################################
        

exit

