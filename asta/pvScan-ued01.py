#!/usr/bin/env python
# For doing DAQ scans.  Logs PV data to a file while doing beam scan. Uses a supporting IOC (pvScan).
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

# PV prefix for pvScan IOC; should be passed as an argument
pvPrefix=sys.argv[1]
# Set an environment variable for so pvScan module can use it
os.environ['PVSCAN_PVPREFIX']=pvPrefix

# Import pvScan module
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/R2.0/modules/')
import pvScan

# Motors
motor1='ASTA:XPSx:m4:MOTR'  # Motor 1 actual PV
motor1Pv=PV(motor1) # Motor position PV object
motor1RBVPv=PV(motor1 + '.RBV') # Motor position RBV PV object
motor1SpeedPv=PV(motor1 + '.VELO') # Motor speed PV object
motor1Start=PV(pvPrefix + ':MOTOR1:START').get()  # for scanning
motor1Stop=PV(pvPrefix + ':MOTOR1:STOP').get()  # for scanning
motor1NSteps=PV(pvPrefix + ':MOTOR1:NSTEPS').get()  # for scanning
motor1Speed=PV(pvPrefix + ':MOTOR1:SPEED').get()  # for scanning
# Stoppers/screens
laserShutter1Pv=PV('ASTA:THSC01:SHUTTER:OC')
laserShutter2Pv=PV('ASTA:BO:2124-8:BIT5')
screenPv=PV('ASTA:BO:2114-1:BIT5')
# ADC values
lsrpwrPv=PV('ASTA:A01:ADC1:AI:CH3')
toroid0355Pv=PV('ASTA:A01:ADC1:AI:CH4')
toroid2150Pv=PV('ASTA:A01:ADC1:AI:CH5')
structureChargePv=PV('ASTA:A01:ADC1:CALC:CH1:CONV')

pause1=1.0  # sec

#---- For data logging --------------------------
#pvList=[lsrpwrPv,toroid0355Pv,toroid2150Pv,structureChargePv,laserShutter1Pv,laserShutter2Pv,screenPv,motor1SpeedPv,motor1RBVPv,motor2RBVPv,motor3RBVPv,foilstageRBVPv]
pvList=[laserShutter1Pv,laserShutter2Pv,screenPv,motor1RBVPv] # list of PVs to be monitored during scan
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
grabImagesSource='ANDOR1'
#-------------------------------------------------------------

####################################################################################################

def scanRoutine():
    "This is the scan routine"
    print pvScan.timestamp(1), 'Starting'
    pvScan.msgPv.put('Starting')
    sleep(pause1)
    # block laser
    #print pvScan.timestamp(1), 'Blocking laser'
    #laserShutter1Pv.put(0)
    #laserShutter2Pv.put(0)  # just in case
    # remove profile monitor screen
    #print pvScan.timestamp(1), 'Removing screen'
    #screenPv.put(0)
    # Scan delay stage and grab images...
    pvScan.motor1DScan(motor1Pv,motor1Start,motor1Stop,motor1RBVPv,motor1NSteps,grabImagesFlag,grabImagesN,grabImagesSource,grabImagesFilepath,grabImagesPlugin,grabImagesFilenameExtras='',settleTime=0.5)
    # block laser
    #print pvScan.timestamp(1), 'Blocking laser'
    #laserShutter1Pv.put(0)
    #laserShutter2Pv.put(0)  # just in case
    print pvScan.timestamp(1), 'Done'
    pvScan.msgPv.put('Done')

    
    

if __name__ == "__main__":
    "Do scan routine; log PV data to file as a separate thread if enabled"
    pvScan.Tee(logFilename, 'w')
    pvScan.dataFlag=1  # start logging data
    if dataEnable==1:
        datalogthread=Thread(target=pvScan.datalog,args=(dataInt,dataFilename,pvList,nPtsMax))
        datalogthread.start()
    scanRoutine()
    sleep(pause1)
    pvScan.dataFlag=0  # stop logging data

        
##################################################################################################################
        

exit

