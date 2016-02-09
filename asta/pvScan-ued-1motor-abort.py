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
motor1='MOTR:AS01:MC01:CH8:MOTOR'
motor1Stop=PV(motor1 + '.STOP')

# Shutter disable PVs
shutter1TTLDisablePv=PV('ASTA:LSC01:TTL:IN:DISABLE')
shutter2TTLDisablePv=PV('ASTA:LSC02:TTL:IN:DISABLE')
shutter3TTLDisablePv=PV('ASTA:LSC03:TTL:IN:DISABLE')
shutterTTLDisablePVList=[shutter1TTLDisablePv,shutter2TTLDisablePv,shutter3TTLDisablePv]
# Shutter close PVs
shutter1ClosePv=PV('ASTA:LSC01:OC:CLOSE')
shutter2ClosePv=PV('ASTA:LSC02:OC:CLOSE')
shutter3ClosePv=PV('ASTA:LSC03:OC:CLOSE')
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
    # Disable shutters
    shutterFunction(shutterTTLDisablePVList,1)
    sleep(0.5)
    # Close shutters
    shutterFunction(shutterClosePVList,1)
    # Stop motors
    motor1Stop.put(1)
    print 'Aborted'
    msgpv.put('Aborted')

    
    

if __name__ == "__main__":
    "Do abort routine"
    abortRoutine()

        
##################################################################################################################
        

exit

