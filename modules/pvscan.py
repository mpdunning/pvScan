#!/usr/bin/env python
# pvScan module

import datetime
import math
import os
import random
import re
import sys
from time import sleep,time
from threading import Thread
import matplotlib.pyplot as plt
from epics import PV,ca,caget,caput
try:
    from PIL import Image
except ImportError:
    print 'PIL not installed'

try:
    # PV prefix of pvScan IOC
    pvPrefix = os.environ['PVSCAN_PVPREFIX']
    # PV for status message
    msgPv = PV(pvPrefix + ':MSG')
    # PV for PID (for abort button)
    pidPV = PV(pvPrefix + ':PID')
except KeyError:
    print 'PVSCAN_PVPREFIX not defined. Continuing...'
    pvPrefix = ''
    msgPv = ''
    pidPV = ''


##################################################################################################################

def timestamp(format='s'):
    """Return Formatted timestamp."""
    if format == 'us' or format == 1:
        return(datetime.datetime.now().strftime('%Y%m%d_%H%M%S.%f'))
    elif format == 'ms':
        return(datetime.datetime.now().strftime('%Y%m%d_%H%M%S.%f'[:-3]))
    elif format == 's' or format == 0:
        return(datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    elif format == 'today':
        return(datetime.datetime.now().strftime('%Y%m%d'))
    elif format == 'year':
        return(datetime.datetime.now().strftime('%Y'))
    elif format == 'month':
        return(datetime.datetime.now().strftime('%Y%m'))


# Global timestamp to be shared between classes
now = timestamp('s')

        
class Experiment:
    """Set experiment name, filepath, and scan mode."""
    def __init__(self, expname=None, filepath=None, scanname=None):
        if not expname:
            expname = PV(pvPrefix + ':IOC.DESC').get()
        if ' ' in expname: expname = expname.replace(' ', '_')
        scanname = PV(pvPrefix + ':SCAN:NAME').get()
        if ' ' in scanname: scanname = scanname.replace(' ', '_')
        if scanname: scanname = '_' + scanname
        #targetname=PV(pvPrefix + ':SCAN:TARGETNAME').get()
        #if ' ' in targetname: targetname=targetname.replace(' ','_')
        filepathAutoset = PV(pvPrefix + ':DATA:FILEPATH:AUTOSET').get()
        if not filepath:
            if filepathAutoset: 
                if os.environ['NFSHOME']:
                    filepath = (os.environ['NFSHOME'] + '/pvScan/' 
                                + expname + '/' +  now + scanname + '/')
                else:
                    filepath = '~/pvScan/' + expname + '/' +  now + scanname + '/'
                PV(pvPrefix + ':DATA:FILEPATH').put(filepath)  # Write filepath to PV for display
            else:
                filepath = PV(pvPrefix + ':DATA:FILEPATH').get(as_string=True)
                if not filepath.endswith('/'): filepath = filepath + '/'
                if ' ' in filepath: filepath = filepath.replace(' ', '_')
        scanmodePv = PV(pvPrefix + ':SCAN:MODE')
        scanmode = scanmodePv.get()
        self.expname = expname
        self.scanname = scanname
        #self.targetname = targetname
        self.targetname = ''
        self.filepath = filepath
        self.filepathAutoset = filepathAutoset
        self.scanflag = PV(pvPrefix + ':SCAN:ENABLE').get()
        self.preScanflag = PV(pvPrefix + ':SCAN:PRESCAN').get()
        self.scanmodePv = scanmodePv
        self.scanmode = scanmode


class Tee(object, Experiment):
    """Write output to stdout and to log file."""
    def __init__(self, filename=None):
        Experiment.__init__(self)
        logFilename = self.filepath + now + '.log'
        if not filename: filename = logFilename
        PV(pvPrefix + ':LOG:FILENAME').put(filename)
        logEnable = PV(pvPrefix + ':LOG:ENABLE').get()  # Enable/Disable log file
        self.stdout = sys.stdout
        sys.stdout = self
        self.logEnable = logEnable
        self.logFilename = logFilename
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
    """Create a PV instance based on the value of PVTYPE PV (selected from edm display)."""
    def __init__(self, pvname, pvnumber=None, rbv=None, pvtype=None):
        if pvnumber and not pvname: 
            pvname = PV(pvPrefix + ':SCANPV' + str(pvnumber) + ':PVNAME').get()
        self.pvname = pvname
        if self.pvname:
            self.pvnumber = pvnumber
            self.rbv = rbv
            # Get PV type from 'PV type' menu
            pvtypePv = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':PVTYPE')
            if not pvtype: pvtype = pvtypePv.get()
            # Create PV instance
            if pvtype == 1:
                scanpv = Motor(self.pvname, self.pvnumber)
            elif pvtype == 2:
                scanpv = PolluxMotor(self.pvname, self.pvnumber)
            elif pvtype == 3:
                scanpv = BeckhoffMotor(self.pvname, self.pvnumber)
            elif pvtype == 4:
                scanpv = Magnet(self.pvname, self.pvnumber)
            elif pvtype == 5:
                scanpv = Lakeshore(self.pvname, self.pvnumber)
            else:
                scanpv = BasePv(self.pvname, self.pvnumber, self.rbv)
            self.scanpv = scanpv
            self.pvtype = pvtype
            self.pvtypePv = pvtypePv
        else:
            self.scanpv = ''
   
     
class BasePv(PV):
    """BasePv class which inherits from pyEpics PV class."""
    def __init__(self, pvname, pvnumber=0, rbv=None):
        # If no name is entered, raise exception and quit:
        if not pvname: 
            msgPv.put('Failed: Invalid PV')
            raise Exception('Invalid PV')
        PV.__init__(self, pvname)
        self.pvnumber = pvnumber
        if rbv: rbv = PV(rbv)
        self.rbv = rbv
        self.abort = ''
        if self.pvname and self.pvnumber:
            PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':VAL.INP').put(self.pvname + ' CPP')
        if self.rbv and self.pvnumber:
            PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':RBV.INP').put(self.rbv.pvname + ' CPP')
        if self.pvnumber:
            self.desc = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':DESC').get()
            if ' ' in self.desc: self.desc = self.desc.replace(' ','_')
            self.start = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':START').get()
            self.stop = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':STOP').get()
            self.nsteps = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':NSTEPS').get()
            self.inc = (self.stop - self.start)/(self.nsteps - 1)
            self.randomScanflag = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':RANDSCAN').get()
            randValStr = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':RAND_VALS').get(as_string=True)
            if not self.randomScanflag:
                self.scanPos = [x for x in frange(self.start, self.stop, self.inc)]
            else:
                self.scanPos = self.shuffleString(randValStr)
            self.offset = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':OFFSET').get()
            self.settletime = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':SETTLETIME').get()
            self.delta = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':DELTA').get()
            self.pre_start = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':PRE_START').get()
            self.pre_stop = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':PRE_STOP').get()
            self.pre_nsteps = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':PRE_NSTEPS').get()
        # Test for PV validity:
        if not self.status:
            print 'PV object: ', self
            print 'PV status: ', self.status
            printMsg('PV %s not valid' % (self.pvname))
            #raise Exception('PV %s not valid' % (self.pvname))

    def pvWait(self, val, delta=0.005, timeout=180.0):
        """Wait until PV is near readback (or times out) to proceed."""
        try:
            count = 0
            pause = 0.2
            while self.rbv.get() != val and count < timeout/pause:
                if math.fabs(self.rbv.get() - val) <= delta: break
                sleep(pause)
                count += 1
        except TypeError:
            print "RBV is invalid for %s, pausing for %f seconds." % (self.pvname,timeout)
            sleep(timeout)

    def move(self, val, wait=False, delta=0.005, timeout=300.0):
        """Put with optional wait."""
        PV.put(self,val)
        if wait or self.rbv:
            if not self.delta:
                delta = delta
            else:
                delta = self.delta
            self.pvWait(val, delta, timeout)

    def shuffleString(self, strng):
        """Shuffle a string of values into a random list of floats.
        Comma, semicolon, and whitespace delimiters recognized, 
        as well as start:step:stop ranges."""
        lst = re.split(r'[;,\s]\s*', strng) 
        rangePat = re.compile(r'([-+]?\d*\.\d+|\d+):([-+]?\d*\.\d+|\d+):([-+]?\d*\.\d+|\d+)')
        lst = [expandRange(x) if rangePat.match(x) else x for x in lst]
        lst = flattenList(lst)
        lst = [float(x) for x in lst if isNumber(x)]
        random.shuffle(lst)
        return lst

 
class Motor(BasePv):
    """Motor class which inherits from BasePv class."""
    def __init__(self, pvname, pvnumber=0):
        if pvname.endswith('.RBV'):
            rbv = pvname
            velo = pvname.replace('.RBV', '.VELO')
            abort = pvname.replace('.RBV', '.STOP')
            pvname = pvname.replace('.RBV', '')
        else:
            rbv = pvname + '.RBV'
            velo = pvname + '.VELO'
            abort = pvname + '.STOP'
        BasePv.__init__(self, pvname, pvnumber, rbv)
        self.velo = PV(velo)
        self.abort = PV(abort)

    def motorWait(self, val, delta=0.005, timeout=300.0):
        """Wait until PV is near readback (or times out) to proceed."""
        BasePv.pvWait(self, val, delta, timeout)
        #super(Motor, self).pvWait(val,delta,timeout)

    def move(self, val, wait=True, delta=0.005, timeout=360.0):
        """Put with optional wait."""
        BasePv.move(self, val, wait, delta, timeout)
        #super(Motor, self).move(val,wait,delta,timeout)


class PolluxMotor(Motor):
    """Pollux Motor class which inherits from pvScan Motor class."""
    def __init__(self, pvname, pvnumber=0):
        if pvname.endswith('ACTPOS'):
            rbv = pvname
            velo = ':'.join(pvname.split(':')[0:2]) + ':AO:VELO'
            go = ':'.join(pvname.split(':')[0:2]) + ':BO:GOABS'
            abort = ':'.join(pvname.split(':')[0:2]) + ':BO:ABORT'
            pvname = ':'.join(pvname.split(':')[0:2]) + ':AO:ABSMOV'
        else:
            rbv = ':'.join(pvname.split(':')[0:2]) + ':AI:ACTPOS'
            velo = ':'.join(pvname.split(':')[0:2]) + ':AO:VELO'
            go = ':'.join(pvname.split(':')[0:2]) + ':BO:GOABS'
            abort = ':'.join(pvname.split(':')[0:2]) + ':BO:ABORT'
        BasePv.__init__(self, pvname, pvnumber, rbv)
        self.velo = PV(velo)
        self.go = PV(go)
        self.abort = PV(abort)
    
    def move(self, val, wait=True, delta=0.005, timeout=360.0):
        """Put value and press Go button."""
        PV.put(self, val)
        sleep(0.2)
        self.go.put(1)
        if wait:
            Motor.motorWait(self, val, delta, timeout)


class BeckhoffMotor(Motor):
    """Beckhoff Motor class which inherits from pvScan Motor class."""
    def __init__(self, pvname, pvnumber=0):
        if 'ESB' in pvname:
            rbv = pvname.split(':')[0] + ':CALC:' + ':'.join(pvname.split(':')[3:5]) + ':POS:MM'
            go = pvname.split(':')[0] + ':BO:' + ':'.join(pvname.split(':')[3:5]) + ':GO:POS'
            abort = pvname.split(':')[0] + ':BO:' + ':'.join(pvname.split(':')[3:5]) + ':STOP'
        elif 'UEDM' in pvname:
            rbv = pvname.split(':')[0] + ':UEDM:' + 'AI:' + pvname.split(':')[-2] + ':POS'
            go = pvname.split(':')[0] + ':UEDM:' + 'BO:' + pvname.split(':')[-2] + ':GOPOS'
            abort = pvname.split(':')[0] + ':UEDM:' + pvname.split(':')[-2] + ':STOP'
        else:
            rbv = pvname.split(':')[0] + ':CALC:' + ':'.join(pvname.split(':')[2:3]) + ':POS:MM'
            go = pvname.split(':')[0] + ':BO:' + ':'.join(pvname.split(':')[2:3]) + ':GO:POS:ABS'
            abort = pvname.split(':')[0] + ':BO:' + ':'.join(pvname.split(':')[2:3]) + ':STOP'
        BasePv.__init__(self, pvname, pvnumber, rbv)
        self.go = PV(go)
        self.abort = PV(abort)

    def move(self, val, wait=True, delta=0.005, timeout=360.0):
        """Put value and press Go button."""
        PV.put(self, val)
        sleep(0.2)
        self.go.put(1)
        if wait:
            Motor.motorWait(self, val, delta, timeout)

    
class Magnet(BasePv):
    """Magnet class which inherits from BasePv class."""
    def __init__(self, pvname, pvnumber=0):
        if pvname.endswith('ACT'):
            rbv = pvname
            pvname = pvname.replace('ACT', 'DES')
        else:
            rbv = pvname.replace('DES', 'ACT')
        BasePv.__init__(self, pvname, pvnumber, rbv)

    def move(self, value, wait=True, delta=0.005, timeout=300.0):
        "Put with optional wait"
        BasePv.move(self, value, wait, delta, timeout)


class Lakeshore(BasePv):
    """Lakeshore class which inherits from BasePv class."""
    def __init__(self, pvname, pvnumber=None):
        if pvname.endswith('RBV'):
            pvname = pvname.replace('_RBV','')
            rbv = pvname.replace('OUT', 'IN')
            rbv = rbv.replace(':SP', '')
        elif 'IN' in pvname:
            rbv = pvname
            pvname = pvname.replace('IN', 'OUT')
            pvname += ':SP' 
        else:
            rbv = pvname.replace('OUT', 'IN')
            rbv = rbv.replace(':SP', '')
        BasePv.__init__(self, pvname, pvnumber, rbv)

    def move(self, value, wait=True, delta=0.2, timeout=600.0):
        "Put with optional wait"
        BasePv.move(self, value, wait, delta, timeout)


class Shutter(PV):
    """Shutter class which inherits from pyEpics PV class."""
    def __init__(self, pvname, rbvpv=None, number=0):
        PV.__init__(self, pvname)
        self.rbv = PV(rbvpv) if rbvpv else ''
        if number:
            self.enabled = PV(pvPrefix + ':SHUTTER' + str(number) + ':ENABLE').get()
        self.number = number
    def openCheck(self, val=0.5):
        sleep(0.2)
        if self.rbv.get() < val:
            printMsg('Failed: Shutter %s check' % (self.number))
            print 'Shutter: %s Value: %f' % (self.pvname, self.rbv.get())
            raise Exception('Failed: Shutter check')
    def closeCheck(self, val=0.5):
        sleep(0.2)
        if self.rbv.get() > val:
            printMsg('Failed: Shutter %s check' % (self.number))
            print 'Shutter: %s Value: %f' % (self.pvname, self.rbv.get())
            raise Exception('Failed: Shutter check')
                

class LSCShutter(Shutter):
    """Lambda SC shutter class which inherits from Shutter class."""
    def __init__(self, pvname, rbvpv=None, number=0):
        Shutter.__init__(self, pvname, rbvpv, number)
        self.OCStatus = PV(':'.join(pvname.split(':')[0:2]) + ':STATUS:OC')
        self.ttlInEnable = PV(':'.join(pvname.split(':')[0:2]) + ':TTL:IN:HIGH')
        self.ttlInDisable = PV(':'.join(pvname.split(':')[0:2]) + ':TTL:IN:DISABLE')
        self.open = PV(':'.join(pvname.split(':')[0:2]) + ':OC:OPEN')
        self.close = PV(':'.join(pvname.split(':')[0:2]) + ':OC:CLOSE')
        self.soft = PV(':'.join(pvname.split(':')[0:2]) + ':MODE:SOFT')
        self.fast = PV(':'.join(pvname.split(':')[0:2]) + ':MODE:FAST')


class DummyShutter(Shutter):
    """Dummy shutter class which inherits from Shutter class. Use for testing only."""
    def __init__(self, pvname, rbvpv=None, number=0):
        Shutter.__init__(self, pvname, rbvpv, number)
        self.OCStatus = PV(pvname)
        self.ttlInEnable = PV(pvname)
        self.ttlInDisable = PV(pvname)
        self.open = PV(pvname)
        self.close = PV(pvname)
        self.soft = PV(pvname)
        self.fast = PV(pvname)


class ShutterGroup:
    """Set up a group of shutters for common functions."""
    def __init__(self, shutterList):
        self.shutterList = shutterList
        self.rbv = [shutter.rbv for shutter in self.shutterList]
    def open(self, val=1):
        for shutter in self.shutterList:
            if shutter.enabled:
                printMsg('Opening shutter %s' % (shutter.number))
                shutter.open.put(val)
    def close(self, val=1):
        for shutter in self.shutterList:
            if shutter.enabled:
                printMsg('Closing shutter %s' % (shutter.number))
                shutter.close.put(val)
    def soft(self, val=1):
        for shutter in self.shutterList:
            if shutter.enabled:
                printMsg('Setting shutter %s to Soft mode' % (shutter.number))
                shutter.soft.put(val)
    def fast(self, val=1):
        for shutter in self.shutterList:
            if shutter.enabled:
                printMsg('Setting shutter %s to Fast mode' % (shutter.number))
                shutter.fast.put(val)
    def ttlInEnable(self, val=1):
        for shutter in self.shutterList:
            if shutter.enabled:
                printMsg('Setting shutter %s to TTL In Enable' % (shutter.number))
                shutter.ttlInEnable.put(val)
    def ttlInDisable(self, val=1):
        for shutter in self.shutterList:
            if shutter.enabled:
                printMsg('Setting shutter %s to TTL In Disable' % (shutter.number))
                shutter.ttlInDisable.put(val)
    def openCheck(self, val=0.5):
        for shutter in self.shutterList:
            if shutter.enabled:
                sleep(0.2)
                if shutter.rbv.get() < val:
                    printMsg('Failed: Shutter %s check' % (shutter.number))
                    print 'Shutter: %s Value: %f' % (shutter.pvname, shutter.rbv.get())
                    raise Exception('Failed: Shutter check')
    def closeCheck(self, val=0.5):
        for shutter in self.shutterList:
            if shutter.enabled:
                sleep(0.2)
                if shutter.rbv.get() > val:
                    printMsg('Failed: Shutter %s check' % (shutter.number))
                    print 'Shutter: %s Value: %f' % (shutter.pvname, shutter.rbv.get())
                    raise Exception('Failed: Shutter check')



class DataLogger(Experiment, Thread):
    """Set up pvlist and filepaths to write data and log files."""
    def __init__(self, pvlist):
        Thread.__init__(self)
        self.running = True  # Datalog flag 
        Experiment.__init__(self)
        # Read file of additional monitor PVs
        pvFile = os.environ['NFSHOME'] + '/pvScan/DataLogger/pvlist-' + pvPrefix.replace(':','_')
        if os.path.isfile(pvFile):
            with open(pvFile, 'r') as file:
                pvlist2 = [line.strip() for line in file if not line.startswith('#')]
                pvlist2 = [PV(line) for line in pvlist2 if line]
            pvlist += pvlist2  # Add additional monitor PVs to existing PV list
        if pvlist:
            pvlist = [pv for pv in pvlist if pv]  # Remove "None" PVs
            for pv in pvlist:
                if not pv.status:
                    pvlist.remove(pv)
                    printMsg('PV %s invalid: removed from Data Logger' % (pv.pvname))
        self.pvlist = pvlist
        self.dataFilename = self.filepath + now + '.dat'
        PV(pvPrefix + ':DATA:FILENAME').put(self.dataFilename)
        self.dataEnable = PV(pvPrefix + ':DATA:ENABLE').get()  # Enable/Disable data logging
        self.dataInt = PV(pvPrefix + ':DATA:INT').get()  # Interval between PV data log points
        self.nPtsMax = 1000000  # limits number of data points
        if self.dataEnable and os.path.exists(self.filepath):
            if not any(item.startswith('images') or '.log' in item for item in os.listdir(self.filepath)):
                msgPv.put('Failed: Filepath already exists')
                raise Exception('Filepath already exists')
        elif self.dataEnable and not os.path.exists(self.filepath): 
            os.makedirs(self.filepath)
        self.plotTimesFlag = PV(pvPrefix + ':DATA:PLOTTIMES').get()  # Plot average time to sample a Monitor PV
        self.formatFlag = PV(pvPrefix + ':DATA:FORMAT').get()  # Format data for nice display

    def datalog(self):
        """Logs PV data to a file.
        Designed to be run in a separate thread. 
        Uses self.running flag to start/stop data.
        PVs must be in pvlist."""
        sampleTimes = []  # To store PV sample times for (optional) plotting.
        nPvs = len(self.pvlist)
        with open(self.dataFilename, 'w') as datafile:
            datafile.write('%-30s %s' % ('PV name', 'PV description\n'))
            for pv in self.pvlist:
                if '.RBV' in pv.pvname: pv = PV(pv.pvname.replace('.RBV', ''))
                if '.RVAL' in pv.pvname: pv = PV(pv.pvname.replace('.RVAL', ''))
                datafile.write('%-30s %s' % (pv.pvname, str(PV(pv.pvname + '.DESC').get()) + '\n'))
            datafile.write('#####################################################################\n')
            if self.formatFlag:
                pvLists = [[] for pv in self.pvlist] + [[]]
                pvLists[0].append('Timestamp')
                for i in range(nPvs):
                    pvLists[i+1].append(self.pvlist[i].pvname)
                count = 0
                while self.running and count < self.nPtsMax:
                    pvLists[0].append(str(timestamp(1)))
                    start = time()
                    for i in range(nPvs):
                        try:
                            pvLists[i+1].append(str(self.pvlist[i].value))
                        except KeyError:
                            pvLists[i+1].append('Invalid')
                        except TypeError:
                            pvLists[i+1].append('Invalid')
                    elapsedTime = time() - start
                    count += 1
                    if self.plotTimesFlag: sampleTimes.append(elapsedTime/nPvs)
                    if self.dataInt - elapsedTime > 0:
                        sleep(self.dataInt - elapsedTime)
                maxStrLens = []
                nCols = nPvs + 1
                for i in range(nCols):
                    maxStrLen = max([len(pvLists[i][j]) for j in range(len(pvLists[i]))])
                    maxStrLens.append(maxStrLen)
                try:
                    for j in range(count):
                        for i in range(nCols):
                            datafile.write('%-*s' %(maxStrLens[i]+1, pvLists[i][j]))
                        datafile.write('\n')
                except IndexError:
                    print 'DataLogger: list index out of range'
            else:
                datafile.write('%s ' % ('Timestamp'))
                for pv in self.pvlist:
                    datafile.write('%s ' % (pv.pvname))
                datafile.write('\n')
                count = 0
                while self.running and count < self.nPtsMax:
                    datafile.write(str(timestamp(1)) + ' ')
                    start = time()
                    for pv in self.pvlist:
                        try:
                            datafile.write('%s ' % (str(pv.value)))
                        except KeyError:
                            datafile.write('Invalid ')
                        except TypeError:
                            datafile.write('Invalid ')
                    elapsedTime = time() - start
                    datafile.write('\n')
                    count += 1
                    if self.plotTimesFlag: sampleTimes.append(elapsedTime/nPvs)
                    if self.dataInt - elapsedTime > 0:
                        sleep(self.dataInt - elapsedTime)
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
        self.running = False


class ImageGrabber(Experiment):
    """Create an image grabber class instance."""
    def __init__(self, cameraPvPrefix, nImages=0, pvlist=[], plugin='TIFF1'):
        if not cameraPvPrefix: 
            cameraPvPrefix = PV(pvPrefix + ':GRABIMAGES:CAMERA').get(as_string=True)
        if 'DirectD' in cameraPvPrefix:
            grabber = DDGrabber(cameraPvPrefix)
        else:
            grabber = ADGrabber(cameraPvPrefix, nImages, pvlist, plugin)
        self.grabber = grabber


class DDGrabber(Experiment):
    """UED Direct Detector grabber."""
    def __init__(self, cameraPvPrefix):
        Experiment.__init__(self)
        self.cameraPvPrefix = cameraPvPrefix
        self.grabFlag = PV(pvPrefix + ':GRABIMAGES:ENABLE').get()
        self.grabSeq2Flag = PV(pvPrefix + ':GRABIMAGES:SEQ2ENABLE').get() # Grab second image sequence after first 
        self.grabSeq2Delay = PV(pvPrefix + ':GRABIMAGES:SEQ2DELAY').get() # Delay between 1st and 2nd sequence
        self.stepFlag = PV(pvPrefix + ':GRABIMAGES:STEPNUMBER').get() # Write step number into filename
        self.dataTime = PV(pvPrefix + ':GRABIMAGES:DATATIME').get() # Data capture time for DirectD
        self.dataStartStopPv = PV('UED:TST:FILEWRITER:CMD')  # DataWriter start/stop PV
        self.dataStatusPv = PV('UED:TST:FILEWRITER:STATUS')  # DataWriter status PV
        self.dataFilenamePv = PV('UED:TST:FILEWRITER:PATH')  # DataWriter filename template PV
        self.nImages2 = None
        self.filenameExtras = ''
        self.timestampRBVPv = None
        self.captureRBVPv = None

    def dataWriterStatus(self):
        """Return status of dataWriter."""
        status = self.dataStatusPv.get()
        if status:
            printMsg('DataWriter status is: ON')
        else:
            printMsg('DataWriter status is: OFF')
        return status
        
    def grabImages(self, nImages=0):
        """Set filepath PV, turn on/off dataWriter."""
        #filenameTemplate='%s/%s%s_%s' %(timestamp('today'), self.expname, self.filenameExtras, timestamp(1))
        if self.filenameExtras.startswith('_'):
            self.filenameExtras = self.filenameExtras.replace('_', '')
        filenameTemplate = ('%s/%s/%s_%s' %(timestamp('today'), self.expname, 
                            self.filenameExtras, timestamp(1)))
        self.dataFilenamePv.put(filenameTemplate + '\0')
        printMsg('Writing %s data for %d seconds...' % (self.cameraPvPrefix, self.dataTime))
        print 'DirectD filepath: ', filenameTemplate
        self.dataStartStopPv.put(1)
        sleep(0.25)
        self.dataStartStopPv.put(1)
        sleep(0.25)
        self.dataWriterStatus()
        sleep(self.dataTime)
        self.dataStartStopPv.put(0)
        sleep(0.25)
        self.dataStartStopPv.put(0)
        sleep(0.25)
        self.dataWriterStatus()
        printMsg('Done Writing %s data.' % (self.cameraPvPrefix))

    def abort(self):
        self.dataStartStopPv.put(0)
        sleep(0.25)
        self.dataStartStopPv.put(0)
        sleep(0.25)
        self.dataWriterStatus()
        


               
class ADGrabber(Experiment):
    """AreaDetector grabber."""
    def __init__(self, cameraPvPrefix, nImages=0, pvlist=[], plugin='TIFF1'):
        Experiment.__init__(self)
        if not cameraPvPrefix: 
            cameraPvPrefix = PV(pvPrefix + ':GRABIMAGES:CAMERA').get(as_string=True)
        if not pvlist:
            if 'ANDOR' in cameraPvPrefix:
                pvlist = ['cam1:BI:NAME.DESC', 'cam1:AcquireTime_RBV',
                        'cam1:AndorEMGain_RBV', 'cam1:AndorEMGainMode_RBV',
                        'cam1:TriggerMode_RBV', 'cam1:ImageMode_RBV',
                        'cam1:ArrayRate_RBV', 'cam1:DataType_RBV',
                        'cam1:ArraySizeX_RBV', 'cam1:ArraySizeY_RBV',
                        'cam1:AndorADCSpeed_RBV', 'cam1:AndorPreAmpGain_RBV',
                        'cam1:ShutterStatus_RBV', 'cam1:AndorCooler',
                        'cam1:TemperatureActual']
            else:
                pvlist = ['cam1:BI:NAME.DESC', 'cam1:AcquireTime_RBV',
                        'cam1:Gain_RBV', 'cam1:TriggerMode_RBV',
                        'cam1:ArrayRate_RBV', 'cam1:DataType_RBV',
                        'cam1:ColorMode_RBV', 'cam1:ArraySizeX_RBV',
                        'cam1:ArraySizeY_RBV']
            for i in xrange(len(pvlist)):
                pvlist[i] = cameraPvPrefix + ':' + pvlist[i]
        filepath = self.filepath + 'images' + '-' + cameraPvPrefix + '/' 
                # self.filepath is inherited from Experiment class
        PV(pvPrefix + ':IMAGE:FILEPATH').put(filepath)  # Write filepath to PV for "Browse images" button
        grabFlag = PV(pvPrefix + ':GRABIMAGES:ENABLE').get()
        if not nImages: nImages = PV(pvPrefix + ':GRABIMAGES:N').get()
        if self.scanmode and grabFlag and nImages and os.path.exists(filepath):
            msgPv.put('Failed: Filepath already exists')
            raise Exception('Filepath already exists')
        elif self.scanmode and grabFlag and nImages and not os.path.exists(filepath):
            os.makedirs(filepath)
        if plugin == 'TIFF1':
            fileExt = '.tif'
        elif plugin == 'JPEG1':
            fileExt = '.jpg'
        else:
            fileExt = '.img'
        imagePvPrefix = cameraPvPrefix + ':' + plugin
        grabImagesRatePv = PV(pvPrefix + ':GRABIMAGES:RATE.INP')
        grabImagesRatePv.put(cameraPvPrefix + ':' + plugin + ':ArrayRate_RBV CPP')
        numCapturePv = PV(imagePvPrefix + ':NumCapture')
        templatePv = PV(imagePvPrefix + ':FileTemplate')
        capturePv = PV(imagePvPrefix + ':Capture')
        captureRBVPv = PV(imagePvPrefix + ':Capture_RBV.RVAL')
        acquirePv = PV(cameraPvPrefix + ':cam1:Acquire')
        acquireRBVPv = PV(cameraPvPrefix + ':cam1:Acquire_RBV.RVAL')
        lastImagePv = PV(imagePvPrefix + ':FullFileName_RBV')
        writingRBVPv = PV(imagePvPrefix + ':WriteFile_RBV.RVAL')
        timestampRBVPv = PV(imagePvPrefix + ':TimeStamp_RBV')
        filePathPv = PV(imagePvPrefix+':FilePath')
        fileNamePv = PV(imagePvPrefix+':FileName')
        self.cameraPvPrefix = cameraPvPrefix
        self.fileNamePrefix = self.cameraPvPrefix  # Make this user modifiable
        self.pvlist = pvlist
        self.plugin = plugin
        self.grabFlag = grabFlag
        self.filepath = filepath
        self.nImages = nImages
        self.fileExt = fileExt
        self.imagePvPrefix = imagePvPrefix
        self.filenameExtras = ''
        self.grabImagesRatePv = grabImagesRatePv
        self.captureMode = PV(pvPrefix + ':GRABIMAGES:CAPTUREMODE').get()
        self.writeTiffTagsFlag = PV(pvPrefix + ':GRABIMAGES:TIFFTS').get() # Tiff tag timestamps
        self.stepFlag = PV(pvPrefix + ':GRABIMAGES:STEPNUMBER').get() # Write step number into filename
        self.grabSeq2Flag = PV(pvPrefix + ':GRABIMAGES:SEQ2ENABLE').get() # Grab second image sequence after first 
        self.grabSeq2Delay = PV(pvPrefix + ':GRABIMAGES:SEQ2DELAY').get() 
        self.nImages2 = PV(pvPrefix + ':GRABIMAGES:N2').get() # N images for second sequence
        self.numCapturePv = numCapturePv
        self.templatePv = templatePv
        self.capturePv = capturePv
        self.captureRBVPv = captureRBVPv
        self.acquirePv = acquirePv
        self.acquireRBVPv = acquireRBVPv
        self.lastImagePv = lastImagePv
        self.writingRBVPv = writingRBVPv
        self.timestampRBVPv = timestampRBVPv
        self.filePathPv = filePathPv
        self.fileNamePv = fileNamePv
        

    def grabImages(self, nImages=0, grabImagesWriteSettingsFlag=1, pause=0.5):
        """Grabs n images from camera."""
        nImages = nImages if nImages else self.nImages
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
        imageFilepaths = []
        if self.captureMode: # Buffered mode (no timestamps)
            self.numCapturePv.put(nImages)
            imageFilenameTemplate = '%s%s_%4.4d' + self.fileExt
            self.templatePv.put(imageFilenameTemplate + '\0')
            self.capturePv.put(1, wait=True)
            # Build a list of filenames for (optional) tiff tag file naming
            if self.writeTiffTagsFlag:
                imageFilepaths = ([('%s%s%s_%04d%s' %(self.filepath, self.fileNamePrefix, 
                        self.filenameExtras, n+1, self.fileExt)) for n in range(nImages)])
            while self.captureRBVPv.get() or self.writingRBVPv.get():
                sleep(0.1)
        else: # Individual mode (with timestamps)
            self.numCapturePv.put(1)
            # Capturing loop
            for i in range(nImages):
                # Set FileTemplate PV and then grab image
                imageFilenameTemplate = '%s%s_' + timestamp(1) + '_%4.4d' + self.fileExt
                self.templatePv.put(imageFilenameTemplate + '\0')
                self.capturePv.put(1, wait=True)
                # Build a list of filenames for (optional) tiff tag file naming
                if self.writeTiffTagsFlag:
                    sleep(0.010)
                    imageFilepaths.append(self.lastImagePv.get(as_string=True))
        if grabImagesWriteSettingsFlag:
            # Write camera settings to file
            settingsFile = (self.filepath + 'cameraSettings-' + 
                    self.cameraPvPrefix + '-' + timestamp() + '.txt')
            with open(settingsFile, 'w') as datafile:
                datafile.write('Camera settings for ' + self.cameraPvPrefix + '\n')
                datafile.write(timestamp() + '\n')
                datafile.write('-----------------------------------------------------------\n')
                for pv in self.pvlist:
                    pv = PV(pv)
                    datafile.write(str(pv.pvname) + ' ')
                    datafile.write(str(pv.value) + '\n')
                datafile.write('\n')
        if self.writeTiffTagsFlag:
            printMsg('Timestamping filenames from Tiff tags...')
            for filepath in imageFilepaths:
                if os.path.exists(filepath):
                    try:
                        im = Image.open(filepath)
                        timestampTag = im.tag[65000][0]
                        timestampEpicsSecTag = im.tag[65002][0]
                        timestampEpicsNsecTag = im.tag[65003][0]
                        timestampFromEpics = (datetime.datetime.fromtimestamp(631152000 + 
                                timestampEpicsSecTag + 
                                1e-9*timestampEpicsNsecTag).strftime('%Y%m%d_%H%M%S.%f'))
                        filename = filepath.split('/')[-1]
                        filenameNew = (self.fileNamePrefix + self.filenameExtras + 
                                '_' + str(timestampFromEpics) + '_' + str(timestampTag) + 
                                '_' + filename.split('_')[-1])
                        os.rename(filepath, filepath.replace(filename, filenameNew))
                        print '%s --> %s' %(filename, filenameNew)
                    except IOError:
                        print 'writeTiffTags: IOError'
                    except NameError:
                        print 'writeTiffTags: PIL not installed'
        printSleep(pause, string='Grabbed %d images from %s: Pausing' % 
                  (nImages, self.cameraPvPrefix))

    def abort(self):
        self.capturePv.put(0)


def pvNDScan(exp, pv1, pv2, grabObject=None, shutter1=None, shutter2=None, shutter3=None):
    """Do 0-, 1-, or 2-D scan and grab images at each step (or do nothing and bail)."""
    if 1 <= exp.scanmode <=2 and pv2.scanpv and not pv1.scanpv:  # 1- or 2-D scan
        pv1 = pv2
        exp.scanmode = 1
    if 1 <= exp.scanmode <=2 and pv1.scanpv:
        initialPos1 = pv1.scanpv.get()
        if exp.scanmode == 2 and pv2.scanpv:
            initialPos2 = pv2.scanpv.get()
        # Do pre-scan if enabled from PV
        if exp.preScanflag: preScan(exp, pv1, grabObject)
        # Scan PV #1
        printMsg('Scanning %s from %f to %f in %d steps' % 
                (pv1.scanpv.pvname, pv1.scanpv.start, pv1.scanpv.stop, len(pv1.scanpv.scanPos)))
        stepCount1 = 0
        for x in pv1.scanpv.scanPos:
            printMsg('Setting %s to %f' % (pv1.scanpv.pvname, x))
            pv1.scanpv.move(x)
            stepCount1 += 1
            printSleep(pv1.scanpv.settletime,'Settling')
            # Scan PV #2
            if exp.scanmode == 2 and pv2.scanpv:
                printMsg('Scanning %s from %f to %f in %d steps' % 
                        (pv2.scanpv.pvname, pv2.scanpv.start, pv2.scanpv.stop, len(pv2.scanpv.scanPos)))
                stepCount2 = 0
                for y in pv2.scanpv.scanPos:
                    printMsg('Setting %s to %f' % (pv2.scanpv.pvname, y))
                    pv2.scanpv.move(y)
                    stepCount2 += 1
                    printSleep(pv2.scanpv.settletime, 'Settling')
                    if grabObject:
                        if grabObject.grabber.grabFlag:
                            if grabObject.grabber.stepFlag:
                                grabObject.grabber.filenameExtras = ('_' + pv1.scanpv.desc + 
                                        '-' + '{0:03d}'.format(stepCount1) + '-' + 
                                        '{0:08.4f}'.format(pv1.scanpv.get()) + '_' + 
                                        pv2.scanpv.desc + '-' + '{0:03d}'.format(stepCount2) + 
                                        '-' + '{0:08.4f}'.format(pv2.scanpv.get()))
                            else:
                                grabObject.grabber.filenameExtras = ('_' + pv1.scanpv.desc + 
                                        '-' + '{0:08.4f}'.format(pv1.scanpv.get()) + 
                                        '_' + pv2.scanpv.desc + '-' + 
                                        '{0:08.4f}'.format(pv2.scanpv.get()))
                            if grabObject.grabber.grabSeq2Flag:
                                pumpedGrabSequence(grabObject, shutter1, shutter2, shutter3)
                            grabObject.grabber.grabImages()
            else:
                if grabObject:
                    if grabObject.grabber.grabFlag:
                        if grabObject.grabber.stepFlag:
                            grabObject.grabber.filenameExtras = ('_' + pv1.scanpv.desc + 
                                    '-' + '{0:03d}'.format(stepCount1) + '-' + 
                                    '{0:08.4f}'.format(pv1.scanpv.get()))
                        else:
                            grabObject.grabber.filenameExtras = ('_' + pv1.scanpv.desc + 
                                    '-' + '{0:08.4f}'.format(pv1.scanpv.get()))
                        if grabObject.grabber.grabSeq2Flag:
                            pumpedGrabSequence(grabObject, shutter1, shutter2, shutter3)
                        grabObject.grabber.grabImages()
        # Move back to initial positions
        printMsg('Setting %s back to initial position: %f' % (pv1.scanpv.pvname,initialPos1))
        pv1.scanpv.move(initialPos1)
        if exp.scanmode == 2 and pv2.scanpv:
            printMsg('Setting %s back to initial position: %f' % (pv2.scanpv.pvname,initialPos2))
            pv2.scanpv.move(initialPos2)
    elif exp.scanmode == 3:  # Grab images only
        if grabObject:
            if grabObject.grabber.grabFlag:
                if grabObject.grabber.grabSeq2Flag:
                    pumpedGrabSequence(grabObject, shutter1, shutter2, shutter3)
                grabObject.grabber.grabImages()
    else:
        printMsg('Scan mode "None" selected or no PVs entered, continuing...')
        sleep(1)
   
def pumpedGrabSequence(grabObject, shutter1, shutter2, shutter3):
    """Do a pumped/static image grab sequence."""
    debug = 0
    printMsg('Starting pumped image sequence')
    sleep(0.25)
    shutter1Stat = shutter1.OCStatus.get()
    shutter2Stat = shutter2.OCStatus.get()
    shutter3Stat = shutter3.OCStatus.get()
    #print shutter1Stat, shutter1.OCStatus.get()
    if debug: 
        print ('shutter stats: %s, %s, %s' 
                % (shutter1.OCStatus.get(), shutter2.OCStatus.get(), shutter3.OCStatus.get()))
    printMsg('Opening shutters 1, 2 and 3')
    shutter1.open.put(1)
    shutter2.open.put(1)
    shutter3.open.put(1)
    sleep(0.25)
    if debug: 
        print ('shutter stats: %s, %s, %s'
                % (shutter1.OCStatus.get(), shutter2.OCStatus.get(), shutter3.OCStatus.get()))
    if debug: print grabObject.grabber.filenameExtras
    if 'Static' in grabObject.grabber.filenameExtras:
        grabObject.grabber.filenameExtras = grabObject.grabber.filenameExtras.replace('Static', 'Pumped')
    else:
        grabObject.grabber.filenameExtras = '_' + 'Pumped' + grabObject.grabber.filenameExtras
    if debug: print grabObject.grabber.filenameExtras
    grabObject.grabber.grabImages(grabObject.grabber.nImages2)
    printMsg('Returning shutters to initial state')
    shutter1.open.put(1) if shutter1Stat == 1 else shutter1.close.put(0)
    shutter2.open.put(1) if shutter2Stat == 1 else shutter2.close.put(0)
    shutter3.open.put(1) if shutter3Stat == 1 else shutter3.close.put(0)
    sleep(0.25)
    #print shutter1Stat, shutter1.OCStatus.get()
    if debug: 
        print ('shutter stats: %s, %s, %s' 
                % (shutter1.OCStatus.get(), shutter2.OCStatus.get(), shutter3.OCStatus.get()))
    if debug: print grabObject.grabber.filenameExtras
    if 'Pumped' in grabObject.grabber.filenameExtras:
        grabObject.grabber.filenameExtras = grabObject.grabber.filenameExtras.replace('Pumped', 'Static')
    else:
        grabObject.grabber.filenameExtras = '_' + 'Static'
    if debug: print grabObject.grabber.filenameExtras
    printMsg('Finished pumped image sequence')
    printSleep(grabObject.grabber.grabSeq2Delay)


def preScan(exp, pv1, grabObject=None):
    """Does pre-scan before main scan.  Pre-scan flag and scan parameters are set from PVs."""
    #inc1 = (pv1.scanpv.pre_stop - pv1.scanpv.pre_start)/(pv1.scanpv.pre_nsteps - 1)
    printMsg('Doing pre-scan ' + '-'*20) 
    printMsg('Scanning %s from %f to %f in %d steps' % 
            (pv1.scanpv.pvname, pv1.scanpv.pre_start, pv1.scanpv.pre_stop, pv1.scanpv.pre_nsteps))
    for i in range(pv1.scanpv.pre_nsteps):
        newPos1 = pv1.scanpv.pre_start + i*pv1.scanpv.inc
        printMsg('Setting %s to %f' % (pv1.scanpv.pvname, newPos1))
        pv1.scanpv.move(newPos1)
        printSleep(pv1.scanpv.settletime,'Settling')
        if grabObject:
            if grabObject.grabber.grabFlag:
                if grabObject.grabber.stepFlag:
                    grabObject.grabber.filenameExtras = ('_prescan_' + pv1.scanpv.desc + 
                            '-' + '{0:03d}'.format(i+1) + '-' + 
                            '{0:08.4f}'.format(pv1.scanpv.get()))
                else:
                    grabObject.grabber.filenameExtras = ('_prescan_' + pv1.scanpv.desc + 
                            '-' + '{0:08.4f}'.format(pv1.scanpv.get()))
                grabObject.grabber.grabImages()
    printMsg('Pre-scan done ' + '-'*20) 

def printMsg(string, pv=msgPv):
    """Print message to stdout and to message PV."""
    try:
        print '%s %s' % (timestamp(1), string)
        pv.put(string)
    except ValueError:
        print 'msgPv.put failed: string too long'


def printSleep(sleepTime, string='Pausing', pv=msgPv):
    """Print message and pause for sleepTime seconds."""
    if sleepTime:
        message = '%s for %f seconds...' % (string, sleepTime)
        printMsg(message)
        sleep(sleepTime)


def printScanInfo(exp, pv1, pv2=None):
    """Print scan info."""
    print '################################'
    print('Scan mode: %s' % (exp.scanmodePv.get(as_string=True)))
    if exp.scanmode == 1 and pv1.pvname:
        print('PV #1 type: %s' % (pv1.pvtypePv.get(as_string=True)))
    elif exp.scanmode == 1 and pv2.pvname and not pv1.pvname:
        print('PV #2 type: %s' % (pv2.pvtypePv.get(as_string=True)))
    if pv2:
        if exp.scanmode == 2 and pv1.pvname and pv2.pvname:
            print('PV #1 type: %s' % (pv1.pvtypePv.get(as_string=True)))
            print('PV #2 type: %s' % (pv2.pvtypePv.get(as_string=True)))
        elif exp.scanmode == 2 and pv1.pvname and not pv2.pvname:
            print('PV #1 type: %s' % (pv1.pvtypePv.get(as_string=True)))
            print('PV #2 type: No PV entered')
        elif exp.scanmode == 2 and pv2.pvname and not pv1.pvname:
            print('PV #1 type: No PV entered')
            print('PV #2 type: %s' % (pv2.pvtypePv.get(as_string=True)))
    print '################################'


def frange(start, stop, step):
    """A range() for floats."""
    i = start
    while i <= stop:
        yield i
        i += step

def expandRange(strng):
    """Expands a matlab-style range string, e.g. 1:0.2:5, and generates a list of string values."""
    start, step, stop = strng.split(':')
    start = float(start)
    stop = float(stop)
    step = float(step)
    lst = [str(x) for x in frange(start, stop, step)]
    return lst

def flattenList(lst):
    """Flattens a nested list."""
    return [x for sublist in lst for x in sublist]

def isNumber(number):
    """Tests whether number is a number."""
    try:
        float(number)
        return True
    except ValueError:
        print '%s not a number.' % number
        return False




#--- Self-test code -------------
if __name__ == "__main__":
    args = 'PV_PREFIX'
    def show_usage():
        "Prints usage"
        print 'Usage: %s %s' % (sys.argv[0], args)
    if len(sys.argv) != 2:
        show_usage()
        sys.exit(1)
    pvPrefix = sys.argv[1]
    iocPv = PV(pvPrefix + ':IOC')
    print 'IOC name PV: ', iocPv
    print 'IOC name: ', iocPv.get()        
    

##################################################################################################################
        

exit

