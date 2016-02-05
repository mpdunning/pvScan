#!/usr/bin/env python
# For aborting scans.  
# mdunning 1/7/16

from epics import caget,caput,PV,Motor
from time import sleep
import datetime,math,os,sys,signal
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

# Get PID PV
pidPV=PV(pvPrefix + ':PID')
pid=pidPV.get()

# PV for status message
msgpv=PV(pvPrefix + ':MSG')

# Motors to be stopped
motor1='ESB:XPS1:m3'
motor1Stop=PV(motor1 + ':MOTR.STOP')
motor2='ESB:XPS1:m6'
motor2Stop=PV(motor2 + ':MOTR.STOP')
motor3='ESB:XPS1:m7'
motor3Stop=PV(motor3 + ':MOTR.STOP')

# Shutters to be inserted
#laserShutter1Pv=PV('')
#laserShutter2Pv=PV('')
#laserShutter3Pv=PV('')
shutter1TTLDisablePv=PV('ESB:GP01:VAL01')
shutter2TTLDisablePv=PV('ESB:GP01:VAL02')
shutter3TTLDisablePv=PV('ESB:GP01:VAL03')
shutterTTLDisablePVList=[shutter1TTLDisablePv,shutter2TTLDisablePv,shutter3TTLDisablePv]
shutter1ClosePv=PV('ESB:GP01:VAL01')
shutter2ClosePv=PV('ESB:GP01:VAL02')
shutter3ClosePv=PV('ESB:GP01:VAL03')
shutterClosePVList=[shutter1ClosePv,shutter2ClosePv,shutter3ClosePv]



##################################################################################################################            

def shutterFunction(shutterPVList,pvVal=1,wait=True):
    "Opens, Closes, or Enables/Disables TTL Input for shutters, depending on which PVs are passed in. Takes a list of PVs as an argument."
    for shutterPV in shutterPVList:
        shutterPV.put(pvVal,wait)
    
def abortRoutine():
    "This is the abort routine"
    msgpv.put('Aborting')
    # kill scan routine process
    os.kill(pid, signal.SIGKILL)
    # Disable and close shutters
    shutterFunction(shutterTTLDisablePVList,0)
    shutterFunction(shutterClosePVList,0)
    # Stop motors
    motor1Stop.put(1)
    motor2Stop.put(1)
    motor3Stop.put(1)
    print 'Aborted'
    msgpv.put('Aborted')

    
    

if __name__ == "__main__":
    "Do abort routine"
    abortRoutine()

        
##################################################################################################################
        

exit

