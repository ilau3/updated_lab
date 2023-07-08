from PyQt5 import QtCore, QtGui, QtWidgets
from .generated.ShutterWidget import Ui_ShutterWidget
#from .generated.closedLoopStageWidget import Ui_closedLoopStageWidget
from .base import QLedLabel, LabviewQDoubleSpinBox

import logging
debuglogger = logging.getLogger(__name__)
hwlogger = logging.getLogger("D35 DEVICES")

class ShutterWidget(QtWidgets.QWidget):
    signalOpenShutter = QtCore.pyqtSignal()
    signalCloseShutter = QtCore.pyqtSignal()

    def __init__(self,parent=None):
        super().__init__(parent)
        self.ui = Ui_ShutterWidget()
        self.ui.setupUi(self)

        self.ui.openShutter.clicked.connect(self.signalOpenShutter.emit)
        self.ui.closeShutter.clicked.connect(self.signalCloseShutter.emit)

    def shutterOpened(self):
        self.ui.openShutter.setEnabled(False)
        self.ui.closeShutter.setEnabled(True)
        self.ui.lineEdit.setText("Open") #BUG, see issue #1

    def shutterClosed(self):
        self.ui.openShutter.setEnabled(True)
        self.ui.closeShutter.setEnabled(False)
        self.ui.lineEdit.setText("Close") #BUG, see issue #1

    def stateUnknown(self):
        self.ui.openShutter.setEnabled(False)
        self.ui.closeShutter.setEnabled(False)
        self.ui.lineEdit.setText("unknown") #BUG, see issue #1

    def updateHardware(self,text):
        self.ui.statusHardware.setText(text)

class ClosedLoopStageWidget(QtWidgets.QWidget):
    newSetpoint = QtCore.pyqtSignal(float)

    def __init__(self,parent=None,label="unknown",raise_on_error=True,digits=2):
        super().__init__(parent)
        self.digits = digits
        self.initUI(label,digits)
        self.raise_on_error = raise_on_error

    def initUI(self,label,digits):
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.label = QtWidgets.QLabel(label)
        self.label.setObjectName(label)

        self.horizontalLayout.addWidget(self.label)

        self.setpoint = LabviewQDoubleSpinBox()
        self.setpoint.setDecimals(digits)
        self.setpoint.valueChanged.connect(self.newSetpoint.emit)

        self.horizontalLayout.addWidget(self.setpoint)

        self.position = QtWidgets.QLineEdit()
        self.position.setEnabled(False)
        self.horizontalLayout.addWidget(self.position)

        self.indicator = QLedLabel()
        self.horizontalLayout.addWidget(self.indicator)

        self.setLayout(self.horizontalLayout)

    def updatePos(self,value: float):
        self.position.setText('{:.{prec}f}'.format(value, prec=self.digits))

    def updateState(self,state):
        self.indicator.setState(state)

    def handleError(self,error):
        hwlogger.warning("Error encountered with stage {0}: {1}".format(self.label,error))
        if self.raise_on_error:
            raise error

    def _setpointFromPosition(self):
        """ Sets the widget setpoint to the read value. """
        with QtCore.QSignalBlocker(self) as _:
            try:
                self.setpoint.setValue(round(float(self.position.text()),self.digits))
            except ValueError:
                pass


class StageController(QtWidgets.QWidget):
    refresh = QtCore.pyqtSignal()

    def __init__(self,parent=None,stages=[],shutters=[]):
        super().__init__(parent)
        self.initUI()
        for stage in stages:
            self.insertStage(stage)
        for shutter in shutters:
            self.insertShutter(shutter)

        self._timeUpdate = QtCore.QTimer()
        self._timeUpdate.timeout.connect(self.update)


    def initUI(self):
        vbox = QtWidgets.QVBoxLayout()

        self.groupstages = QtWidgets.QGroupBox("Stages")
        self.groupshutters = QtWidgets.QGroupBox("Shutters")
        self.stages = QtWidgets.QVBoxLayout()
        self.shutters = QtWidgets.QVBoxLayout()
        
        self.groupstages.setLayout(self.stages)
        self.groupshutters.setLayout(self.shutters)

        vbox.addWidget(self.groupstages)
        vbox.addWidget(self.groupshutters)



        group = QtWidgets.QGroupBox("Acquisition Control")
        hbox = QtWidgets.QHBoxLayout(group)
        self.pauseButton = QtWidgets.QPushButton("Pause")
        self.pauseButton.setCheckable(True)
        self.stopButton = QtWidgets.QPushButton("Stop")
        self.stopButton.setCheckable(True)
        self.abortButton = QtWidgets.QPushButton("Abort")
        self.abortButton.setCheckable(True)
        hbox.addWidget(self.pauseButton)
        hbox.addWidget(self.stopButton)
        hbox.addWidget(self.abortButton)
        vbox.addWidget(group)
        
        self.logView = QtWidgets.QPlainTextEdit()

        vbox.addWidget(self.logView)
        
        hbox = QtWidgets.QHBoxLayout()
        updatePeriodLabel = QtWidgets.QLabel("FPS: ")
        self.updatePeriod = QtWidgets.QSpinBox()
        self.updatePeriod.setMinimum(1)
        self.updatePeriod.setMaximum(60)
        self.updatePeriod.setValue(1)
        self.updatePeriod.valueChanged.connect(self.restartTimer)

        self.doUpdateButton = QtWidgets.QPushButton("self-update")
        self.doUpdateButton.setCheckable(True)
        self.doUpdateButton.clicked.connect(self.onUpdateClick)

        hbox.addWidget(updatePeriodLabel)
        hbox.addWidget(self.updatePeriod)
        hbox.addWidget(self.doUpdateButton)

        vbox.addLayout(hbox)        

        self.setLayout(vbox)

    def insertStage(self,stage):
        if stage is None:
            line = QtWidgets.QFrame()
            line.setFrameShape(QtWidgets.QFrame.HLine)
            line.setFrameShadow(QtWidgets.QFrame.Sunken)
            self.stages.addWidget(line)
        else:
            self.stages.addWidget(stage)

    def insertShutter(self,shutter):
        self.shutters.addWidget(shutter)

    def update(self,overwriteSetpoints=False):
        """ Manually updates all widgets in the control window.
        If overwriteSetpoints is True, the current position will be written
        to the widgets' setpoint widget (but not to the hardware) """
        for widget in self.groupstages.children():
            if isinstance(widget,QtWidgets.QFrame):
                continue
            try:
                if widget.isEnabled(): # only update enabled widgets.
                    widget._update()
                    if overwriteSetpoints:
                        widget._setpointFromPosition()
            except AttributeError:
                debuglogger.debug("Illegal widget")

        for widget in self.groupshutters.children():
            try:
                widget._update()
            except AttributeError:
                debuglogger.debug("Illegal widget")

    def onUpdateClick(self,checked):
        if checked:
            T = 1000//self.updatePeriod.value() # period in ms from FPS
            self._timeUpdate.start(T)
        else:
            self._timeUpdate.stop()

    def restartTimer(self):
        self._timeUpdate.stop()
        if self.doUpdateButton.isChecked():
            T = 1000//self.updatePeriod.value() # period in ms from FPS
            self._timeUpdate.start(T)

    def start(self):
        self.doUpdateButton.setChecked(True)
        self.restartTimer()

    def stop(self):
        self.doUpdateButton.setChecked(False)
        self.restartTimer()

    @property
    def paused(self):
        return self.pauseButton.isChecked()

    @property
    def stopped(self):
        return self.stopButton.isChecked()

    @property
    def aborted(self):
        return self.abortButton.isChecked()


