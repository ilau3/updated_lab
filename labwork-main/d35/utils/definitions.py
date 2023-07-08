from PyQt5.QtCore import QObject, pyqtSignal
import logging

class AcquisitionContext(QObject):
    acquisitionStarted = pyqtSignal()
    acquisitionStopped = pyqtSignal()
    acquisitionFinished = pyqtSignal()

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._finished = False

    def __enter__(self):
        self._finished = False
        self.acquisitionStarted.emit()

    def __exit__(self):
        if not self._finished:
            self.acquisitionStopped.emit()
        self._finished = True

    def finish(self):
        self._finished = True
        self.acquisitionFinished.emit()

    def stop(self):
        self._finished = True
        self.acquisitionStopped.emit()

    @property
    def finished(self):
        return self._finished


class ConsoleWindowLogHandler(logging.Handler, QObject):
    sigLog = pyqtSignal(str)
    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, logRecord):
        message = str(logRecord.getMessage())
        self.sigLog.emit(message)
