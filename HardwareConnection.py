

from PyQt6 import QtCore, QtWidgets
from pipython import GCSDevice, GCSError
import logging


import time
from Reference import ShutterWidget, ClosedLoopStageWidget
import serial

#logger name?
logger = logging.getLogger(__name__)

class PIStageHardware(QtCore.QObject):
    signalDeviceConnect = QtCore.pyqtSignal()
    signalDeviceDisconnected = QtCore.pyqtSignal()
    newSetpoint = QtCore.pyqtSignal(float)
    newPosition = QtCore.pyqtSignal(float)
    onTarget = QtCore.pyqtSignal()
    onMove = QtCore.pyqtSignal()
    
    def __init__(self):
        super().__init__()


    def open(self,model=None,serial=None,connect_type=None,com_port=None,ip=None,baudrate=115200,fastmode=False):
        if model is None:
            raise AttributeError
        self._dev = GCSDevice(model)
        if serial is not None and connect_type == 'USB':
            self._dev.ConnectUSB(serial)
        elif com_port is not None and connect_type == "RS232":
            self._dev.ConnectRS232(comport=com_port, baudrate=baudrate)
        elif ip is not None and connect_type == "IP":
            self._dev.ConnectTCPIP(ipaddress=ip)
        else:
            self._dev.InterfaceSetupDlg()

        logger.info("Connected to device: " + self._dev.qIDN().strip())

        if fastmode:
            self._dev.errcheck = False

        self.signalDeviceConnect.emit()

    def close(self):
        self._dev.CloseConnection()

    def getLimits(self,axes="1"):
        return self.getMinimum(axes), self.getMaximum(axes)

    def getMinimum(self,axes="1"):
        return self._dev.qTMN(axes)[axes]

    def getMaximum(self,axes="1"):
        return self._dev.qTMX(axes)[axes]

    def startup(self,axes="1"):
        self._dev.SVO(axes,1)

    def shutdown(self,axes="1"):
        self._dev.SVO(axes,0)

    def getPosition(self,axes="1"):
        pos = self._dev.qPOS(axes)[axes]
        self.newPosition.emit(pos)
        return pos

    def getTarget(self,axes="1"):
        return self._dev.qMOV(axes)[axes]

    def setPosition(self,position,axes="1"):
        self._dev.MOV(axes,position)
        self.newSetpoint.emit(position)

    def isPosition(self,position,eps=0.001,axes="1"):
        pos = self.getPosition()
        return abs(position-pos)<eps and self.isOnTarget()

    def isOnTarget(self,axes="1"):
        state = self._dev.qONT(axes)[axes]
        if state:
            self.onTarget.emit()
        return state

    def isMoving(self,axes="1"):
        state = self.isOnTarget(axes)
        if not state:
            self.onMove.emit()
        return not state




    """
    def open(self,model=None,serial=None,connect_type=None,com_port=None,ip=None,baudrate=115200,fastmode=False,axes="1"):
        if model is None:
            raise AttributeError

        self._dev = GCSDevice(model)
        if serial is not None and connect_type == 'USB':
            self._dev.ConnectUSB(serial)
        elif com_port is not None and connect_type == "RS232":
            if model == "E-516":
                self._dev = self.openGCS1(com_port)
            else:
                self._dev.ConnectRS232(comport=com_port, baudrate=baudrate)
        elif ip is not None and connect_type == "IP":
            self._dev.ConnectTCPIP(ipaddress=ip)
        else:
            self._dev.InterfaceSetupDlg()

        logger.info("Connected to device: " + self._dev.qIDN().strip())

        if fastmode:
            self._dev.errcheck = False

        self.axes=axes
        self.signalDeviceConnect.emit()

    def openGCS1(self,com_port=None,baudrate=19200):
        from pipython.pidevice.gcscommands import GCSCommands
        from pipython.pidevice.gcsmessages import GCSMessages
        from pipython.pidevice.interfaces.piserial import PISerial
        gateway =  PISerial(port=com_port, baudrate=baudrate)
        messages = GCSMessages(gateway)
        return GCSCommands(messages)

    def close(self):
        self._dev.CloseConnection()

    def getLimits(self):
        return self.getMinimum(self.axes), self.getMaximum(self.axes)

    def getMinimum(self):
        return self._dev.qTMN(self.axes)[self.axes]

    def getMaximum(self):
        return self._dev.qTMX(self.axes)[self.axes]

    def startup(self,axes="1"):
        self._dev.SVO(self.axes,1)

    def shutdown(self):
        self._dev.SVO(self.axes,0)

    def getPosition(self):
        pos = self._dev.qPOS(self.axes)[self.axes]
        self.newPosition.emit(pos)
        return pos

    def getTarget(self):
        return self._dev.qMOV(self.axes)[self.axes]

    def setPosition(self,position):
        self._dev.MOV(self.axes,position)
        self.newSetpoint.emit(position)

    def isPosition(self,position,eps=0.001):
        pos = self.getPosition()
        return abs(position-pos)<eps and self.isOnTarget()
        
    def isOnTarget(self):
        state = self._dev.qONT(self.axes)[self.axes]
        if state:
            self.onTarget.emit()
        return state

    def isMoving(self):
        state = self.isOnTarget(self.axes)
        if not state:
            self.onMove.emit()
        return not state
    """

class PIStageWidget(ClosedLoopStageWidget):
    def __init__(self,device=None,parent=None,label="PI Stage",**kwargs):
        super().__init__(parent,label=label,**kwargs)        
        if device is None:
            device = PIStageHardware(**kwargs)
        self._dev = device
        self._dev.signalDeviceConnect.connect(self.setStateOK)

        self.newSetpoint.connect(self.changeSetpoint)
       

    def _update(self):
        try:
            self.updatePos(self._dev.getPosition())
            if self._dev.isOnTarget: 
                self.setStateOK() 
            else: 
                self.setStateMoving()
        except GCSError as e:
            self.updateStateError()
            ClosedLoopStageWidget.handleError(self,e)



    def setStateOK(self):
        self.updateState(0)

    def setStateError(self):
        self.updateState(-1)

    def setStateMoving(self):
        self.updateState(1) # orange

    def changeSetpoint(self,value):
        try:
            self._dev.setPosition(value)
        except GCSError as e:
            self.updateStateError()
            self.handleError(e)


class ThorlabsShutterHardware(QtCore.QObject):
    signalOpenedShutter = QtCore.pyqtSignal()
    signalClosedShutter = QtCore.pyqtSignal()
    signalDeviceConnect = QtCore.pyqtSignal()
    signalDeviceDisconnected = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self._shadowShutter = None # Local copy of desired state

	## changed to accomodate SC10, true if shutter is open 
    def _queryState(self):
        jump = self._dev.write('ens?\r'.encode())
        self._dev.read(size=jump)
        res = self._dev.read()
        self._dev.read(size=3)
        if  res == b'1':
            return True
        elif res == b'0':
            return False       

    def _emitSignal(self, state):
        if state: self.signalOpenedShutter.emit() 
        else: self.signalClosedShutter.emit()

    #### changed to comport, set default baud rate to 9600 but could consider increasing through terminal. 
    def open(self,comport=None,baud=9600):
        if comport is None:
            try:
                comport = 'COM5'
            except NameError:
                # Could try to connect to the first shutter we can find
                # But for now let's give up
                raise
        self._dev = serial.Serial(comport,baud,timeout=1,parity=serial.PARITY_NONE,stopbits=serial.STOPBITS_ONE,bytesize=serial.EIGHTBITS)
	## sets mode to manual
        jump = self._dev.write("mode=1\r".encode())
        self._dev.read(size=jump+2)
        self.signalDeviceConnect.emit()
        self._shadowShutter = self.getShutter(forceEmit=True)
	## deal with this safety feature later 
	#if self._queryState():
           # self._dev.setShutter(False)     
    
    ### changed already 
    def close(self):
        self._dev.close()

    def setShutter(self,state=False,timeout=1000):
        """ Open or close the shutter, shutter will open if state is set to true. 
        If timeout is 0, will not check if shutter movement completed.
        If timeout is <0 will wait until shutter movement completed
        If timeout is >0 will wait value in ms for shutter to movement to complete or raise TimeoutError """
        # If the state of the shutter doesn't match the set state, it toggles the shutter. 
        if self._queryState() != state:
            jump = self._dev.write('ens\r'.encode())
            self._dev.read(size=jump+2)
        #self._dev.send_comm(0x04CB,0x00,0x01 if state else 0x02)
        if timeout != 0:
            return self.waitOnShutter(state,timeout)


    def waitOnShutter(self,state: bool,timeout=1000):
        """ Wait until shutter reports complete opening """
        start = time.time()
        while self._queryState() is not state:
            QtWidgets.QApplication.processEvents()
            if timeout>=0 and (time.time()-start)>(timeout/1000.):
                raise TimeoutError
        self._shadowShutter = state
        self._emitSignal(state)
        return state

    def getShutter(self,forceEmit=False):
        """ Query the state of the shutter, return true if shutter is open """
        # As per Thorlabs Doc, Req SOL is 0x04CC
        state = self._queryState()
        if state is not self._shadowShutter or forceEmit:
            self._emitSignal(state)
            self._shadowShutter = state
        return state

class ThorlabsShutterWidget(ShutterWidget):
    def __init__(self,device=None,parent=None):
        if device is None:
            device = ThorlabsShutterHardware()
        self._dev = device
        super().__init__(parent)

        self.signalOpenShutter.connect(self.openShutter)
        self.signalCloseShutter.connect(self.closeShutter)

        self._dev.signalOpenedShutter.connect(self.shutterOpened)
        self._dev.signalClosedShutter.connect(self.shutterClosed)

        
    def openShutter(self):
        self._dev.setShutter(True)

    def closeShutter(self):
        self._dev.setShutter(False)

    def _update(self):
        self._dev.getShutter()