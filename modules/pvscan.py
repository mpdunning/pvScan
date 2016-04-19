#!/usr/bin/env python
# pvScan module

from epics import PV,ca
from time import sleep,time
import datetime,math,os,sys
import matplotlib.pyplot as plt
from threading import Thread
try:
    from PIL import Image
except ImportError:
    print 'PIL not installed'

try:
    # PV prefix of pvScan IOC
    pvPrefix=os.environ['PVSCAN_PVPREFIX']
    # PV for status message
    msgPv=PV(pvPrefix + ':MSG')
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
    "Sets experiment name, filepath, and scan mode."
    def __init__(self, expname='',filepath='',scanname=''):
        if not expname:
            expname=PV(pvPrefix + ':IOC.DESC').get()
        if ' ' in expname: expname=expname.replace(' ','_')
        scanname=PV(pvPrefix + ':SCAN:NAME').get()
        if ' ' in scanname: scanname=scanname.replace(' ','_')
        if scanname: scanname = '_' + scanname
        #targetname=PV(pvPrefix + ':SCAN:TARGETNAME').get()
        #if ' ' in targetname: targetname=targetname.replace(' ','_')
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
        scanmodePv=PV(pvPrefix + ':SCAN:MODE')
        scanmode=scanmodePv.get()
        self.expname=expname
        self.scanname=scanname
        #self.targetname=targetname
        self.targetname=''
        self.filepath=filepath
        self.filepathAutoset=filepathAutoset
        self.scanflag=PV(pvPrefix + ':SCAN:ENABLE').get()
        self.scanmodePv=scanmodePv
        self.scanmode=scanmode


class Tee(object,Experiment):
    "Writes output to stdout and to log file"
    def __init__(self, filename=''):
        Experiment.__init__(self)
        logFilename=self.filepath + now + '.log'
        if not filename: filename = logFilename
        PV(pvPrefix + ':LOG:FILENAME').put(filename)
        logEnable=PV(pvPrefix + ':LOG:ENABLE').get()  # Enable/Disable log file
        self.stdout = sys.stdout
        sys.stdout = self
        self.logEnable=logEnable
        self.logFilename=logFilename
        if logEnable and os.path.exists(self.filepath):
            msgPv.put('Failed: Filepath already exists')
            raise Exception('Filepath already exists')
        elif logEnable and not os.path.exists(self.filepath): 
            os.makedirs(self.filepath)
        if logEnable:
            self.file = open(filename, 'w')
    def __del__(self):
        sys.stdout = self.stdout
        if self.logEnable:
            self.file.close()
    def write(self, data):
        if self.logEnable:
            self.file.write(data)
        self.stdout.write(data)


class ScanPv():
    "Creates a PV instance based on the value of PVTYPE PV (selected from edm display)."
    def __init__(self,pvname,pvnumber=0,rbv='',pvtype=0):
        if pvnumber and not pvname: pvname=PV(pvPrefix + ':SCANPV' + str(pvnumber) + ':PVNAME').get()
        self.pvname=pvname
        if self.pvname:
            self.pvnumber=pvnumber
            self.rbv=rbv
            # Get PV type from 'PV type' menu
            pvtypePv=PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':PVTYPE')
            if not pvtype: pvtype=pvtypePv.get()
            # Create PV instance
            if pvtype == 1:
                scanpv=Motor(self.pvname,self.pvnumber)
            elif pvtype == 2:
                scanpv=PolluxMotor(self.pvname,self.pvnumber)
            elif pvtype == 3:
                scanpv=BeckhoffMotor(self.pvname,self.pvnumber)
            elif pvtype == 4:
                scanpv=Magnet(self.pvname,self.pvnumber)
            else:
                scanpv=BasePv(self.pvname,self.pvnumber)
            self.scanpv=scanpv
            self.pvtype=pvtype
            self.pvtypePv=pvtypePv
        else:
            self.scanpv=''
   
     
class BasePv(PV):
    "BasePv class which inherits from pyEpics PV class."
    def __init__(self,pvname,pvnumber=0,rbv=''):
        # If no name is entered, raise exception and quit:
        if not pvname: 
            msgPv.put('Failed: Invalid PV')
            raise Exception('Invalid PV')
        PV.__init__(self,pvname)
        self.pvnumber=pvnumber
        if rbv: rbv=PV(rbv)
        self.rbv=rbv
        self.abort=''
        if self.pvname and self.pvnumber:
            PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':VAL.INP').put(self.pvname + ' CPP')
        if self.rbv and self.pvnumber:
            PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':RBV.INP').put(self.rbv.pvname + ' CPP')
        if self.pvnumber:
            self.desc= PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':DESC').get()
            if ' ' in self.desc: self.desc=self.desc.replace(' ','_')
            self.start= PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':START').get()
            self.stop= PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':STOP').get()
            self.nsteps= PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':NSTEPS').get()
            self.offset= PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':OFFSET').get()
            self.settletime= PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':SETTLETIME').get()
        # Test for PV validity:
        if not self.status:
            print 'PV object: ', self
            print 'PV status: ', self.status
            printMsg('PV %s not valid' % (self.pvname))
            #raise Exception('PV %s not valid' % (self.pvname))

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
            print "RBV is invalid for %s, pausing for %f seconds." %(self.pvname,timeout)
            sleep(timeout)

    def move(self,val,wait=False,delta=0.005,timeout=300.0):
        "Put with optional wait."
        PV.put(self,val)
        if wait:
            self.pvWait(val,delta,timeout)

    
class Motor(BasePv):
    "Motor class which inherits from BasePv class."
    def __init__(self,pvname,pvnumber=0):
        if pvname.endswith('.RBV'):
            rbv=pvname
            velo=pvname.rstrip('.RBV') + '.VELO'
            abort=pvname.rstrip('.RBV') + '.STOP'
            pvname=pvname.rstrip('.RBV')
        else:
            rbv=pvname + '.RBV'
            velo=pvname + '.VELO'
            abort=pvname + '.STOP'
        BasePv.__init__(self,pvname,pvnumber,rbv)
        self.velo=PV(velo)
        self.abort=PV(abort)

    def motorWait(self,val,delta=0.005,timeout=300.0):
        "Waits until PV is near readback to proceed."
        BasePv.pvWait(self,val,delta,timeout)
        #super(Motor, self).pvWait(val,delta,timeout)

    def move(self,val,wait=True,delta=0.005,timeout=360.0):
        "Put with optional wait"
        BasePv.move(self,val,wait,delta,timeout)
        #super(Motor, self).move(val,wait,delta,timeout)


class PolluxMotor(Motor):
    "Pollux Motor class which inherits from pvScan Motor class."
    def __init__(self,pvname,pvnumber=0):
        if pvname.endswith('ACTPOS'):
            rbv=pvname
            velo=':'.join(pvname.split(':')[0:2]) + ':AO:VELO'
            go=':'.join(pvname.split(':')[0:2]) + ':BO:GOABS'
            abort=':'.join(pvname.split(':')[0:2]) + ':BO:ABORT'
            pvname=':'.join(pvname.split(':')[0:2]) + ':AO:ABSMOV'
        else:
            rbv=':'.join(pvname.split(':')[0:2]) + ':AI:ACTPOS'
            velo=':'.join(pvname.split(':')[0:2]) + ':AO:VELO'
            go=':'.join(pvname.split(':')[0:2]) + ':BO:GOABS'
            abort=':'.join(pvname.split(':')[0:2]) + ':BO:ABORT'
        BasePv.__init__(self,pvname,pvnumber,rbv)
        self.velo=PV(velo)
        self.go=PV(go)
        self.abort=PV(abort)
    
    def move(self,val,wait=True,delta=0.005,timeout=360.0):
        "Put value and press Go button"
        PV.put(self,val)
        sleep(0.2)
        self.go.put(1)
        if wait:
            Motor.motorWait(self,val,delta,timeout)


class BeckhoffMotor(Motor):
    "Beckhoff Motor class which inherits from pvScan Motor class."
    def __init__(self,pvname,pvnumber=0):
        if 'CALC' in pvname:
            rbv=pvname.split(':')[0] + ':CALC:' + ':'.join(pvname.split(':')[2:4]) + ':POS:MM'
            go=pvname.split(':')[0] + ':BO:' + ':'.join(pvname.split(':')[2:4]) + ':GO:POS'
            abort=pvname.split(':')[0] + ':BO:' + ':'.join(pvname.split(':')[2:4]) + ':STOP'
            pvname=pvname.split(':')[0] + ':AO:SC:' + ':'.join(pvname.split(':')[2:4]) + ':SET:POS:MM'
        else:   
            rbv=pvname.split(':')[0] + ':CALC:' + ':'.join(pvname.split(':')[3:5]) + ':POS:MM'
            go=pvname.split(':')[0] + ':BO:' + ':'.join(pvname.split(':')[3:5]) + ':GO:POS'
            abort=pvname.split(':')[0] + ':BO:' + ':'.join(pvname.split(':')[3:5]) + ':STOP'
        BasePv.__init__(self,pvname,pvnumber,rbv)
        self.go=PV(go)
        self.abort=PV(abort)

    def move(self,val,wait=True,delta=0.005,timeout=360.0):
        "Put value and press Go button"
        PV.put(self,val)
        sleep(0.2)
        self.go.put(1)
        if wait:
            Motor.motorWait(self,val,delta,timeout)

    
class Magnet(BasePv):
    "Magnet class which inherits from BasePv class."
    def __init__(self,pvname,pvnumber=0):
        if pvname.endswith('ACT'):
            rbv=pvname
            pvname=pvname.replace('ACT','DES')
        else:
            rbv=pvname.replace('DES','ACT')
        BasePv.__init__(self,pvname,pvnumber,rbv)

    def move(self,value,wait=True,delta=0.005,timeout=300.0):
        "Put with optional wait"
        BasePv.move(self,value,wait,delta,timeout)


class Shutter(PV):
    "Shutter class which inherits from pyEpics PV class."
    def __init__(self,pvname,rbvpv='',number=0):
        PV.__init__(self,pvname)
        self.rbv=PV(rbvpv) if rbvpv else ''
        if number:
            self.enabled= PV(pvPrefix + ':SHUTTER' + str(number) + ':ENABLE').get()
        self.number=number
    def openCheck(self,val=0.5):
        sleep(0.2)
        if self.rbv.get() < val:
            printMsg('Failed: Shutter %s check' %(self.number))
            print 'Shutter: %s Value: %f' % (self.pvname,self.rbv.get())
            raise Exception('Failed: Shutter check')
    def closeCheck(self,val=0.5):
        sleep(0.2)
        if self.rbv.get() > val:
            printMsg('Failed: Shutter %s check' %(self.number))
            print 'Shutter: %s Value: %f' % (self.pvname,self.rbv.get())
            raise Exception('Failed: Shutter check')
                

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
        self.rbv=[shutter.rbv for shutter in self.shutterList]
    def open(self,val=1):
        for shutter in self.shutterList:
            if shutter.enabled:
                printMsg('Opening shutter %s' %(shutter.number))
                shutter.open.put(val)
    def close(self,val=1):
        for shutter in self.shutterList:
            if shutter.enabled:
                printMsg('Closing shutter %s' %(shutter.number))
                shutter.close.put(val)
    def soft(self,val=1):
        for shutter in self.shutterList:
            if shutter.enabled:
                printMsg('Setting shutter %s to Soft mode' %(shutter.number))
                shutter.soft.put(val)
    def fast(self,val=1):
        for shutter in self.shutterList:
            if shutter.enabled:
                printMsg('Setting shutter %s to Fast mode' %(shutter.number))
                shutter.fast.put(val)
    def ttlInEnable(self,val=1):
        for shutter in self.shutterList:
            if shutter.enabled:
                printMsg('Setting shutter %s to TTL In Enable' %(shutter.number))
                shutter.ttlInEnable.put(val)
    def ttlInDisable(self,val=1):
        for shutter in self.shutterList:
            if shutter.enabled:
                printMsg('Setting shutter %s to TTL In Disable' %(shutter.number))
                shutter.ttlInDisable.put(val)
    def openCheck(self,val=0.5):
        for shutter in self.shutterList:
            if shutter.enabled:
                sleep(0.2)
                if shutter.rbv.get() < val:
                    printMsg('Failed: Shutter %s check' %(shutter.number))
                    print 'Shutter: %s Value: %f' %(shutter.pvname,shutter.rbv.get())
                    raise Exception('Failed: Shutter check')
    def closeCheck(self,val=0.5):
        for shutter in self.shutterList:
            if shutter.enabled:
                sleep(0.2)
                if shutter.rbv.get() > val:
                    printMsg('Failed: Shutter %s check' %(shutter.number))
                    print 'Shutter: %s Value: %f' %(shutter.pvname,shutter.rbv.get())
                    raise Exception('Failed: Shutter check')



class DataLogger(Experiment, Thread):
    "Sets up pvlist and filepaths to write data and log files"
    def __init__(self,pvlist):
        Thread.__init__(self)
        self.running=True  # Datalog flag 
        Experiment.__init__(self)
        # Read file of additional monitor PVs
        pvFile=os.environ['NFSHOME'] + '/pvScan/DataLogger/pvlist-' + pvPrefix.replace(':','_')
        if os.path.isfile(pvFile):
            with open(pvFile, 'r') as file:
                pvlist2=[line.strip() for line in file if not line.startswith('#')]
                pvlist2=[PV(line) for line in pvlist2 if line]
            pvlist+=pvlist2  # Add additional monitor PVs to existing PV list
        if pvlist:
            for pv in pvlist:
                if not pv.status:
                    pvlist.remove(pv)
                    printMsg('PV %s invalid: removed from Data Logger' % (pv.pvname))
        self.pvlist=pvlist
        self.dataFilename=self.filepath + now + '.dat'
        PV(pvPrefix + ':DATA:FILENAME').put(self.dataFilename)
        self.dataEnable=PV(pvPrefix + ':DATA:ENABLE').get()  # Enable/Disable data logging
        self.dataInt=PV(pvPrefix + ':DATA:INT').get()  # Interval between PV data log points
        self.nPtsMax=1000000  # limits number of data points
        if self.dataEnable and os.path.exists(self.filepath):
            if not any(item.startswith('images') or '.log' in item for item in os.listdir(self.filepath)):
                msgPv.put('Failed: Filepath already exists')
                raise Exception('Filepath already exists')
        elif self.dataEnable and not os.path.exists(self.filepath): 
            os.makedirs(self.filepath)
        self.plotTimesFlag=PV(pvPrefix + ':DATA:PLOTTIMES').get()  # Plot average time to sample a Monitor PV
        self.formatFlag=PV(pvPrefix + ':DATA:FORMAT').get()  # Format data for nice display

    def datalog(self):
        "Logs PV data to a file; designed to be run in a separate thread. Uses self.running flag to start/stop data.  PVs must be in pvlist."
        sampleTimes=[]  # To store PV sample times for (optional) plotting.
        nPvs=len(self.pvlist)
        with open(self.dataFilename, 'w') as datafile:
            datafile.write('%-30s %s' %('PV name', 'PV description\n'))
            for pv in self.pvlist:
                if '.RBV' in pv.pvname: pv=PV(pv.pvname.replace('.RBV',''))
                if '.RVAL' in pv.pvname: pv=PV(pv.pvname.replace('.RVAL',''))
                datafile.write('%-30s %s' %(pv.pvname, str(PV(pv.pvname + '.DESC').get()) + '\n'))
            datafile.write('#####################################################################\n')
            if self.formatFlag:
                pvLists=[[] for pv in self.pvlist] + [[]]
                pvLists[0].append('Timestamp')
                for i in range(nPvs):
                    pvLists[i+1].append(self.pvlist[i].pvname)
                count=0
                while self.running and count < self.nPtsMax:
                    pvLists[0].append(str(timestamp(1)))
                    start=time()
                    for i in range(nPvs):
                        try:
                            pvLists[i+1].append(str(self.pvlist[i].value))
                        except KeyError:
                            pvLists[i+1].append('Invalid')
                        except TypeError:
                            pvLists[i+1].append('Invalid')
                    elapsedTime=time()-start
                    count+=1
                    if self.plotTimesFlag: sampleTimes.append(elapsedTime/nPvs)
                    if self.dataInt-elapsedTime > 0:
                        sleep(self.dataInt-elapsedTime)
                maxStrLens=[]
                nCols=nPvs+1
                for i in range(nCols):
                    maxStrLen=max([len(pvLists[i][j]) for j in range(len(pvLists[i]))])
                    maxStrLens.append(maxStrLen)
                try:
                    for j in range(count):
                        for i in range(nCols):
                            datafile.write('%-*s' %(maxStrLens[i]+1, pvLists[i][j]))
                        datafile.write('\n')
                except IndexError:
                    print 'DataLogger: list index out of range'
            else:
                datafile.write('%s ' %('Timestamp'))
                for pv in self.pvlist:
                    datafile.write('%s ' %(pv.pvname))
                datafile.write('\n')
                count=0
                while self.running and count < self.nPtsMax:
                    datafile.write(str(timestamp(1)) + ' ')
                    start=time()
                    for pv in self.pvlist:
                        try:
                            datafile.write('%s ' %(str(pv.value)))
                        except KeyError:
                            datafile.write('Invalid ')
                        except TypeError:
                            datafile.write('Invalid ')
                    elapsedTime=time()-start
                    datafile.write('\n')
                    count+=1
                    if self.plotTimesFlag: sampleTimes.append(elapsedTime/nPvs)
                    if self.dataInt-elapsedTime > 0:
                        sleep(self.dataInt-elapsedTime)
        if self.plotTimesFlag:
            plt.xlabel('Sample index') 
            plt.ylabel('Time [s]') 
            plt.title('Average time to sample a Monitor PV') 
            plt.plot(sampleTimes)
            plt.show()
    # These are for threading
    def run(self):
        self.datalog()
    def stop(self):
        self.running=False

               
class ImageGrabber(Experiment):
    "Sets things up to grab images"
    def __init__(self,cameraPvPrefix,nImages=0,pvlist=[],plugin='TIFF1'):
        Experiment.__init__(self)
        if not cameraPvPrefix: cameraPvPrefix=PV(pvPrefix + ':GRABIMAGES:CAMERA').get(as_string=True)
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
        if not nImages: nImages=PV(pvPrefix + ':GRABIMAGES:N').get()
        if self.scanmode and grabFlag and nImages and os.path.exists(filepath):
            msgPv.put('Failed: Filepath already exists')
            raise Exception('Filepath already exists')
        elif self.scanmode and grabFlag and nImages and not os.path.exists(filepath):
            os.makedirs(filepath)
        if plugin=='TIFF1':
            fileExt='.tif'
        elif plugin=='JPEG1':
            fileExt='.jpg'
        else:
            fileExt='.img'
        imagePvPrefix=cameraPvPrefix + ':' + plugin
        grabImagesRatePv=PV(pvPrefix + ':GRABIMAGES:RATE.INP')
        grabImagesRatePv.put(cameraPvPrefix + ':' + plugin + ':ArrayRate_RBV CPP')
        numCapturePv=PV(imagePvPrefix + ':NumCapture')
        templatePv=PV(imagePvPrefix + ':FileTemplate')
        capturePv=PV(imagePvPrefix + ':Capture')
        captureRBVPv=PV(imagePvPrefix + ':Capture_RBV.RVAL')
        acquirePv=PV(cameraPvPrefix + ':cam1:Acquire')
        acquireRBVPv=PV(cameraPvPrefix + ':cam1:Acquire_RBV.RVAL')
        lastImagePv=PV(imagePvPrefix + ':FullFileName_RBV')
        writingRBVPv=PV(imagePvPrefix + ':WriteFile_RBV.RVAL')
        timestampRBVPv=PV(imagePvPrefix + ':TimeStamp_RBV')
        filePathPv=PV(imagePvPrefix+':FilePath')
        fileNamePv=PV(imagePvPrefix+':FileName')
        self.cameraPvPrefix=cameraPvPrefix
        self.fileNamePrefix=self.cameraPvPrefix  # Make this user modifiable
        self.pvlist=pvlist
        self.plugin=plugin
        self.grabFlag=grabFlag
        self.filepath=filepath
        self.nImages=nImages
        self.fileExt=fileExt
        self.imagePvPrefix=imagePvPrefix
        self.filenameExtras=''
        self.grabImagesRatePv=grabImagesRatePv
        self.captureMode=PV(pvPrefix + ':GRABIMAGES:CAPTUREMODE').get()
        self.writeTiffTagsFlag=PV(pvPrefix + ':GRABIMAGES:TIFFTS').get()
        self.stepFlag=PV(pvPrefix + ':GRABIMAGES:STEPNUMBER').get()
        self.numCapturePv=numCapturePv
        self.templatePv=templatePv
        self.capturePv=capturePv
        self.captureRBVPv=captureRBVPv
        self.acquirePv=acquirePv
        self.acquireRBVPv=acquireRBVPv
        self.lastImagePv=lastImagePv
        self.writingRBVPv=writingRBVPv
        self.timestampRBVPv=timestampRBVPv
        self.filePathPv=filePathPv
        self.fileNamePv=fileNamePv
        

    def grabImages(self,nImages=0,grabImagesWriteSettingsFlag=1,pause=0.5):
        "Grabs n images from camera"
        nImages=nImages if nImages else self.nImages
        printMsg('Grabbing %d images from %s...' % (nImages,self.cameraPvPrefix))
        PV(self.imagePvPrefix+':EnableCallbacks').put(1)
        # PV().put() seems to need a null terminator when putting strings to waveforms.
        self.filePathPv.put(self.filepath + '\0')
        self.fileNamePv.put(self.fileNamePrefix + self.filenameExtras + '\0')
        PV(self.imagePvPrefix+':AutoIncrement').put(1)
        PV(self.imagePvPrefix+':FileWriteMode').put(1)
        PV(self.imagePvPrefix+':AutoSave').put(1)
        PV(self.imagePvPrefix+':FileNumber').put(1)
        if not self.acquireRBVPv.get(): # If camera is not acquiring...
            self.acquirePv.put(1) # Try to turn acquisition on
            sleep(0.5) # Give camera time to turn on...
            if not self.acquireRBVPv.get():
                # If unable to acquire, raise exception & quit
                printMsg('Failed: Camera not acquiring')
                raise Exception('Camera not acquiring')
        imageFilepaths=[]
        if self.captureMode: # Buffered mode (no timestamps)
            self.numCapturePv.put(nImages)
            imageFilenameTemplate='%s%s_%4.4d' + self.fileExt
            self.templatePv.put(imageFilenameTemplate + '\0')
            self.capturePv.put(1,wait=True)
            # Build a list of filenames for (optional) tiff tag file naming
            if self.writeTiffTagsFlag:
                imageFilepaths=[('%s%s%s_%04d%s' %(self.filepath,self.fileNamePrefix,self.filenameExtras,n+1,self.fileExt)) for n in range(nImages)]
            while self.captureRBVPv.get() or self.writingRBVPv.get():
                sleep(0.1)
        else: # Individual mode (with timestamps)
            self.numCapturePv.put(1)
            # Capturing loop
            for i in range(nImages):
                # Set FileTemplate PV and then grab image
                imageFilenameTemplate='%s%s_' + timestamp(1) + '_%4.4d' + self.fileExt
                self.templatePv.put(imageFilenameTemplate + '\0')
                self.capturePv.put(1,wait=True)
                # Build a list of filenames for (optional) tiff tag file naming
                if self.writeTiffTagsFlag:
                    sleep(0.010)
                    imageFilepaths.append(self.lastImagePv.get(as_string=True))
        if grabImagesWriteSettingsFlag:
            # Write camera settings to file
            settingsFile=self.filepath + 'cameraSettings-' + self.cameraPvPrefix + '-' + timestamp() + '.txt'
            with open(settingsFile, 'w') as datafile:
                datafile.write('Camera settings for ' + self.cameraPvPrefix + '\n')
                datafile.write(timestamp() + '\n')
                datafile.write('-----------------------------------------------------------\n')
                for pv in self.pvlist:
                    pv=PV(pv)
                    datafile.write(str(pv.pvname) + ' ')
                    datafile.write(str(pv.value) + '\n')
                datafile.write('\n')
        if self.writeTiffTagsFlag:
            printMsg('Timestamping filenames from Tiff tags...')
            for filepath in imageFilepaths:
                if os.path.exists(filepath):
                    try:
                        im=Image.open(filepath)
                        timestampTag=im.tag[65000][0]
                        timestampEpicsSecTag=im.tag[65002][0]
                        timestampEpicsNsecTag=im.tag[65003][0]
                        timestampFromEpics=datetime.datetime.fromtimestamp(631152000+timestampEpicsSecTag+1e-9*timestampEpicsNsecTag).strftime('%Y%m%d_%H%M%S.%f')
                        filename=filepath.split('/')[-1]
                        #filenameNew=filename.split('_')[0] + self.filenameExtras + '_' + str(timestampFromEpics) + '_' + str(timestampTag) + '_' + filename.split('_')[-1]
                        filenameNew=self.fileNamePrefix + self.filenameExtras + '_' + str(timestampFromEpics) + '_' + str(timestampTag) + '_' + filename.split('_')[-1]
                        os.rename(filepath, filepath.replace(filename, filenameNew))
                        print '%s --> %s' %(filename, filenameNew)
                    except IOError:
                        print 'writeTiffTags: IOError'
                    except NameError:
                        print 'writeTiffTags: PIL not installed'
        printSleep(pause, string='Grabbed %d images from %s: Pausing' %(nImages, self.cameraPvPrefix))


def pvNDScan(exp,pv1,pv2,grabObject=''):
    if 1 <= exp.scanmode <=2 and pv2.scanpv and not pv1.scanpv:
        pv1=pv2
        exp.scanmode=1
    if 1 <= exp.scanmode <=2 and pv1.scanpv:
        initialPos1=pv1.scanpv.get()
        inc1=(pv1.scanpv.stop-pv1.scanpv.start)/(pv1.scanpv.nsteps-1)
        if exp.scanmode==2 and pv2.scanpv:
            initialPos2=pv2.scanpv.get()
            inc2=(pv2.scanpv.stop-pv2.scanpv.start)/(pv2.scanpv.nsteps-1)
        printMsg('Scanning %s from %f to %f in %d steps' % (pv1.scanpv.pvname,pv1.scanpv.start,pv1.scanpv.stop,pv1.scanpv.nsteps))
        for i in range(pv1.scanpv.nsteps):
            newPos1=pv1.scanpv.start + i*inc1
            printMsg('Setting %s to %f' % (pv1.scanpv.pvname,newPos1))
            pv1.scanpv.move(newPos1)
            printSleep(pv1.scanpv.settletime,'Settling')
            if exp.scanmode==2 and pv2.scanpv:
                printMsg('Scanning %s from %f to %f in %d steps' % (pv2.scanpv.pvname,pv2.scanpv.start,pv2.scanpv.stop,pv2.scanpv.nsteps))
                for j in range(pv2.scanpv.nsteps):
                    newPos2=pv2.scanpv.start + j*inc2
                    printMsg('Setting %s to %f' % (pv2.scanpv.pvname,newPos2))
                    pv2.scanpv.move(newPos2)
                    printSleep(pv2.scanpv.settletime,'Settling')
                    if grabObject:
                        if grabObject.grabFlag:
                            if grabObject.stepFlag:
                                grabObject.filenameExtras= '_' + pv1.scanpv.desc + '-' + '{0:03d}'.format(i+1) + '-' + '{0:08.4f}'.format(pv1.scanpv.get()) + '_' + pv2.scanpv.desc + '-' + '{0:03d}'.format(j+1) + '-' + '{0:08.4f}'.format(pv2.scanpv.get())
                            else:
                                grabObject.filenameExtras= '_' + pv1.scanpv.desc + '-' + '{0:08.4f}'.format(pv1.scanpv.get()) + '_' + pv2.scanpv.desc + '-' + '{0:08.4f}'.format(pv2.scanpv.get())
                            ImageGrabber.grabImages(grabObject)
            else:
                if grabObject:
                    if grabObject.grabFlag:
                        if grabObject.stepFlag:
                            grabObject.filenameExtras= '_' + pv1.scanpv.desc + '-' + '{0:03d}'.format(i+1) + '-' + '{0:08.4f}'.format(pv1.scanpv.get())
                        else:
                            grabObject.filenameExtras= '_' + pv1.scanpv.desc + '-' + '{0:08.4f}'.format(pv1.scanpv.get())
                        ImageGrabber.grabImages(grabObject)
        # Move back to initial positions
        printMsg('Setting %s back to initial position: %f' %(pv1.scanpv.pvname,initialPos1))
        pv1.scanpv.move(initialPos1)
        if exp.scanmode==2 and pv2.scanpv:
            printMsg('Setting %s back to initial position: %f' %(pv2.scanpv.pvname,initialPos2))
            pv2.scanpv.move(initialPos2)
    elif exp.scanmode==3:  # Grab images only
        if grabObject:
            if grabObject.grabFlag:
                ImageGrabber.grabImages(grabObject)
    else:
        printMsg('Scan mode "None" selected or no PVs entered, continuing...')
        sleep(1)
    

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


def printScanInfo(exp,pv1,pv2=''):
    "Prints scan info"
    print '################################'
    print('Scan mode: %s' % (exp.scanmodePv.get(as_string=True)))
    if exp.scanmode==1 and pv1.pvname:
        print('PV #1 type: %s' % (pv1.pvtypePv.get(as_string=True)))
    elif exp.scanmode==1 and pv2.pvname and not pv1.pvname:
        print('PV #2 type: %s' % (pv2.pvtypePv.get(as_string=True)))
    if pv2:
        if exp.scanmode==2 and pv1.pvname and pv2.pvname:
            print('PV #1 type: %s' % (pv1.pvtypePv.get(as_string=True)))
            print('PV #2 type: %s' % (pv2.pvtypePv.get(as_string=True)))
        elif exp.scanmode==2 and pv1.pvname and not pv2.pvname:
            print('PV #1 type: %s' % (pv1.pvtypePv.get(as_string=True)))
            print('PV #2 type: No PV entered')
        elif exp.scanmode==2 and pv2.pvname and not pv1.pvname:
            print('PV #1 type: No PV entered')
            print('PV #2 type: %s' % (pv2.pvtypePv.get(as_string=True)))
    print '################################'




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

