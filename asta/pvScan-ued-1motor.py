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
motor1=pvScan.Motor('MOTR:AS01:MC01:CH8:MOTOR',1)  # Motor 1 class instance (UED Delay motor)
#
# Shutters.  Make a list for each group, to use shutterFunction()
shutter1=pvScan.LSCShutter('ASTA:LSC01') # Shutter 1 class instance (UED Drive laser)
shutter2=pvScan.LSCShutter('ASTA:LSC02') # Shutter 2 class instance (UED pump laser)
shutter3=pvScan.LSCShutter('ASTA:LSC03') # Shutter 3 class instance (UED HeNe laser)
shutterList=[shutter1,shutter2,shutter3]
shutterTTLEnablePVList=[]
shutterTTLDisablePVList=[]
shutterOpenPVList=[]
shutterClosePVList=[]
shutterSoftPVList=[]
shutterFastPVList=[]
for i in xrange(len(shutterList)):
    shutterTTLEnablePVList.append(shutterList[i].ttlInEnable)
    shutterTTLDisablePVList.append(shutterList[i].ttlInDisable)
    shutterOpenPVList.append(shutterList[i].open)
    shutterClosePVList.append(shutterList[i].close)
    shutterSoftPVList.append(shutterList[i].soft)
    shutterFastPVList.append(shutterList[i].fast)
# Shutter RBVs
shutter1RBVPv=PV('ADC:AS01:12:V')
shutter2RBVPv=PV('ADC:AS01:13:V')
shutter3RBVPv=PV('ADC:AS01:14:V')
shutterRBVPVList=[shutter1RBVPv,shutter2RBVPv,shutter3RBVPv]
#
# ADC values
#lsrpwrPv=PV('ESB:A01:ADC1:AI:CH3')
#toroid0355Pv=PV('ESB:A01:ADC1:AI:CH4')
#toroid2150Pv=PV('ESB:A01:ADC1:AI:CH5')
#structureChargePv=PV('ESB:A01:ADC1:CALC:CH1:CONV')

pause1=1.0  # sec

#---- For data logging --------------------------
pvList=[shutter1RBVPv,shutter2RBVPv,shutter3RBVPv,motor1.rbv] # list of PVs to be monitored during scan
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
    # Open shutters
    print pvScan.timestamp(1), 'Opening shutters'
    pvScan.msgPv.put('Opening shutters')
    pvScan.shutterFunction(shutterOpenPVList,1)
    # Scan delay stage and grab images...
    pvScan.motor1DScan(motor1,grabImagesFlag,grabImagesN,grabImagesSource,grabImagesFilepath,grabImagesPlugin,grabImagesFilenameExtras='',settleTime=0.5)
    # Close shutters
    print pvScan.timestamp(1), 'Closing shutters'
    pvScan.msgPv.put('Closing shutters')
    pvScan.shutterFunction(shutterClosePVList,0)
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

