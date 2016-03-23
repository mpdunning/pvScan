#!/usr/bin/env python
# pvScan module

from epics import PV,ca
from time import sleep,time
import datetime,math,os,sys

try:
    # PV prefix of pvScan IOC
    pvPrefix=os.environ['PVSCAN_PVPREFIX']
    # PV for status message
    msgPv=PV(pvPrefix + ':MSG')
    msgPv.put('Initializing...')
    print 'Initializing...'
    # PV for PID (for abort button)
    pidPV=PV(pvPrefix + ':PID')
except KeyError:
    print 'PVSCAN_PVPREFIX not defined. Continuing...'
    pvPrefix=''
    msgPv=''
    pidPV=''


##################################################################################################################

def timestamp(format='s'):
    "Formatted timestamp"
    if format=='us' or format==1:
        return(datetime.datetime.now().strftime('%Y%m%d_%H%M%S.%f'))
    elif format=='ms':
        return(datetime.datetime.now().strftime('%Y%m%d_%H%M%S.%f'[:-3]))
    elif format=='s' or format==0:
        return(datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    elif format=='today':
        return(datetime.datetime.now().strftime('%Y%m%d'))
    elif format=='year':
        return(datetime.datetime.now().strftime('%Y'))
    elif format=='month':
        return(datetime.datetime.now().strftime('%Y%m'))

# Global timestamp to be shared between classes
now=timestamp('s')
        
class Experiment:
    "Sets experiment name and filepath"
    def __init__(self, expname='',filepath='',scanname=''):
        expname=PV(pvPrefix + ':IOC.DESC').get()
        if ' ' in expname: expname=expname.replace(' ','_')
        scanname=PV(pvPrefix + ':SCAN:NAME').get()
        if ' ' in scanname: scanname=scanname.replace(' ','_')
        if scanname: scanname = '_' + scanname
        filepathAutoset=PV(pvPrefix + ':DATA:FILEPATH:AUTOSET').get()
        if not filepath:
            if filepathAutoset: 
                if os.environ['NFSHOME']:
                    filepath=os.environ['NFSHOME'] + '/pvScan/' + expname + '/' +  now + scanname + '/'
                else:
                    filepath='~/pvScan/' + expname + '/' +  now + scanname + '/'
                PV(pvPrefix + ':DATA:FILEPATH').put(filepath)  # Write filepath to PV for display
            else:
                filepath=PV(pvPrefix + ':DATA:FILEPATH').get(as_string=True)
                if not filepath.endswith('/'): filepath=filepath + '/'
                if ' ' in filepath: filepath=filepath.replace(' ','_')
        self.expname=expname
        self.scanname=scanname
        self.filepath=filepath
        self.filepathAutoset=filepathAutoset
        self.scanflag=PV(pvPrefix + ':SCAN:ENABLE').get()

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
        
class ScanPv(PV):
    "ScanPv class which inherits from pyEpics PV class."
    def __init__(self,pvname,pvnumber=0,rbv=''):
        self.pvnumber=pvnumber
        if rbv: self.rbv=PV(rbv)
        if not pvname: pvname=PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':PVNAME').get()
        PV.__init__(self,pvname)
        #if not self.status:
        #    print 'PV object: ', self
        #    print 'PV status: ', self.status
        #    printMsg('PV %s not valid' % (self.pvname))
        #    raise Exception('PV %s not valid' % (self.pvname))
        if pvnumber:
            self.desc= PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':DESC').get()
            if ' ' in self.desc: self.desc=self.desc.replace(' ','_')
            self.start= PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':START').get()
            self.stop= PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':STOP').get()
            self.nsteps= PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':NSTEPS').get()
            self.offset= PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':OFFSET').get()
            self.settletime= PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':SETTLETIME').get()

    def pvWait(self,val,delta=0.005,timeout=180.0):
        "Waits until PV is near readback to proceed."
        try:
            count=0
            pause=0.2
            while self.rbv.get() != val and count < timeout/pause:
                if math.fabs(self.rbv.get() - val) <= delta: break
                sleep(pause)
                count+=1
        except TypeError:
            print "PV %s RBV is invalid, pausing for %f seconds." %(self.pvname,timeout)
            sleep(timeout)

    def move(self,value,wait=False,timeout=300.0):
        "Put with optional wait."
        PV.put(self,value)
        if wait:
            ScanPv.pvWait(self,value,timeout=timeout)
    
    def pv1DScan(self,grabObject=''):
        "Scans pv from start to stop in n steps, optionally grabbing images at each step."
        initialPos=self.get()
        printMsg('Scanning %s from %f to %f in %d steps' % (self.pvname,self.start,self.stop,self.nsteps))
        inc=(self.stop-self.start)/(self.nsteps-1)
        for i in range(self.nsteps):
            newPos=self.start + i*inc
            printMsg('Setting %s to %f' % (self.pvname,newPos))
            self.move(newPos)
            printSleep(self.settletime,'Settling')
            if grabObject:
                if grabObject.grabFlag:
                    grabObject.filenameExtras='_' + self.desc + '-' + '{0:08.4f}'.format(self.get())
                    ImageGrabber.grabImages(grabObject)
        # Move back to initial positions
        printMsg('Setting %s back to initial position: %f' %(self.pvname,initialPos))
        self.move(initialPos)

class Motor(ScanPv):
    "Motor class which inherits from ScanPv class."
    def __init__(self,pvname,pvnumber=0):
        ScanPv.__init__(self,pvname,pvnumber)
        self.rbv=PV(pvname + '.RBV')
        self.velo=PV(pvname + '.VELO')
        self.abort=PV(pvname + '.STOP')

    def motorWait(self,val,delta=0.005,timeout=300.0):
        ScanPv.pvWait(self,val,delta=0.005,timeout=300.0)

    def move(self,value,wait=True,timeout=300.0):
        "Put with optional wait"
        ScanPv.move(self,value,wait=True,timeout=300.0)

    def motor1DScan(self,grabObject=''):
        ScanPv.pv1DScan(self,grabObject)

class PolluxMotor(Motor):
    "Motor class which inherits from pvScan Motor class."
    def __init__(self,pvname,motorNumber=0):
        Motor.__init__(self,pvname,motorNumber)
        self.rbv=PV(':'.join(pvname.split(':')[0:2]) + ':AI:ACTPOS')
        self.velo=PV(':'.join(pvname.split(':')[0:2]) + ':AO:VELO')
        self.go=PV(':'.join(pvname.split(':')[0:2]) + ':BO:GOABS')
        self.abort=PV(':'.join(pvname.split(':')[0:2]) + ':BO:ABORT')
    
    def move(self,value,wait=True,timeout=180.0):
        "Put value and press Go button"
        PV.put(self,value)
        sleep(0.2)
        self.go.put(1)
        if wait:
            Motor.motorWait(self,value,timeout=timeout)

class Shutter(PV):
    "Shutter class which inherits from pyEpics PV class."
    def __init__(self,pvname,rbvpv='',number=0):
        PV.__init__(self,pvname)
        self.rbv=PV(rbvpv) if rbvpv else ''
        if number:
            self.enabled= PV(pvPrefix + ':SHUTTER' + str(number) + ':ENABLE').get()
        self.number=number
                

class LSCShutter(Shutter):
    "Lambda SC shutter class which inherits from Shutter class."
    def __init__(self,pvname,rbvpv='',number=0):
        Shutter.__init__(self,pvname,rbvpv,number)
        self.OCStatus=PV(':'.join(pvname.split(':')[0:2]) + ':STATUS:OC')
        self.ttlInEnable=PV(':'.join(pvname.split(':')[0:2]) + ':TTL:IN:HIGH')
        self.ttlInDisable=PV(':'.join(pvname.split(':')[0:2]) + ':TTL:IN:DISABLE')
        self.open=PV(':'.join(pvname.split(':')[0:2]) + ':OC:OPEN')
        self.close=PV(':'.join(pvname.split(':')[0:2]) + ':OC:CLOSE')
        self.soft=PV(':'.join(pvname.split(':')[0:2]) + ':MODE:SOFT')
        self.fast=PV(':'.join(pvname.split(':')[0:2]) + ':MODE:FAST')

class DummyShutter(Shutter):
    "Dummy shutter class which inherits from Shutter class. For testing only."
    def __init__(self,pvname,rbvpv='',number=0):
        Shutter.__init__(self,pvname,rbvpv,number)
        self.ttlInEnable=PV(pvname)
        self.ttlInDisable=PV(pvname)
        self.open=PV(pvname)
        self.close=PV(pvname)
        self.soft=PV(pvname)
        self.fast=PV(pvname)

class ShutterGroup:
    "Sets up a group of shutters for common functions"
    def __init__(self,shutterList):
        self.shutterList=shutterList
        self.ttlInEnable=[]
        self.ttlInDisable=[]
        self.open=[]
        self.close=[]
        self.soft=[]
        self.fast=[]
        self.rbv=[]
        for i in xrange(len(self.shutterList)):
            self.ttlInEnable.append(self.shutterList[i].ttlInEnable)
            self.ttlInDisable.append(self.shutterList[i].ttlInDisable)
            self.open.append(self.shutterList[i].open)
            self.close.append(self.shutterList[i].close)
            self.soft.append(self.shutterList[i].soft)
            self.fast.append(self.shutterList[i].fast)
            self.rbv.append(self.shutterList[i].rbv)

class DataLogger(Experiment):
    "Sets up pvlist and filepaths to write data and log files"
    def __init__(self,pvlist):
        Experiment.__init__(self)
        if pvlist:
            for pv in pvlist:
                if not pv.status:
                    pvlist.remove(pv)
                    printMsg('PV %s invalid: removed' % (pv.pvname))
        self.pvlist=pvlist
        #if self.filepathAutoset:
        self.dataFilename=self.filepath + now + '.dat'
        PV(pvPrefix + ':DATA:FILENAME').put(self.dataFilename)
        self.logFilename=self.filepath + now + '.log'
        PV(pvPrefix + ':LOG:FILENAME').put(self.logFilename)
        self.dataEnable=PV(pvPrefix + ':DATA:ENABLE').get()  # Enable/Disable data logging
        self.dataInt=PV(pvPrefix + ':DATA:INT').get()  # Interval between PV data log points
        self.nPtsMax=100000  # limits number of data points
        if self.dataEnable and os.path.exists(self.filepath): 
            msgPv.put('Failed: Filepath already exists')
            raise Exception('Filepath already exists')
        elif self.dataEnable and not os.path.exists(self.filepath): 
            os.makedirs(self.filepath)

    def datalog(self):
        "Logs PV data to a file; designed to be run in a separate thread. Uses dataFlag global variable which is shared between threads. PVs must be in pvlist."
        global dataFlag
        with open(self.dataFilename, 'w') as datafile:
            datafile.write('%-30s %s' %('PV name', 'PV description\n'))
            for pv in self.pvlist:
                datafile.write('%-30s %s' %(pv.pvname, str(PV(pv.pvname + '.DESC').get()) + '\n'))
            datafile.write('#####################################################################\n')
            datafile.write('%-22s ' %('Timestamp'))
            for pv in self.pvlist:
                datafile.write(pv.pvname + ' ')
            datafile.write('\n')
            count=0
            #chids=[ca.create_channel(pv.pvname) for pv in self.pvlist] 
            #[ca.connect_channel(chid) for chid in chids] 
            while dataFlag and count < self.nPtsMax:
                datafile.write(str(timestamp(1)))
                start=time()
                datafile.write(' ')
                for pv in self.pvlist:
                #for chid in chids:
                    try:
                        datafile.write(str(pv.value) + ' ')
                        #datafile.write(str(pv.get(timeout=0.8*self.dataInt,use_monitor=False)))
                        # Must use epics.ca here since PV() timeout doesn't seem to work.
                        #chid  = ca.create_channel(pv.pvname)
                        #pvValue = ca.get(chid,timeout=0.9*self.dataInt/len(self.pvlist))
                        #pvValue = ca.get(chid)
                        #datafile.write(str(pvValue) + ' ')
                    except KeyError:
                        datafile.write('Invalid ')
                    except TypeError:
                        datafile.write('Invalid ')
                elapsedTime=time()-start
                datafile.write('\n')
                count+=1
                if self.dataInt-elapsedTime > 0:
                    sleep(self.dataInt - elapsedTime)
               
class ImageGrabber(Experiment):
    "Sets things up to grab images"
    def __init__(self,cameraPvPrefix,pvlist=[],plugin='TIFF1'):
        Experiment.__init__(self)
        if not pvlist:
            if 'ANDOR' in cameraPvPrefix:
                pvlist=['cam1:BI:NAME.DESC','cam1:AcquireTime_RBV','cam1:AndorEMGain_RBV','cam1:AndorEMGainMode_RBV','cam1:TriggerMode_RBV','cam1:ImageMode_RBV','cam1:ArrayRate_RBV','cam1:DataType_RBV','cam1:ArraySizeX_RBV','cam1:ArraySizeY_RBV','cam1:AndorADCSpeed_RBV','cam1:AndorPreAmpGain_RBV','cam1:ShutterStatus_RBV','cam1:AndorCooler','cam1:TemperatureActual']
            else:
                pvlist=['cam1:BI:NAME.DESC','cam1:AcquireTime_RBV','cam1:Gain_RBV','cam1:TriggerMode_RBV','cam1:ArrayRate_RBV','cam1:DataType_RBV','cam1:ColorMode_RBV','cam1:ArraySizeX_RBV','cam1:ArraySizeY_RBV']
            for i in xrange(len(pvlist)):
                pvlist[i]= cameraPvPrefix + ':' + pvlist[i]
        filepath=self.filepath + 'images' + '-' + cameraPvPrefix + '/' # self.filepath is inherited from Experiment class
        PV(pvPrefix + ':IMAGE:FILEPATH').put(filepath)  # Write filepath to PV for "Browse images" button
        grabFlag=PV(pvPrefix + ':GRABIMAGES:ENABLE').get()
        if grabFlag and os.path.exists(filepath):
            msgPv.put('Failed: Image filepath already exists')
            raise Exception('Image filepath already exists')
        elif grabFlag and not os.path.exists(filepath):
            os.makedirs(filepath)
        if plugin=='TIFF1':
            fileExt='.tif'
        elif plugin=='JPEG1':
            fileExt='.jpg'
        else:
            fileExt='.img'
        self.cameraPvPrefix=cameraPvPrefix
        self.pvlist=pvlist
        self.plugin=plugin
        self.grabFlag=grabFlag
        self.filepath=filepath
        self.nImages=PV(pvPrefix + ':GRABIMAGES:N').get()
        self.fileExt=fileExt
        self.imagePvPrefix=self.cameraPvPrefix + ':' + plugin
        self.filenameExtras=''
        self.captureMode=PV(pvPrefix + ':GRABIMAGES:CAPTUREMODE').get()
        

    def grabImages(self,nImages=0,grabImagesWriteSettingsFlag=1,pause=0.5):
        "Grabs n images from camera"
        self.nImages=nImages if nImages else self.nImages
        printMsg('Grabbing %d images from %s...' % (self.nImages,self.cameraPvPrefix))
        PV(self.imagePvPrefix+':EnableCallbacks').put(1)
        # PV().put() seems to need a null terminator when putting strings to waveforms.
        PV(self.imagePvPrefix+':FilePath').put(self.filepath + '\0')
        PV(self.imagePvPrefix+':FileName').put(self.cameraPvPrefix + self.filenameExtras + '\0')
        PV(self.imagePvPrefix+':AutoIncrement').put(1)
        PV(self.imagePvPrefix+':FileWriteMode').put(1)
        PV(self.imagePvPrefix+':AutoSave').put(1)
        PV(self.imagePvPrefix+':FileNumber').put(1)
        numCapturePv=PV(self.imagePvPrefix+':NumCapture')
        # Must define the following PVs before capturing loop below, or else it slows things down
        templatePv=PV(self.imagePvPrefix+':FileTemplate')
        capturePv=PV(self.imagePvPrefix+':Capture')
        acquirePv=PV(self.cameraPvPrefix+':cam1:Acquire')
        #acquireRawPv=PV(self.cameraPvPrefix+':cam1:Acquire.RVAL')
        if not acquirePv.get(): # If camera is not acquiring...
            acquirePv.put(1) # Try to turn acquisition on
            sleep(0.5) # Give camera time to turn on...
            if not acquirePv.get():
                # If unable to acquire, raise exception & quit
                printMsg('Failed: Camera not acquiring')
                raise Exception('Camera not acquiring')
        if self.captureMode: # Buffered mode (no timestamps)
            numCapturePv.put(self.nImages)
            imageFilenameTemplate='%s%s_%3.3d' + self.fileExt
            templatePv.put(imageFilenameTemplate + '\0')
            capturePv.put(1,wait=True)
        else: # Individual mode (with timestamps)
            numCapturePv.put(1)
            # Capturing loop
            for i in range(self.nImages):
                # Set FileTemplate PV and then grab image
                imageFilenameTemplate='%s%s_' + timestamp(1) + '_%3.3d' + self.fileExt
                templatePv.put(imageFilenameTemplate + '\0')
                capturePv.put(1,wait=True)
        if grabImagesWriteSettingsFlag:
            # Write camera settings to file
            settingsFile=self.filepath + 'cameraSettings-' + timestamp() + '.txt'
            with open(settingsFile, 'w') as datafile:
                datafile.write('Camera settings for ' + self.cameraPvPrefix + '\n')
                datafile.write(timestamp() + '\n')
                datafile.write('-----------------------------------------------------------\n')
                for pv in self.pvlist:
                    pv=PV(pv)
                    datafile.write(str(pv.pvname) + ' ')
                    datafile.write(str(pv.value) + '\n')
                datafile.write('\n')
        printSleep(pause)

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

def printMsg(string,pv=msgPv):
    "Prints message to stdout and to message PV."
    try:
        print '%s %s' % (timestamp(1),string)
        pv.put(string)
    except ValueError:
        print 'msgPv.put failed: string too long'

def printSleep(sleepTime,string='Pausing',pv=msgPv):
    "Prints message and pauses for sleepTime seconds."
    if sleepTime:
        message='%s for %f seconds...' % (string,sleepTime)
        printMsg(message)
        sleep(sleepTime)


#--- Self-test code -------------
if __name__ == "__main__":
    args='PV_PREFIX'
    def show_usage():
        "Prints usage"
        print 'Usage: %s %s' %(sys.argv[0], args)
    if len(sys.argv) != 2:
        show_usage()
        sys.exit(1)
    pvPrefix=sys.argv[1]
    iocPv=PV(pvPrefix + ':IOC')
    print 'IOC name PV: ',iocPv
    print 'IOC name: ',iocPv.get()        
    

##################################################################################################################
        

exit

