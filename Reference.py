from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QObject, pyqtSignal
import logging

#name?
debuglogger = logging.getLogger(__name__)
hwlogger = logging.getLogger("D93 DEVICES")

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



class QLedLabel(QtWidgets.QLabel):
    SIZE = 20;
    green = "color: white;border-radius: %d ;background-color: qlineargradient(spread:pad, x1:0.145, y1:0.16, x2:1, y2:1, stop:0 rgba(20, 252, 7, 255), stop:1 rgba(25, 134, 5, 255));" % (SIZE/2)
    red = "color: white;border-radius: %d ;background-color: qlineargradient(spread:pad, x1:0.145, y1:0.16, x2:0.92, y2:0.988636, stop:0 rgba(255, 12, 12, 255), stop:0.869347 rgba(103, 0, 0, 255));" % (SIZE/2)
    orange = "color: white;border-radius: %d ;background-color: qlineargradient(spread:pad, x1:0.232, y1:0.272, x2:0.98, y2:0.959773, stop:0 rgba(255, 113, 4, 255), stop:1 rgba(91, 41, 7, 255))" % (SIZE/2)
    blue = "color: white;border-radius: %d ;background-color: qlineargradient(spread:pad, x1:0.04, y1:0.0565909, x2:0.799, y2:0.795, stop:0 rgba(203, 220, 255, 255), stop:0.41206 rgba(0, 115, 255, 255), stop:1 rgba(0, 49, 109, 255));" % (SIZE/2)

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)

        self.setState(0)
        self.setFixedSize(QLedLabel.SIZE,QLedLabel.SIZE)

    def setState(self, state):
        if state == 0: # Green
            self.setStyleSheet(QLedLabel.green)
            return
        if state == 1: # Orange
            self.setStyleSheet(QLedLabel.orange)
            return
        if state == 2: # Blue
            self.setStyleSheet(QLedLabel.blue)
            return
        self.setStyleSheet(QLedLabel.red)




class LabviewQDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    def textFromValue(self, value):
        # show + sign for positive values
        text = super().textFromValue(value)
        if value >= 0:
            text = "+" + text
        return text

    def stepBy(self, steps):
        cursor_position = self.lineEdit().cursorPosition()
        # number of characters before the decimal separator including +/- sign
        n_chars_before_sep = len(str(abs(int(self.value())))) + 1
        if cursor_position == 0:
            # set the cursor right of the +/- sign
            self.lineEdit().setCursorPosition(1)
            cursor_position = self.lineEdit().cursorPosition()
        single_step = 10 ** (n_chars_before_sep - cursor_position)
        # Handle decimal separator. Step should be 0.1 if cursor is at `1.|23` or
        # `1.2|3`.
        if cursor_position >= n_chars_before_sep + 2:
            single_step = 10 * single_step
        # Change single step and perform the step
        self.setSingleStep(single_step)
        super().stepBy(steps)
        # Undo selection of the whole text.
        self.lineEdit().deselect()
        # Handle cases where the number of characters before the decimal separator
        # changes. Step size should remain the same.
        new_n_chars_before_sep = len(str(abs(int(self.value())))) + 1
        if new_n_chars_before_sep < n_chars_before_sep:
            cursor_position -= 1
        elif new_n_chars_before_sep > n_chars_before_sep:
            cursor_position += 1
        self.lineEdit().setCursorPosition(cursor_position)

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




class Ui_ShutterWidget(object):
    def setupUi(self, ShutterWidget):
        ShutterWidget.setObjectName("ShutterWidget")
        ShutterWidget.resize(392, 132)
        self.verticalLayout = QtWidgets.QVBoxLayout(ShutterWidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.formLayout = QtWidgets.QFormLayout()
        self.formLayout.setObjectName("formLayout")
        self.label = QtWidgets.QLabel(ShutterWidget)
        self.label.setObjectName("label")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.label)
        self.statusHardware = QtWidgets.QLineEdit(ShutterWidget)
        self.statusHardware.setEnabled(False)
        self.statusHardware.setReadOnly(True)
        self.statusHardware.setObjectName("statusHardware")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.statusHardware)
        self.label_2 = QtWidgets.QLabel(ShutterWidget)
        self.label_2.setObjectName("label_2")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.label_2)
        self.lineEdit = QtWidgets.QLineEdit(ShutterWidget)
        self.lineEdit.setEnabled(False)
        self.lineEdit.setReadOnly(True)
        self.lineEdit.setObjectName("lineEdit")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.lineEdit)
        self.verticalLayout.addLayout(self.formLayout)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.openShutter = QtWidgets.QPushButton(ShutterWidget)
        self.openShutter.setObjectName("openShutter")
        self.horizontalLayout.addWidget(self.openShutter)
        self.closeShutter = QtWidgets.QPushButton(ShutterWidget)
        self.closeShutter.setObjectName("closeShutter")
        self.horizontalLayout.addWidget(self.closeShutter)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.quit = QtWidgets.QPushButton(ShutterWidget)
        self.quit.setObjectName("quit")
        self.verticalLayout.addWidget(self.quit)

        self.retranslateUi(ShutterWidget)
        self.quit.clicked.connect(ShutterWidget.close) # type: ignore
        QtCore.QMetaObject.connectSlotsByName(ShutterWidget)

    def retranslateUi(self, ShutterWidget):
        _translate = QtCore.QCoreApplication.translate
        ShutterWidget.setWindowTitle(_translate("ShutterWidget", "Form"))
        self.label.setText(_translate("ShutterWidget", "Status Hardware"))
        self.statusHardware.setText(_translate("ShutterWidget", "unknown"))
        self.label_2.setText(_translate("ShutterWidget", "Status Shutter"))
        self.lineEdit.setText(_translate("ShutterWidget", "unknown"))
        self.openShutter.setText(_translate("ShutterWidget", "Open"))
        self.closeShutter.setText(_translate("ShutterWidget", "Close"))
        self.quit.setText(_translate("ShutterWidget", "Quit"))

class ConsoleWindowLogHandler(logging.Handler, QObject):
    sigLog = pyqtSignal(str)
    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, logRecord):
        message = str(logRecord.getMessage())
        self.sigLog.emit(message)

