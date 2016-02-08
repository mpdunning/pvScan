# pvScan module

from epics import caget,caput,PV
from time import sleep
import datetime,math,os,sys
import subprocess

try:
    # PV prefix of pvScan IOC
    pvPrefix=os.environ['PVSCAN_PVPREFIX']
    # PV for status message
    msgPv=PV(pvPrefix + ':MSG')
    # Get PID for abort button
    pid=os.getpid()
    pidPV=PV(pvPrefix + ':PID')
    pidPV.put(pid)
except KeyError:
    print 'Warning: PVSCAN_PVPREFIX not defined. Continuing...'
    pvPrefix=''
    msgPv=PV(pvPrefix + ':MSG')
    pidPV=PV(pvPrefix + ':PID')


##################################################################################################################

def timestamp(format=0):
    "Formatted timestamp"
    if format:
        return(datetime.datetime.now().strftime("%Y%m%d_%H%M%S.%f"))
    else:
        return(datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        
class Tee(object):
    "Writes output to stdout and to log file"
    def __init__(self, name, mode):
        self.file = open(name, mode)
        self.stdout = sys.stdout
        sys.stdout = self
    def __del__(self):
        sys.stdout = self.stdout
        self.file.close()
    def write(self, data):
        self.file.write(data)
        self.stdout.write(data)
        
class Motor(PV):
    "Motor class which inherits from pyEpics PV class."
    def __init__(self,pvname,motorNumber=0):
        PV.__init__(self,pvname)
        self.motorNumber=motorNumber
        self.rbv=PV(pvname + '.RBV')
        self.velo=PV(pvname + '.VELO')
        if motorNumber:
            self.start= PV(pvPrefix + ':MOTOR' + str(self.motorNumber) + ':START').get()
            self.stop= PV(pvPrefix + ':MOTOR' + str(self.motorNumber) + ':STOP').get()
            self.nsteps= PV(pvPrefix + ':MOTOR' + str(self.motorNumber) + ':NSTEPS').get()
            self.offset= PV(pvPrefix + ':MOTOR' + str(self.motorNumber) + ':OFFSET').get()

    def motorWait(self,val,delta=0.005,timeout=180.0):
        "Waits until motor has stopped to proceed."
        try:
            count=0
            pause=0.2
            while self.rbv.get() != val and count < timeout/pause:
                if math.fabs(self.rbv.get() - val) <= delta: break
                sleep(pause)
                count+=1
        except TypeError:
            print "Motor %s RBV is invalid, pausing for %f seconds." %(self.pvname,timeout)
            sleep(timeout)

    def put(self,value,wait=True,timeout=180.0):
        PV.put(self,value)
        if wait:
            Motor.motorWait(self,value,timeout=timeout)

class PolluxMotor(Motor):
    "Motor class which inherits from pvScan Motor class."
    def __init__(self,pvname,motorNumber=0):
        Motor.__init__(self,pvname,motorNumber)
        self.rbv=PV(':'.join(pvname.split(':')[0:2]) + ':AI:ACTPOS')
        self.velo=PV(':'.join(pvname.split(':')[0:2]) + ':AO:VELO')
        self.go=PV(':'.join(pvname.split(':')[0:2]) + ':BO:GOABS')
    
    def put(self,value,wait=True,timeout=180.0):
        Motor.put(self,value)
        self.go.put(1)

class Shutter(PV):
    "Shutter class which inherits from pyEpics PV class."
    def __init__(self,pvname):
        PV.__init__(self,pvname)

class LSCShutter(Shutter):
    "Lambda SC shutter class which inherits from Shutter class."
    def __init__(self,pvname):
        Shutter.__init__(self,pvname)
        self.OCStatus=PV(':'.join(pvname.split(':')[0:2]) + ':STATUS:OC')
        self.ttlInEnable=PV(':'.join(pvname.split(':')[0:2]) + ':TTL:IN:HIGH')
        self.ttlInDisable=PV(':'.join(pvname.split(':')[0:2]) + ':TTL:IN:DISABLE')
        self.open=PV(':'.join(pvname.split(':')[0:2]) + ':OC:OPEN')
        self.close=PV(':'.join(pvname.split(':')[0:2]) + ':OC:CLOSE')
        self.soft=PV(':'.join(pvname.split(':')[0:2]) + ':MODE:SOFT')
        self.fast=PV(':'.join(pvname.split(':')[0:2]) + ':MODE:FAST')

class DummyShutter(Shutter):
    "Dummy shutter class which inherits from Shutter class. For testing only."
    def __init__(self,pvname):
        Shutter.__init__(self,pvname)
        self.ttlInEnable=PV(pvname)
        self.ttlInDisable=PV(pvname)
        self.open=PV(pvname)
        self.close=PV(pvname)
        self.soft=PV(pvname)
        self.fast=PV(pvname)

def grabImages(grabImagesN,cameraPvPrefix,grabImagesFilepath,grabImagesPlugin='TIFF1',grabImagesFilenameExtras='',grabImagesWriteSettingsFlag=1,grabImagesSettingsPvList=[],pause=0.5):
    "Grabs n images from camera"
    print timestamp(1), 'Grabbing %d images from %s...' % (grabImagesN,cameraPvPrefix)
    msgPv.put('Grabbing ' + str(grabImagesN) + 'images...')
    if not os.path.exists(grabImagesFilepath): os.makedirs(grabImagesFilepath)
    imagePvPrefix=cameraPvPrefix + ':' + grabImagesPlugin
    if grabImagesPlugin=='TIFF1':
        fileExt='.tif'
    elif grabImagesPlugin=='JPEG1':
        fileExt='.jpg'
    else:
        fileExt='.img'
    PV(imagePvPrefix+':EnableCallbacks').put(1)
    # PV().put() doesn't seem to work for putting strings to waveforms. Use subprocess.check_call('caput') instead.
    with open(os.devnull, 'wb') as devnull:
        subprocess.check_call('caput -t -S ' + cameraPvPrefix + ':' + grabImagesPlugin + ':FilePath ' + grabImagesFilepath, shell=True, stdout=devnull)
        subprocess.check_call('caput -t -S ' + cameraPvPrefix + ':' + grabImagesPlugin + ':FileName ' + cameraPvPrefix + grabImagesFilenameExtras, shell=True, stdout=devnull)
    PV(imagePvPrefix+':AutoIncrement').put(1)
    PV(imagePvPrefix+':FileWriteMode').put(1)
    PV(imagePvPrefix+':NumCapture').put(1)
    PV(imagePvPrefix+':AutoSave').put(1)
    if PV(cameraPvPrefix+':cam1:Acquire.RVAL').get(): # Test whether camera is acquiring
        for i in range(grabImagesN):
            imageFilenameTemplate='%s%s_' + timestamp(1) + '_%3.3d' + fileExt
            PV(imagePvPrefix+':FileTemplate').put(imageFilenameTemplate)
            PV(imagePvPrefix+':Capture').put(1,wait=True)
    else: # If cam not acquiring, try to turn acquisition on
        PV(cameraPvPrefix+':cam1:Acquire').put(1) # Try to turn acquisition on
        sleep(0.5)
        if not PV(cameraPvPrefix+':cam1:Acquire.RVAL').get():
            # If unable to acquire, raise exception & quit
            print timestamp(1), 'Failed: Camera not acquiring'
            msgPv.put('Failed: Camera not acquiring')
            raise Exception('Camera not acquiring')
    if grabImagesWriteSettingsFlag:
        # Write camera settings to file
        settingsFile=grabImagesFilepath + 'cameraSettings-' + timestamp() + '.txt'
        if grabImagesSettingsPvList==[]:
            pvlist=['cam1:BI:NAME.DESC','cam1:AcquireTime','cam1:Gain','cam1:TriggerMode_RBV','cam1:ArraySizeX_RBV','cam1:SizeY_RBV','cam1:ShutterStatus_RBV','cam1:TemperatureActual']
            for i in xrange(len(pvlist)):
                pvlist[i]= cameraPvPrefix + ':' + pvlist[i]
        else:
            pvlist=grabImagesSettingsPvList
        with open(settingsFile, 'w') as datafile:
            datafile.write('Camera settings for ' + cameraPvPrefix + '\n')
            datafile.write(timestamp() + '\n')
            datafile.write('-----------------------------------------------------------\n')
            for pv in pvlist:
                datafile.write(str(PV(pv).pvname) + ' ')
                datafile.write(str(PV(pv).value) + '\n')
            datafile.write('\n')
    printSleep(pause)

def motor1DScan(motorPv,start,stop,motorRBVPv,nSteps,grabImagesFlag=0,grabImagesN=0,grabImagesSource='',grabImagesFilepath='~/pvScan/images/',grabImagesPlugin='TIFF1',grabImagesFilenameExtras='',settleTime=0.5):
    "Scans motor from start to stop in n steps, optionally grabbing images at each step."
    initialPos=motorPv.get()
    print timestamp(1), 'Starting motor scan'
    msgPv.put('Starting motor scan')
    inc=(stop-start)/(nSteps-1)
    for i in range(nSteps):
        newPos=start + i*inc
        print timestamp(1), 'Moving %s to %f' % (motorPv.pvname,newPos)
        msgPv.put('Moving motor')
        motorPv.put(newPos)
        motorWait(motorRBVPv,newPos)
        printSleep(settleTime,'Settling')
        if grabImagesFlag:
            grabImagesFilenameExtras='_MotorPos-' + str(motorPv.get())
            grabImages(grabImagesN,grabImagesSource,grabImagesFilepath,grabImagesPlugin,grabImagesFilenameExtras)
    # Move motor back to initial positions
    print timestamp(1), 'Moving %s back to initial position: %f' %(motorPv.pvname,initialPos)
    msgPv.put('Moving motor back to initial position')
    motorPv.put(initialPos)
    motorWait(motorRBVPv,initialPos)

def shutterFunction(shutterPVList,pvVal=1,wait=True):
    "Opens, Closes, or Enables/Disables TTL Input for shutters, depending on which PVs are passed in. Takes a list of PVs as an argument."
    for shutterPV in shutterPVList:
        shutterPV.put(pvVal,wait)

def shutterCheck(shutterPVList,val=1.0):
    for shutter in shutterPVList:
        if shutter.get() > val:
            print 'Shutter: %s Value: %f' % (shutter.pvname,shutter.get())
            print timestamp(1), 'Failed: Shutter not closed'
            msgPv.put('Failed: Shutter not closed')
            raise Exception('Shutter not closed')

def printSleep(sleepTime,printString='Pausing'):
    "Prints message and pauses for sleepTime seconds."
    if sleepTime:
        print timestamp(1), '%s for %f seconds...' % (printString,sleepTime)
        msgPv.put(printString + ' for ' + str(sleepTime) + ' seconds...')
        sleep(sleepTime)

def datalog(interval,filename,pvlist,nptsmax):
    "Logs PV data to a file; designed to be run in a separate thread. Uses dataFlag global variable which is shared between threads. PVs must be in pvlist."
    global dataFlag
    with open(filename, 'w') as datafile:
        datafile.write('Timestamp ')
        for pv in pvlist:
            datafile.write(pv.pvname)
            datafile.write(' ')
        datafile.write('\n')
        count=0
        while dataFlag and count < nptsmax:
            datafile.write(str(timestamp(1)))
            datafile.write(' ')
            for pv in pvlist:
                datafile.write(str(pv.value))
                datafile.write(' ')
            datafile.write('\n')
            sleep(interval)
            count+=1
               
                
    

##################################################################################################################
        

exit

