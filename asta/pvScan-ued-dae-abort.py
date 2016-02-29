#!/usr/bin/env python
# For aborting scans.  
# mdunning 1/7/16

from epics import PV
from time import sleep
import os,sys,signal

# PV prefix for pvScan IOC; should be passed as an argument to this script.
pvPrefix=sys.argv[1]
# Set an environment variable for so pvScan module can use it
os.environ['PVSCAN_PVPREFIX']=pvPrefix

# Import pvScan module
sys.path.append('/afs/slac/g/testfac/extras/scripts/pvScan/prod/modules/')
import pvscan

# Get PID PV
pid=pvscan.pidPV.get()

#--- Scan PVs ------------------------------------------
# Create Motor objects, one for each PV you are scanning. 
# First argument is the scan PV, leave blank to get from pvScan IOC. 
# Second arg is an index which should be unique.
motor1=pvscan.PolluxMotor('ASTA:POLX01:AO:ABSMOV',1)  # (UED pitch motor)
motor2=pvscan.Motor('MOTR:AS01:MC02:CH8:MOTOR',2)  # (UED Y motor)
motor3=pvscan.Motor('MOTR:AS01:MC02:CH2:MOTOR',3)  # (UED Z motor)
motor4=pvscan.Motor('MOTR:AS01:MC02:CH7:MOTOR',4)  # (UED X motor)
motor5=pvscan.Motor('MOTR:AS01:MC01:CH8:MOTOR',5)  # (UED Delay motor)

#--- Shutters -----------------------------------------
# Create Shutter objects. 
# First argument is shutter PV.
# Second arg (optional) is an RBV PV, for example an ADC channel.
shutter1=pvscan.LSCShutter('ASTA:LSC01') # (UED Drive laser)
shutter2=pvscan.LSCShutter('ASTA:LSC02') # (UED pump laser)
shutter3=pvscan.LSCShutter('ASTA:LSC03') # (UED HeNe laser)
#
# Create ShutterGroup object to use common functions on all shutters.
# Argument is a list of shutter objects.
shutterGroup1=pvscan.ShutterGroup([shutter1,shutter2,shutter3])
shutterGroup2=pvscan.ShutterGroup([shutter2,shutter3])

##################################################################################################################            
def abortRoutine():
    "This is the abort routine"
    pvscan.printMsg('Aborting')
    # Stop motors
    pvscan.printMsg('Stopping motors')
    motor1.abort.put(1)
    motor2.abort.put(1)
    motor3.abort.put(1)
    # Kill scan routine process
    pvscan.printMsg('Killing process %d...' % (pid))
    os.kill(pid, signal.SIGKILL)
    # Disable shutters
    #pvscan.printMsg('Disabling shutters')
    #pvscan.shutterFunction(shutterGroup1.ttlInDisable,0)
    #sleep(0.5)
    # Close/disable shutters
    pvscan.printMsg('Disabling TTL In for all shutters')
    pvscan.shutterFunction(shutterGroup1.ttlInDisable,1)
    pvscan.printMsg('Closing pump and HeNe shutters')
    pvscan.shutterFunction(shutterGroup2.close,1)
    pvscan.printMsg('Aborted')


if __name__ == "__main__":
    "Do abort routine"
    args='PV_PREFIX'
    def show_usage():
        "Prints usage"
        print 'Usage: %s %s' %(sys.argv[0], args)
    if len(sys.argv) != 2:
        show_usage()
        sys.exit(1)
    abortRoutine()

##################################################################################################################
        

exit

