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
motor1='ESB:XPS1:m4:MOTR'
motor1Stop=PV(motor1 + '.STOP')

# Shutters to be inserted
laserShutter1Pv=PV('ESB:GP01:VAL01')
laserShutter2Pv=PV('ESB:GP01:VAL02')


##################################################################################################################            
    
def abortRoutine():
    "This is the abort routine"
    msgpv.put('Aborting')
    # kill scan routine process
    os.kill(pid, signal.SIGKILL)
    # block laser
    laserShutter1Pv.put(0)
    laserShutter2Pv.put(0)  # just in case
    # stop stages
    motor1Stop.put(1)
    print 'Aborted'
    msgpv.put('Aborted')

    
    

if __name__ == "__main__":
    "Do abort routine"
    abortRoutine()

        
##################################################################################################################
        

exit

