#!/usr/bin/env python
# pvScan module

import datetime
import math
import logging
import os
import random
import re
import sys
from time import sleep, time
from threading import Thread, Lock
import matplotlib.pyplot as plt
from epics import PV, ca, caget, caput
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

def loggingConfig():
    """Configure logging."""
    debugFlag = PV(pvPrefix + ':DEBUG:ENABLE').get()
    logLevel = logging.DEBUG if debugFlag else logging.WARNING
    logging.basicConfig(format='%(levelname)s [%(asctime)s]: %(message)s', datefmt='%I:%M:%S', level=logLevel)
    logging.info('Start')

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
NOW = timestamp('s')

        
class Experiment:
    """Set experiment name, filepath, and scan mode."""
    def __init__(self, npvs=None, expname=None, filepath=None, scanname=None, mutex=None, log=True, createDirs=True):
        className = self.__class__.__name__
        functionName = '__init__'
        logging.info('%s.%s' % (className, functionName))
        if expname is None:
            expname = PV(pvPrefix + ':IOC.DESC').get()
        if ' ' in expname: expname = expname.replace(' ', '_')
        if scanname is None:
            scanname = PV(pvPrefix + ':SCAN:NAME').get()
        if ' ' in scanname: scanname = scanname.replace(' ', '_')
        if scanname: scanname = '_' + scanname
        self.mutex = mutex
        self.dataFlag = PV(pvPrefix + ':DATA:ENABLE').get()
        self.logFlag = PV(pvPrefix + ':LOG:ENABLE').get()
        self.imageFlag = PV(pvPrefix + ':GRABIMAGES:ENABLE').get()
        self.scanmodePv = PV(pvPrefix + ':SCAN:MODE')
        self.scanmode = self.scanmodePv.get()
        self.expname = expname
        self.scanname = scanname
        self.createDirs = createDirs
        self.filepath = self._set_filepath(filepath) if self.createDirs else None
        self.scanflag = PV(pvPrefix + ':SCAN:ENABLE').get()
        self.preScanflag = PV(pvPrefix + ':SCAN:PRESCAN').get()
        self.acqFixed = PV(pvPrefix + ':ACQ:FIXED').get()
        self.acqPumpProbe = PV(pvPrefix + ':ACQ:PUMP_PROBE').get()
        self.acqStatic = PV(pvPrefix + ':ACQ:STATIC').get()
        self.acqPumpBG = PV(pvPrefix + ':ACQ:PUMP_BG').get()
        self.acqDarkCurrent = PV(pvPrefix + ':ACQ:DARK_CURRENT').get()
        self.acqDelay1 = PV(pvPrefix + ':ACQ:DELAY1').get()
        self.acqDelay2 = PV(pvPrefix + ':ACQ:DELAY2').get()
        self.acqDelay3 = PV(pvPrefix + ':ACQ:DELAY3').get()
        # Create objects needed in experiment
        if log: 
            self.logFile = Tee(filepath=self.filepath)
        self.create_scan_pvs(npvs)
        self.create_image_grabber()
        if log:
            self.dataLog = DataLogger(filepath=self.filepath, pvlist=self.imagepvs, 
                                  scanpvs=self.scanpvs, mutex=self.mutex)
        logging.debug('%s.%s: scanmode: %s' % (className, functionName, self.scanmode))

    def _set_filepath(self, filepath):
        """Create filepath."""
        if filepath is None:
            filepathAutoset = PV(pvPrefix + ':DATA:FILEPATH:AUTOSET').get()
            if filepathAutoset: 
                if os.environ['NFSHOME']:
                    filepath = (os.environ['NFSHOME'] + '/pvScan/' 
                                + self.expname + '/' +  NOW + self.scanname + '/')
                else:
                    filepath = '~/pvScan/' + self.expname + '/' +  NOW + self.scanname + '/'
                PV(pvPrefix + ':DATA:FILEPATH').put(filepath)  # Write filepath to PV for display
            else:
                filepath = PV(pvPrefix + ':DATA:FILEPATH').get(as_string=True)
                if not filepath.endswith('/'): filepath = filepath + '/'
                if ' ' in filepath: filepath = filepath.replace(' ', '_')
        if self.dataFlag or self.logFlag or self.imageFlag:
            if os.path.exists(filepath):
                msgPv.put('Failed: Filepath already exists')
                raise IOError('Filepath already exists')
            else: 
                os.makedirs(filepath)
        return filepath

    def create_scan_pvs(self, npvs=None):
        """Create scan PV instances."""
        if npvs is not None:
            scanpvs = []
            for i in range(npvs):
                pvname = PV(pvPrefix + ':SCANPV' + str(i+1) + ':PVNAME').get()
                if pvname:
                    pvstatus = PV(pvname).status
                else:  # No PV entered
                    continue
                if pvstatus is None: 
                    print 'Error: _create_scan_pvs: Invalid PV', pvname
                    continue
                pvtype = PV(pvPrefix + ':SCANPV' + str(i+1) + ':PVTYPE').get(as_string=False)
                # Create PV instance
                if pvtype == 1:
                    scanpvs.append(Motor(pvname, i+1))
                elif pvtype == 2:
                    scanpvs.append(PolluxMotor(pvname, i+1))
                elif pvtype == 3:
                    scanpvs.append(BeckhoffMotor(pvname, i+1))
                elif pvtype == 4:
                    scanpvs.append(Magnet(pvname, i+1))
                elif pvtype == 5:
                    scanpvs.append(Lakeshore(pvname, i+1))
                elif pvtype == 6:
                    scanpvs.append(RbvPv(pvname, i+1))
                else:
                    scanpvs.append(BasePv(pvname, i+1))
        else:
            scanpvs = None
        self.scanpvs = scanpvs

    def create_image_grabber(self, cameraPvPrefix=None):
        """Create image grabber instance."""
        if cameraPvPrefix is None:
            cameraPvPrefix = PV(pvPrefix + ':GRABIMAGES:CAMERA').get(as_string=True)
        if 'DirectD' in cameraPvPrefix:
            grabber = DDGrabber(cameraPvPrefix, expname=self.expname)
        else:
            grabber = ADGrabber(cameraPvPrefix=cameraPvPrefix, filepath=self.filepath)
            if self.createDirs:
                grabber._create_image_filepath()
        self.imagepvs = [grabber.timestampRBVPv, grabber.captureRBVPv]
        self.grabber = grabber
    

class Tee(object):
    """Write output to stdout and to log file."""
    def __init__(self, filepath=None, filename=None):
        if filepath is None:
            filepath = './'
        logFilename = filepath + NOW + '.log'
        if filename is None:
            filename = logFilename
        PV(pvPrefix + ':LOG:FILENAME').put(filename)
        logEnable = PV(pvPrefix + ':LOG:ENABLE').get()  # Enable/Disable log file
        if logEnable:
            self.file = open(filename, 'w')
        self.filepath = filepath
        self.logEnable = logEnable
        self.logFilename = logFilename
        self.stdout = sys.stdout
        sys.stdout = self
    
    def __del__(self):
        sys.stdout = self.stdout
        if self.logEnable:
            self.file.close()
    
    def write(self, data):
        if self.logEnable:
            self.file.write(data)
        self.stdout.write(data)


class BasePv(PV):
    """Base class which inherits from pyEpics PV class."""
    def __init__(self, pvname, pvnumber=None, rbv=None):
        className = self.__class__.__name__
        functionName = '__init__'
        logging.debug('%s.%s: pvname: %s' % (className, functionName, pvname))
        # If no name is entered, raise exception and quit:
        if not pvname: 
            msgPv.put('Failed: Invalid PV')
            raise NameError('Invalid PV')
        PV.__init__(self, pvname)
        self.pvnumber = pvnumber
        if rbv is not None:
            rbv = PV(rbv)
        self.rbv = rbv
        self.abort = None
        if self.pvname and self.pvnumber:
            self.pvtypePv = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':PVTYPE')
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
            # Do random scan if enabled from PV
            if self.randomScanflag:
                randValStr = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':RAND_VALS').get(as_string=True)
                self.scanPos = self._shuffleString(randValStr)
                print self.scanPos
            else:
                self.scanPos = [x for x in frange(self.start, self.stop, self.inc)]
            self.offset = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':OFFSET').get()
            self.settletime = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':SETTLETIME').get()
            self.delta = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':DELTA').get()
            self.pre_start = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':PRE_START').get()
            self.pre_stop = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':PRE_STOP').get()
            self.pre_nsteps = PV(pvPrefix + ':SCANPV' + str(self.pvnumber) + ':PRE_NSTEPS').get()
        else:
            self.delta = None
        # Test for PV validity:
        if not self.status:
            print 'PV object: ', self
            print 'PV status: ', self.status
            printMsg('PV %s not valid' % (self.pvname))
            #raise NameError('PV %s not valid' % (self.pvname))

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
            if self.delta:
                delta = self.delta
            self.pvWait(val, delta, timeout)

    def _shuffleString(self, strng):
        """Shuffle a string of values into a random list of floats.
        Comma, semicolon, and whitespace delimiters recognized, 
        as well as start:step:stop ranges."""
        lst = re.split(r'[;,\s]\s*', strng) 
        rangePat = re.compile(r'([-+]?\d*\.\d+|\d+):([-+]?\d*\.\d+|\d+):([-+]?\d*\.\d+|\d+)')
        lst = [expandRange(rangePat.search(x).group(0)) if rangePat.search(x) else x for x in lst]
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


class RbvPv(BasePv):
    """RBV PV class which inherits from BasePv class."""
    def __init__(self, pvname, pvnumber=None, rbv=None):
        if rbv is None:
            rbv = PV(pvPrefix + ':SCANPV' + str(pvnumber) + ':RBVNAME').get(as_string=True)
        if PV(rbv).status is None:
            printMsg('Failed: RBV %s invalid' % (rbv))
            raise NameError('RbvPv: RBV %s invalid' % (rbv))
        BasePv.__init__(self, pvname, pvnumber, rbv)

    def move(self, value, wait=True, delta=0.1, timeout=360.0):
        "Put with optional wait"
        BasePv.move(self, value, wait, delta, timeout)


class Shutter(PV):
    """Shutter class which inherits from pyEpics PV class."""
    def __init__(self, pvname, rbvpv=None, number=0):
        PV.__init__(self, pvname)
        self.rbv = PV(rbvpv) if rbvpv else ''
        if number:
            self.enabled = PV(pvPrefix + ':SHUTTER' + str(number) + ':ENABLE').get()
            self.initial = PV(pvPrefix + ':SHUTTER' + str(number) + ':INITIAL')
        self.number = number
    def openCheck(self, val=0.5):
        sleep(0.2)
        if self.rbv.get() < val:
            printMsg('Failed: Shutter %s check' % (self.number))
            print 'Shutter: %s Value: %f' % (self.pvname, self.rbv.get())
            raise ValueError('Failed: Shutter check')
    def closeCheck(self, val=0.5):
        sleep(0.2)
        if self.rbv.get() > val:
            printMsg('Failed: Shutter %s check' % (self.number))
            print 'Shutter: %s Value: %f' % (self.pvname, self.rbv.get())
            raise ValueError('Failed: Shutter check')
                

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
                    raise ValueError('Failed: Shutter check')
    
    def closeCheck(self, val=0.5):
        for shutter in self.shutterList:
            if shutter.enabled:
                sleep(0.2)
                if shutter.rbv.get() > val:
                    printMsg('Failed: Shutter %s check' % (shutter.number))
                    print 'Shutter: %s Value: %f' % (shutter.pvname, shutter.rbv.get())
                    raise ValueError('Failed: Shutter check')



class DataLogger(Thread):
    """Set up pvlist and filepaths to write data and log files."""
    def __init__(self, filepath=None, pvlist=None, scanpvs=None, mutex=None):
        className = self.__class__.__name__
        functionName = '__init__'
        logging.info('%s.%s' % (className, functionName))
        if filepath is None:
            filepath = './'
        if pvlist is None:
            pvlist = []
        if mutex is None:
            mutex = Lock()
        self.mutex = mutex
        Thread.__init__(self)
        self.running = True  # Datalog flag 
        # Read file of additional monitor PVs
        pvFile = os.environ['NFSHOME'] + '/pvScan/DataLogger/pvlist-' + pvPrefix.replace(':','_')
        if os.path.isfile(pvFile):
            with open(pvFile, 'r') as file:
                pvlist2 = [line.strip() for line in file if not line.startswith('#')]
                pvlist2 = [PV(line) for line in pvlist2 if line]
            pvlist += pvlist2  # Add additional monitor PVs to existing PV list
        if pvlist is not None:
            pvlist = [pv for pv in pvlist if pv]  # Remove invalid PVs
            for pv in pvlist:
                if not pv.status:
                    pvlist.remove(pv)
                    with self.mutex:
                        printMsg('PV %s invalid: removed from Data Logger' % (pv.pvname))
        self.pvlist = pvlist
        self.filepath = filepath
        self.dataFilename = self.filepath + NOW + '.dat'
        PV(pvPrefix + ':DATA:FILENAME').put(self.dataFilename)
        self.dataEnable = PV(pvPrefix + ':DATA:ENABLE').get()  # Enable/Disable data logging
        self.dataInt = PV(pvPrefix + ':DATA:INT').get()  # Interval between PV data log points
        self.nPtsMax = 1000000  # limits number of data points
        self.plotTimesFlag = PV(pvPrefix + ':DATA:PLOTTIMES').get()  # Plot average time to sample a Monitor PV
        self.formatFlag = PV(pvPrefix + ':DATA:FORMAT').get()  # Format data for nice display
        self.sampleTimes = []  # To store PV sample times for (optional) plotting.

    def datalog(self):
        """Logs PV data to a file.
        Designed to be run in a separate thread. 
        Uses self.running flag to start/stop data.
        PVs must be in pvlist."""
        with open(self.dataFilename, 'w') as self.datafile:
            self._writeHeader()
            if self.formatFlag:
                self._writeFormattedData()
            else:
                self._writeData()
        if self.plotTimesFlag:
           self._plotSampleTimes()
    
    # These are for threading
    def run(self):
        self.datalog()
    def stop(self):
        self.running = False

    def _writeHeader(self):
        """Write data file header."""
        self.datafile.write('%-30s %s' % ('PV name', 'PV description\n'))
        for pv in self.pvlist:
            if '.RBV' in pv.pvname: pv = PV(pv.pvname.replace('.RBV', ''))
            if '.RVAL' in pv.pvname: pv = PV(pv.pvname.replace('.RVAL', ''))
            self.datafile.write('%-30s %s' % (pv.pvname, str(PV(pv.pvname + '.DESC').get()) + '\n'))
        self.datafile.write('#'*50 + '\n')

    def _writeData(self):
        """Write data."""
        self.datafile.write('%s ' % ('Timestamp'))
        for pv in self.pvlist:
            self.datafile.write('%s ' % (pv.pvname))
        self.datafile.write('\n')
        count = 0
        while self.running and count < self.nPtsMax:
            self.datafile.write(str(timestamp(1)) + ' ')
            start = time()
            for pv in self.pvlist:
                try:
                    self.datafile.write('%s ' % (str(pv.value)))
                except KeyError:
                    self.datafile.write('Invalid ')
                except TypeError:
                    self.datafile.write('Invalid ')
            elapsedTime = time() - start
            self.datafile.write('\n')
            count += 1
            nPvs = len(self.pvlist)
            if self.plotTimesFlag:
                self.sampleTimes.append(elapsedTime/nPvs)
            if self.dataInt - elapsedTime > 0:
                sleep(self.dataInt - elapsedTime)

    def _writeFormattedData(self):
        """Write formatted data (left justify, ...)."""
        nPvs = len(self.pvlist)
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
            if self.plotTimesFlag:
                self.sampleTimes.append(elapsedTime/nPvs)
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
                    self.datafile.write('%-*s' %(maxStrLens[i]+1, pvLists[i][j]))
                self.datafile.write('\n')
        except IndexError:
            with self.mutex:
                print 'DataLogger: list index out of range'

    def _plotSampleTimes(self):
        """Plot time to sample each PV."""
        plt.xlabel('Sample index') 
        plt.ylabel('Time [s]') 
        plt.title('Average time to sample a Monitor PV') 
        plt.plot(self.sampleTimes)
        plt.show()


class DDGrabber():
    """UED Direct Detector grabber."""
    def __init__(self, cameraPvPrefix, expname=None):
        className = self.__class__.__name__
        functionName = '__init__'
        logging.info('%s.%s' % (className, functionName))
        logging.info('%s.__init__()' % (self.__class__.__name__))
        self.cameraPvPrefix = cameraPvPrefix
        self.expname = expname
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
        if self.filenameExtras.startswith('_'):
            self.filenameExtras = self.filenameExtras.replace('_', '')
        filenameTemplate = ('%s/%s/%s_%s' % (timestamp('today'), self.expname, 
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
        """Abort data writing."""
        self.dataStartStopPv.put(0)
        sleep(0.25)
        self.dataStartStopPv.put(0)
        

class ADGrabber():
    """AreaDetector grabber."""
    def __init__(self, cameraPvPrefix=None, filepath=None, nImages=None, 
                 pvlist=None, plugin='TIFF1'):
        className = self.__class__.__name__
        functionName = '__init__'
        logging.info('%s.%s' % (className, functionName))
        if cameraPvPrefix is None: 
            cameraPvPrefix = PV(pvPrefix + ':GRABIMAGES:CAMERA').get(as_string=True)
        if filepath is None:
            filepath = PV(pvPrefix + ':DATA:FILEPATH').get(as_string=True)
            if not filepath.endswith('/'): filepath = filepath + '/'
        if nImages is None:
            nImages = PV(pvPrefix + ':GRABIMAGES:N').get()
        if pvlist is None:
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
            pvlist = [(cameraPvPrefix + ':' + item) for item in pvlist]
        filepath += 'images' + '-' + cameraPvPrefix + '/' 
        self.scanmode = PV(pvPrefix + ':SCAN:MODE').get()
        self.grabFlag = PV(pvPrefix + ':GRABIMAGES:ENABLE').get()
        if plugin == 'TIFF1':
            fileExt = '.tif'
        elif plugin == 'JPEG1':
            fileExt = '.jpg'
        else:
            fileExt = '.img'
        self.imagePvPrefix = cameraPvPrefix + ':' + plugin
        self.grabImagesRatePv = PV(pvPrefix + ':GRABIMAGES:RATE.INP')
        self.grabImagesRatePv.put(cameraPvPrefix + ':' + plugin + ':ArrayRate_RBV CPP')
        self.numCapturePv = PV(self.imagePvPrefix + ':NumCapture')
        self.templatePv = PV(self.imagePvPrefix + ':FileTemplate')
        self.capturePv = PV(self.imagePvPrefix + ':Capture')
        self.captureRBVPv = PV(self.imagePvPrefix + ':Capture_RBV.RVAL')
        self.acquirePv = PV(cameraPvPrefix + ':cam1:Acquire')
        self.acquireRBVPv = PV(cameraPvPrefix + ':cam1:Acquire_RBV.RVAL')
        self.imageModePv = PV(cameraPvPrefix + ':cam1:ImageMode')
        self.numExposuresPv = PV(cameraPvPrefix + ':cam1:NumExposures')
        self.arrayCounterPv = PV(cameraPvPrefix + ':cam1:ArrayCounter_RBV')
        self.lastImagePv = PV(self.imagePvPrefix + ':FullFileName_RBV')
        self.writingRBVPv = PV(self.imagePvPrefix + ':WriteFile_RBV.RVAL')
        self.timestampRBVPv = PV(self.imagePvPrefix + ':TimeStamp_RBV')
        self.filePathPv = PV(self.imagePvPrefix + ':FilePath')
        self.fileNamePv = PV(self.imagePvPrefix + ':FileName')
        self.cameraPvPrefix = cameraPvPrefix
        self.fileNamePrefix = self.cameraPvPrefix  # Make this user modifiable
        self.pvlist = pvlist
        self.plugin = plugin
        self.filepath = filepath
        self.nImages = nImages
        self.fileExt = fileExt
        self.filenameExtras = ''
        self.captureMode = PV(pvPrefix + ':GRABIMAGES:CAPTUREMODE').get()
        self.writeTiffTagsFlag = PV(pvPrefix + ':GRABIMAGES:TIFFTS').get() # Tiff tag timestamps
        self.stepFlag = PV(pvPrefix + ':GRABIMAGES:STEPNUMBER').get() # Write step number into filename
        self.grabSeq2Flag = PV(pvPrefix + ':GRABIMAGES:SEQ2ENABLE').get() # Grab second image sequence after first 
        self.grabSeq2Delay = PV(pvPrefix + ':GRABIMAGES:SEQ2DELAY').get() 
        self.nImages2 = PV(pvPrefix + ':GRABIMAGES:N2').get() # N images for second sequence
        self.waitForNewImageFlag = PV(pvPrefix + ':GRABIMAGES:WAIT_NEW').get() # Wait for new image before capturing?
        self.imageFilepaths = []

    def _create_image_filepath(self):
        """Creates image filepath, sets IMAGE:FILEPATH PV.
           Should be called just after image grabber object is created.
        """
        if self.scanmode and self.grabFlag:
            if os.path.exists(self.filepath):
                msgPv.put('Failed: Filepath already exists')
                raise IOError('Filepath already exists')
            else:
                os.makedirs(self.filepath)
        PV(pvPrefix + ':IMAGE:FILEPATH').put(self.filepath)  # Write filepath to PV for "Browse images" button
        
    def grabImages(self, nImages=0, grabImagesWriteSettingsFlag=1, pause=0.5):
        """Grabs n images from camera."""
        self.nImages = nImages if nImages else self.nImages
        printMsg('Grabbing %d images from %s...' % (self.nImages, self.cameraPvPrefix))
        PV(self.imagePvPrefix + ':EnableCallbacks').put(1)
        # PV().put() seems to need a null terminator when putting strings to waveforms.
        self.filePathPv.put(self.filepath + '\0')
        self.fileNamePv.put(self.fileNamePrefix + self.filenameExtras + '\0')
        PV(self.imagePvPrefix + ':AutoIncrement').put(1)
        PV(self.imagePvPrefix + ':FileWriteMode').put(1)
        PV(self.imagePvPrefix + ':AutoSave').put(1)
        PV(self.imagePvPrefix + ':FileNumber').put(1)
        if self.captureMode == 1:
            self._bufferedCapture()
        elif self.captureMode == 2:
            self._CBACapture()
        else:
            self._individualCapture()
        if grabImagesWriteSettingsFlag:
            self._writeCameraSettings()
        if self.writeTiffTagsFlag:
            self._writeTiffTags()
        printSleep(pause, string='Grabbed %d images from %s: Pausing' % 
                  (self.nImages, self.cameraPvPrefix))
            
    def _setAcquire(self):
        """Starts camera acquisition if not already acquiring."""
        functionName = '_setAcquire'
        logging.debug('%s: acquiring: %s' % (functionName, self.acquireRBVPv.get()))
        if not self.acquireRBVPv.get(): # If camera is not acquiring...
            logging.debug('%s: turning acquisition on' % (functionName))
            self.acquirePv.put(1) # Try to turn acquisition on
            sleep(0.5) # Give camera time to turn on...
            if not self.acquireRBVPv.get():
                # If unable to acquire, raise exception & quit
                printMsg('Failed: Camera not acquiring')
                raise ValueError('Camera not acquiring')

    def _writeCameraSettings(self):
        """Writes camera settings to file."""
        settingsFile = (self.filepath + 'cameraSettings-' + 
                self.cameraPvPrefix + '-' + timestamp() + '.txt')
        with open(settingsFile, 'w') as outfile:
            outfile.write('Camera settings for ' + self.cameraPvPrefix + '\n')
            outfile.write(timestamp() + '\n')
            outfile.write('-----------------------------------------------------------\n')
            for pv in self.pvlist:
                pv = PV(pv)
                outfile.write(str(pv.pvname) + ' ')
                outfile.write(str(pv.value) + '\n')
            outfile.write('\n')

    def _writeTiffTags(self):
        """Timestamps image file names with tiff tags."""
        printMsg('Timestamping filenames from Tiff tags...')
        for filepath in self.imageFilepaths:
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

    def _bufferedCapture(self):
        """Capture images in AD buffered mode."""
        functionName = '_bufferedCapture'
        logging.debug('%s' % (functionName))
        self._setAcquire() # Turn acquisition on
        self.numCapturePv.put(self.nImages)
        imageFilenameTemplate = '%s%s_%4.4d' + self.fileExt
        self.templatePv.put(imageFilenameTemplate + '\0')
        if self.waitForNewImageFlag:
            self._waitForNewImage()
        logging.debug('%s: capturing' % (functionName))
        self.capturePv.put(1, wait=True)
        # Build a list of filenames for (optional) tiff tag file naming
        if self.writeTiffTagsFlag:
            self.imageFilepaths = ([('%s%s%s_%04d%s' % (self.filepath, self.fileNamePrefix, 
                    self.filenameExtras, n+1, self.fileExt)) for n in range(self.nImages)])
        while self.captureRBVPv.get() or self.writingRBVPv.get():
            sleep(0.05)

    def _individualCapture(self):
        """Capture images in AD individual mode."""
        functionName = '_individualCapture'
        logging.debug('%s' % (functionName))
        self._setAcquire() # Turn acquisition on
        self.numCapturePv.put(1)
        if self.waitForNewImageFlag:
            self._waitForNewImage()
        # Capturing loop
        logging.debug('%s: capturing' % (functionName))
        for i in range(self.nImages):
            # Set FileTemplate PV and then grab image
            imageFilenameTemplate = '%s%s_' + timestamp(1) + '_%4.4d' + self.fileExt
            self.templatePv.put(imageFilenameTemplate + '\0')
            self.capturePv.put(1, wait=True)
            # Build a list of filenames for (optional) tiff tag file naming
            if self.writeTiffTagsFlag:
                sleep(0.010)
                self.imageFilepaths.append(self.lastImagePv.get(as_string=True))

    def _CBACapture(self):
        """Capture images one at a time by enabling capture, turning on acquisition, 
            turning off acquisition, and repeating."""
        functionName = '_CBACapture'
        logging.debug('%s' % (functionName))
        if self.acquirePv.get():
            self.acquirePv.put(0)
        while self.acquirePv.get():
            sleep(0.05)
        imageMode0 = self.imageModePv.get()  # Get current image mode
        self.imageModePv.put(0)  # Set to Image Mode = Single
        self.numExposuresPv.put(1)  # 1 exposure per image
        self.numCapturePv.put(1)
        # Capturing loop
        logging.debug('%s: capturing' % (functionName))
        for i in range(self.nImages):
            # Set FileTemplate PV and then grab image
            imageFilenameTemplate = '%s%s_' + timestamp(1) + '_%4.4d' + self.fileExt
            self.templatePv.put(imageFilenameTemplate + '\0')
            self.capturePv.put(1)  # Turn capturing on
            while self.capturePv.get() != 1:
                sleep(0.05)
            self.acquirePv.put(1) # Turn acquisition on
            while self.captureRBVPv.get() or self.writingRBVPv.get():
                sleep(0.05)
            self.acquirePv.put(0) # Turn acquisition off
            while self.acquirePv.get():
                sleep(0.05)
            # Build a list of filenames for (optional) tiff tag file naming
            if self.writeTiffTagsFlag:
                sleep(0.010)
                self.imageFilepaths.append(self.lastImagePv.get(as_string=True))
        self.imageModePv.put(imageMode0)  # Set image mode back

    def _waitForNewImage(self):
        """Waits for ArrayCounter to increment."""
        functionName = '_waitForNewImage'
        if self.arrayCounterPv:
            arrayCount0 = self.arrayCounterPv.get()
            logging.debug('%s: arrayCount0: %s' % (functionName, arrayCount0))
            if arrayCount0 is not None:
                msgPv.put('Waiting for new image...')
                while self.arrayCounterPv.get() == arrayCount0:
                    sleep(0.05)
        msgPv.put('Grabbing %d images from %s...' % (self.nImages, self.cameraPvPrefix))

    def abort(self):
        """Abort image capturing."""
        self.capturePv.put(0)


def pvNDScan(exp, scanpvs=None, grabObject=None, shutter1=None, shutter2=None, shutter3=None):
    """Do 0-, 1-, or 2-D scan and grab images at each step (or do nothing and bail)."""
    functionName = 'pvNDScan'
    logging.debug('%s: %s' %(functionName, scanpvs))
    if scanpvs is None:
        if exp.scanmode == 1:
            raise ValueError('pvNDScan: Need to create at least one PV.')
        elif exp.scanmode == 2:
            raise ValueError('pvNDScan: Need to create at least two PVs.')
    else:
        if len(scanpvs) == 1:
            pv1 = scanpvs[0]
            pv2 = None
        elif len(scanpvs) == 2:
            pv1 = scanpvs[0]
            pv2 = scanpvs[1]
        else:
            raise ValueError('pvNDScan: Need one or two PVs.')
    if 1 <= exp.scanmode <=2 and pv2 and not pv1:  # 1- or 2-D scan
        pv1 = pv2
        exp.scanmode = 1
    if 1 <= exp.scanmode <=2 and pv1:
        initialPos1 = pv1.get()
        if exp.scanmode == 2 and pv2:
            initialPos2 = pv2.get()
        elif exp.scanmode == 2 and not pv2:
            print '***WARNING***: pvNDScan: Scan mode 2-D selected but no PV #2.'
        # Do pre-scan if enabled from PV
        if exp.preScanflag: preScan(exp, pv1, grabObject)
        # Scan PV #1
        if pv1.randomScanflag:
            printMsg('Scanning %s randomly' %(pv1.pvname))
        else:
            printMsg('Scanning %s from %f to %f in %d steps' % 
                    (pv1.pvname, pv1.start, pv1.stop, len(pv1.scanPos)))
        stepCount1 = 0
        for x in pv1.scanPos:
            printMsg('Setting %s to %f' % (pv1.pvname, x))
            pv1.move(x)
            stepCount1 += 1
            printSleep(pv1.settletime,'Settling')
            # Scan PV #2
            if exp.scanmode == 2 and pv2:
                if pv1.randomScanflag:
                    printMsg('Scanning %s randomly' %(pv1.pvname))
                else:
                    printMsg('Scanning %s from %f to %f in %d steps' % 
                            (pv2.pvname, pv2.start, pv2.stop, len(pv2.scanPos)))
                stepCount2 = 0
                for y in pv2.scanPos:
                    printMsg('Setting %s to %f' % (pv2.pvname, y))
                    pv2.move(y)
                    stepCount2 += 1
                    printSleep(pv2.settletime, 'Settling')
                    if grabObject:
                        if grabObject.grabFlag:
                            if grabObject.stepFlag:
                                grabObject.filenameExtras = ('_{0}-{1:03d}-{2:08.4f}_{3}-{4:03d}-{5:08.4f}'
                                        .format(pv1.desc, stepCount1, pv1.get(), pv2.desc, stepCount2, pv2.get()))
                            else:
                                grabObject.filenameExtras = ('_{0}-{1:08.4f}_{2}-{3:08.4f}'
                                        .format(pv1.desc, pv1.get(), pv2.desc, pv2.get()))
                            if grabObject.grabSeq2Flag:
                                pumpedGrabSequence(grabObject, shutter1, shutter2, shutter3)
                            if exp.acqFixed:
                                grabObject.grabImages()
                            else:
                                if exp.acqPumpProbe:
                                    acqPumpProbe(grabObject, shutter1, shutter2)
                                    if exp.acqDelay1 and (exp.acqStatic or exp.acqPumpBG or exp.acqDarkCurrent):
                                        #sleep(exp.acqDelay1)
                                        printSleep(exp.acqDelay1, 'Pausing')
                                if exp.acqStatic:
                                    acqStatic(grabObject, shutter1, shutter2)
                                    if exp.acqDelay2 and (exp.acqPumpBG or exp.acqDarkCurrent):
                                        #sleep(exp.acqDelay2)
                                        printSleep(exp.acqDelay2, 'Pausing')
                                if exp.acqPumpBG:
                                    acqPumpBG(grabObject, shutter1, shutter2)    
                                    if exp.acqDelay3 and exp.acqDarkCurrent:
                                        #sleep(exp.acqDelay3)
                                        printSleep(exp.acqDelay3, 'Pausing')
                                if exp.acqDarkCurrent:
                                    acqDarkCurrent(grabObject, shutter1, shutter2)
            else:
                if grabObject:
                    if grabObject.grabFlag:
                        if grabObject.stepFlag:
                            grabObject.filenameExtras = ('_{0}-{1:03d}-{2:08.4f}'
                                    .format(pv1.desc, stepCount1, pv1.get()))
                        else:
                            grabObject.filenameExtras = ('_{0}-{1:08.4f}'.format(pv1.desc, pv1.get()))
                        if grabObject.grabSeq2Flag:
                            pumpedGrabSequence(grabObject, shutter1, shutter2, shutter3)
                        if exp.acqFixed:
                            grabObject.grabImages()
                        else:
                            if exp.acqPumpProbe:
                                acqPumpProbe(grabObject, shutter1, shutter2)
                                if exp.acqDelay1 and (exp.acqStatic or exp.acqPumpBG or exp.acqDarkCurrent):
                                    #sleep(exp.acqDelay1)
                                    printSleep(exp.acqDelay1, 'Pausing')
                            if exp.acqStatic:
                                acqStatic(grabObject, shutter1, shutter2)
                                if exp.acqDelay2 and (exp.acqPumpBG or exp.acqDarkCurrent):
                                    #sleep(exp.acqDelay2)
                                    printSleep(exp.acqDelay2, 'Pausing')
                            if exp.acqPumpBG:
                                acqPumpBG(grabObject, shutter1, shutter2)    
                                if exp.acqDelay3 and exp.acqDarkCurrent:
                                    #sleep(exp.acqDelay3)
                                    printSleep(exp.acqDelay3, 'Pausing')
                            if exp.acqDarkCurrent:
                                acqDarkCurrent(grabObject, shutter1, shutter2)
        # Move back to initial positions
        printMsg('Setting %s back to initial position: %f' % (pv1.pvname,initialPos1))
        pv1.move(initialPos1)
        if exp.scanmode == 2 and pv2:
            printMsg('Setting %s back to initial position: %f' % (pv2.pvname,initialPos2))
            pv2.move(initialPos2)
    elif exp.scanmode == 3:  # Grab images only
        if grabObject:
            if grabObject.grabFlag:
                if grabObject.grabSeq2Flag:
                    pumpedGrabSequence(grabObject, shutter1, shutter2, shutter3)
                grabObject.grabImages()
    else:
        printMsg('Scan mode "None" selected or no PVs entered, continuing...')
        sleep(1)
    return 0
   
def pumpedGrabSequence(grabObject, shutter1, shutter2, shutter3):
    """Do a pumped/static image grab sequence."""
    debug = 0
    printMsg('Starting pumped image sequence')
    sleep(0.25)
    shutter1Stat = shutter1.OCStatus.get()
    shutter2Stat = shutter2.OCStatus.get()
    shutter3Stat = shutter3.OCStatus.get()
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
    if debug: print grabObject.filenameExtras
    if 'Static' in grabObject.filenameExtras:
        grabObject.filenameExtras = grabObject.filenameExtras.replace('Static', 'Pumped')
    else:
        grabObject.filenameExtras = '_' + 'Pumped' + grabObject.filenameExtras
    if debug: print grabObject.filenameExtras
    grabObject.grabImages(grabObject.nImages2)
    printMsg('Returning shutters to initial state')
    shutter1.open.put(1) if shutter1Stat == 1 else shutter1.close.put(0)
    shutter2.open.put(1) if shutter2Stat == 1 else shutter2.close.put(0)
    shutter3.open.put(1) if shutter3Stat == 1 else shutter3.close.put(0)
    sleep(0.25)
    if debug: 
        print ('shutter stats: %s, %s, %s' 
                % (shutter1.OCStatus.get(), shutter2.OCStatus.get(), shutter3.OCStatus.get()))
    if debug: print grabObject.filenameExtras
    if 'Pumped' in grabObject.filenameExtras:
        grabObject.filenameExtras = grabObject.filenameExtras.replace('Pumped', 'Static')
    else:
        grabObject.filenameExtras = '_' + 'Static'
    if debug: print grabObject.filenameExtras
    printMsg('Finished pumped image sequence')
    printSleep(grabObject.grabSeq2Delay)


def acqPumpProbe(grabObject, shutter1, shutter2, restoreShutters=True):
    """Do a pump-probe image grab sequence: open both shutters, and return them to
    initial state when finished."""
    functionName = 'acqPumpProbe'
    printMsg('Starting pump-probe acquisition')
    if restoreShutters:
        shutter1Stat = shutter1.OCStatus.get()
        shutter2Stat = shutter2.OCStatus.get()
    logging.debug('%s: shutter stats: %s, %s' % (functionName, shutter1.OCStatus.get(), shutter2.OCStatus.get()))
    printMsg('Opening shutters 1 and 2')
    shutter1.open.put(1)
    shutter2.open.put(1)
    sleep(0.5)
    shutter1.openCheck(val=0.5)
    shutter2.openCheck(val=0.5)
    logging.debug('%s: shutter stats: %s, %s' % (functionName, shutter1.OCStatus.get(), shutter2.OCStatus.get()))
    filenameExtras0 = grabObject.filenameExtras
    grabObject.filenameExtras = '_' + 'PumpProbe' + grabObject.filenameExtras
    grabObject.grabImages()    
    if restoreShutters:
        printMsg('Returning shutters to initial state')
        shutter1.open.put(1) if shutter1Stat == 1 else shutter1.close.put(0)
        shutter2.open.put(1) if shutter2Stat == 1 else shutter2.close.put(0)
        sleep(0.5)
    logging.debug('%s: shutter stats: %s, %s' % (functionName, shutter1.OCStatus.get(), shutter2.OCStatus.get()))
    grabObject.filenameExtras = filenameExtras0
    printMsg('Finished pump-probe acquisition')


def acqStatic(grabObject, shutter1, shutter2, restoreShutters=True):
    """Do a static image grab sequence: open shutter1, close shutter 2, and return them to
    initial state when finished."""
    functionName = 'acqStatic'
    printMsg('Starting static acquisition')
    if restoreShutters:
        shutter1Stat = shutter1.OCStatus.get()
        shutter2Stat = shutter2.OCStatus.get()
    printMsg('Opening shutter 1, closing shutter 2')
    shutter1.open.put(1)
    shutter2.close.put(0)
    sleep(0.5)
    shutter1.openCheck(val=0.5)
    shutter2.closeCheck(val=0.5)
    logging.debug('%s: shutter stats: %s, %s' % (functionName, shutter1.OCStatus.get(), shutter2.OCStatus.get()))
    filenameExtras0 = grabObject.filenameExtras
    grabObject.filenameExtras = '_' + 'Static' + grabObject.filenameExtras
    grabObject.grabImages()    
    if restoreShutters:
        printMsg('Returning shutters to initial state')
        shutter1.open.put(1) if shutter1Stat == 1 else shutter1.close.put(0)
        shutter2.open.put(1) if shutter2Stat == 1 else shutter2.close.put(0)
        sleep(0.5)
    logging.debug('%s: shutter stats: %s, %s' % (functionName, shutter1.OCStatus.get(), shutter2.OCStatus.get()))
    grabObject.filenameExtras = filenameExtras0
    printMsg('Finished static acquisition')

def acqPumpBG(grabObject, shutter1, shutter2, restoreShutters=True):
    """Do a pump-background image grab sequence: close shutter1, open shutter 2, and return them to
    initial state when finished."""
    functionName = 'acqPumpBG'
    printMsg('Starting pump BG acquisition')
    if restoreShutters:
        shutter1Stat = shutter1.OCStatus.get()
        shutter2Stat = shutter2.OCStatus.get()
    logging.debug('%s: shutter stats: %s, %s' % (functionName, shutter1.OCStatus.get(), shutter2.OCStatus.get()))
    printMsg('Closing shutter 1, opening shutter 2')
    shutter1.close.put(0)
    shutter2.open.put(1)
    sleep(0.5)
    shutter1.closeCheck(val=0.5)
    shutter2.openCheck(val=0.5)
    logging.debug('%s: shutter stats: %s, %s' % (functionName, shutter1.OCStatus.get(), shutter2.OCStatus.get()))
    filenameExtras0 = grabObject.filenameExtras
    grabObject.filenameExtras = '_' + 'PumpBG' + grabObject.filenameExtras
    grabObject.grabImages()    
    if restoreShutters:
        printMsg('Returning shutters to initial state')
        shutter1.open.put(1) if shutter1Stat == 1 else shutter1.close.put(0)
        shutter2.open.put(1) if shutter2Stat == 1 else shutter2.close.put(0)
        sleep(0.5)
    logging.debug('%s: shutter stats: %s, %s' % (functionName, shutter1.OCStatus.get(), shutter2.OCStatus.get()))
    grabObject.filenameExtras = filenameExtras0
    printMsg('Finished pump BG acquisition')


def acqDarkCurrent(grabObject, shutter1, shutter2, restoreShutters=True):
    """Do a dark-current image grab sequence: close both shutters, and return them to
    initial state when finished."""
    functionName = 'acqDarkCurrent'
    printMsg('Starting dark current acquisition')
    if restoreShutters:
        shutter1Stat = shutter1.OCStatus.get()
        shutter2Stat = shutter2.OCStatus.get()
    logging.debug('%s: shutter stats: %s, %s' % (functionName, shutter1.OCStatus.get(), shutter2.OCStatus.get()))
    printMsg('Closing both shutters')
    shutter1.close.put(0)
    shutter2.close.put(0)
    sleep(0.5)
    shutter1.closeCheck(val=0.5)
    shutter2.closeCheck(val=0.5)
    logging.debug('%s: shutter stats: %s, %s' % (functionName, shutter1.OCStatus.get(), shutter2.OCStatus.get()))
    filenameExtras0 = grabObject.filenameExtras
    grabObject.filenameExtras = '_' + 'DarkCurrent' + grabObject.filenameExtras
    grabObject.grabImages()    
    if restoreShutters:
        printMsg('Returning shutters to initial state')
        shutter1.open.put(1) if shutter1Stat == 1 else shutter1.close.put(0)
        shutter2.open.put(1) if shutter2Stat == 1 else shutter2.close.put(0)
        sleep(0.5)
    logging.debug('%s: shutter stats: %s, %s' % (functionName, shutter1.OCStatus.get(), shutter2.OCStatus.get()))
    grabObject.filenameExtras = filenameExtras0
    printMsg('Finished dark current acquisition')


def preScan(exp, pv1, grabObject=None):
    """Does pre-scan before main scan.  Pre-scan flag and scan parameters are set from PVs."""
    #inc1 = (pv1.pre_stop - pv1.pre_start)/(pv1.pre_nsteps - 1)
    printMsg('Doing pre-scan ' + '-'*20) 
    printMsg('Scanning %s from %f to %f in %d steps' % 
            (pv1.pvname, pv1.pre_start, pv1.pre_stop, pv1.pre_nsteps))
    for i in range(pv1.pre_nsteps):
        newPos1 = pv1.pre_start + i*pv1.inc
        printMsg('Setting %s to %f' % (pv1.pvname, newPos1))
        pv1.move(newPos1)
        printSleep(pv1.settletime,'Settling')
        if grabObject:
            if grabObject.grabFlag:
                if grabObject.stepFlag:
                    grabObject.filenameExtras = ('_prescan_' + pv1.desc + 
                            '-' + '{0:03d}'.format(i+1) + '-' + 
                            '{0:08.4f}'.format(pv1.get()))
                else:
                    grabObject.filenameExtras = ('_prescan_' + pv1.desc + 
                            '-' + '{0:08.4f}'.format(pv1.get()))
                grabObject.grabImages()
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


def printScanInfo(exp, scanpvs=None):
    """Print scan info."""
    print '################################'
    print('Scan mode: %s' % (exp.scanmodePv.get(as_string=True)))
    try:
        if scanpvs is not None:
            if exp.scanmode == 1:
                if scanpvs[0].pvname:
                    print('PV #1 type: %s' % (scanpvs[0].pvtypePv.get(as_string=True)))
                elif scanpvs[1].pvname and not scanpvs[0].pvname:
                    print('PV #2 type: %s' % (scanpvs[1].pvtypePv.get(as_string=True)))
                else:
                    pass
            elif exp.scanmode == 2:
                if scanpvs[0].pvname:
                    print('PV #1 type: %s' % (scanpvs[0].pvtypePv.get(as_string=True)))
                else:
                    print('PV #1 type: No PV entered')
                if scanpvs[1].pvname:   
                    print('PV #2 type: %s' % (scanpvs[1].pvtypePv.get(as_string=True)))
                else:
                    print('PV #2 type: No PV entered')
            else:
                pass
        else:
            pass
    except IndexError:
        print '***WARNING***: printScanInfo: IndexError'
    print '################################'


def frange(start, stop, step=1.0):
    """A range() for floats."""
    x = float(start)
    while x <= float(stop):
        yield x
        x += float(step)

def expandRange(strng):
    """Expands a matlab-style range string, e.g. 1:0.2:5, and generates a list of string values."""
    if re.match(r'([-+]?\d*\.\d+|\d+):([-+]?\d*\.\d+|\d+):([-+]?\d*\.\d+|\d+)', strng):
        start, step, stop = strng.split(':')
        lst = [str(x) for x in frange(start, stop, step)]
        return lst
    else:
        raise ValueError('expandRange: %s does not match pattern.' % strng)

def flattenList(lst):
    """Flattens a nested list. Does not flatten strings."""
    for x in lst:
        if hasattr(x, '__iter__') and not isinstance(x, basestring):
            for y in flattenList(x):
                yield y
        else:
            yield x

def isNumber(number):
    """Tests whether number is a number."""
    try:
        float(number)
        return True
    except ValueError:
        print 'isNumber: %s not a number.' % (number)
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

