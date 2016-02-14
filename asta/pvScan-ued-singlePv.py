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

# Scan PVs
scanPv1=pvScan.ScanPv('SOLN:AS01:311:BCTRL',1)  # ScanPv class instance (UED Solenoid)
#scanPv1=pvScan.ScanPv('MOTR:AS01:MC02:CH7:MOTOR',1)  # ScanPv class instance (x-stage)
#
# Shutters.  Make a list for each group, to use shutterFunction()
shutter1=pvScan.LSCShutter('ASTA:LSC01') # Shutter 1 class instance (UED Drive laser)
shutter2=pvScan.LSCShutter('ASTA:LSC02') # Shutter 2 class instance (UED pump laser)
shutter3=pvScan.LSCShutter('ASTA:LSC03') # Shutter 3 class instance (UED HeNe laser)
shutterList=[shutter1,shutter2]
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
shutter1RBVPv=PV('ADC:AS01:13:V')
shutter2RBVPv=PV('ADC:AS01:14:V')
shutter3RBVPv=PV('ADC:AS01:15:V')
shutterRBVPVList=[shutter1RBVPv,shutter2RBVPv]
#
# ADC values
#lsrpwrPv=PV('ESB:A01:ADC1:AI:CH3')
#toroid0355Pv=PV('ESB:A01:ADC1:AI:CH4')
#toroid2150Pv=PV('ESB:A01:ADC1:AI:CH5')
#structureChargePv=PV('ESB:A01:ADC1:CALC:CH1:CONV')

pause1=1.0  # sec

#---- For data logging --------------------------
pvList=shutterRBVPVList + [scanPv1] # list(s) of PVs to be monitored during scan
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
# Leave grabImagesSettingsPvList=[] to use the default; otherwise add PVs with single quotes.
#grabImagesSettingsPvList=[]
grabImagesSettingsPvList=['ANDOR1:cam1:PortName_RBV','ANDOR1:cam1:ArraySizeX_RBV','ANDOR1:cam1:ArraySizeY_RBV','ANDOR1:cam1:AndorADCSpeed_RBV','ANDOR1:cam1:AcquireTime_RBV','ANDOR1:cam1:AndorEMGain_RBV','ANDOR1:cam1:AndorEMGainMode_RBV','ANDOR1:cam1:TriggerMode_RBV','ANDOR1:cam1:ShutterStatus_RBV','ANDOR1:cam1:TemperatureActual']
#-------------------------------------------------------------

####################################################################################################

def singlePvScan(scanPv,grabImagesFlag=0,grabImagesN=0,grabImagesSource='',grabImagesFilepath='~/pvScan/images/',grabImagesPlugin='TIFF1',grabImagesFilenameExtras='',grabImagesWriteSettingsFlag=1,grabImagesSettingsPvList=[]):
    "Scans pv from start to stop in n steps, optionally grabbing images at each step."
    initialPos=scanPv.get()
    pvScan.printMsg('Starting scan')
    inc=(scanPv.stop-scanPv.start)/(scanPv.nsteps-1)
    for i in range(scanPv.nsteps):
        newPos=scanPv.start + i*inc
        pvScan.printMsg('Setting %s to %f' % (scanPv.pvname,newPos))
        scanPv.put(newPos)
        pvScan.printSleep(scanPv.settletime,'Settling')
        if grabImagesFlag:
            grabImagesFilenameExtras='_Sol2-' + '{0:08.4f}'.format(scanPv.get())
            pvScan.grabImages(grabImagesN,grabImagesSource,grabImagesFilepath,grabImagesPlugin,grabImagesFilenameExtras,grabImagesWriteSettingsFlag,grabImagesSettingsPvList)
    # Move back to initial positions
    pvScan.printMsg('Setting %s back to initial position: %f' %(scanPv.pvname,initialPos))
    scanPv.put(initialPos)

def scanRoutine():
    "This is the scan routine"
    pvScan.printMsg('Starting')
    sleep(pause1)
    # Open shutters
    #pvScan.printMsg('Opening shutters')
    #pvScan.shutterFunction(shutterOpenPVList,1)
    # Scan delay stage and grab images...
    singlePvScan(scanPv1,grabImagesFlag,grabImagesN,grabImagesSource,grabImagesFilepath,grabImagesPlugin,grabImagesFilenameExtras='',grabImagesWriteSettingsFlag=1,grabImagesSettingsPvList=grabImagesSettingsPvList)
    # Close shutters
    #pvScan.printMsg('Closing shutters')
    #pvScan.shutterFunction(shutterClosePVList,0)
    pvScan.printMsg('Done')

if __name__ == "__main__":
    "Do scan routine; log PV data to file as a separate thread if enabled"
    pvScan.Tee(logFilename, 'w')
    pvScan.dataFlag=1  # Start logging data when thread starts
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

