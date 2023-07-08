from PyQt5 import QtCore

from .picam import picam, PicamErrorLookup

import numpy as np

import logging
logger=logging.getLogger(__name__)

from ..utils.definitions import AcquisitionContext

class XUVCamera(QtCore.QObject):
    """ Wrapper class for PiCam, offers convenience functions to underlying library API """

    tempUpdated = QtCore.pyqtSignal(float)

    spectrumReady = QtCore.pyqtSignal(np.ndarray)
    spectrumFinished = QtCore.pyqtSignal()
    imageReady = QtCore.pyqtSignal(np.ndarray)
    imageFinished = QtCore.pyqtSignal()

    acquisitionStarted = QtCore.pyqtSignal()
    acquisitionStopped = QtCore.pyqtSignal()
    acquisitionFinished = QtCore.pyqtSignal()

    previewStarted = QtCore.pyqtSignal()
    previewStopped = QtCore.pyqtSignal()
    previewFinished = QtCore.pyqtSignal()


    errorLogged = QtCore.pyqtSignal(str)

    def __init__(self,cam=None) -> None:
        
        
        super().__init__()
        # init internal state
        self._acquisitionRunning = None
        self._previewRunning = None
        self._imageMode = False

        self._tainted = False # True if sendConfiguration needs to be called before next acquisition
        self._lingering = False # True if it should be checked if an aquisition has really stopped.
        
        self._exposure = 1 # Shadow exposure time to state
        # init timers
        self.logger = logger

        # initialize library
        # The library is initialized on import. Could consider importing here instead of at module level
        self.cam= picam()
        self.cam.loadLibrary()
        
    def add_logger(self):
        self.logger = logger

    def connect(self,camID=None):
        self.cam.getAvailableCameras()
        self.cam.connect(camID)

    def disconnect(self):
        self.cam.disconnect()

    def isConnected(self):
        return self.cam.is_opened()
        
    def getState(self):
        if self.cam.is_opened():
            return repr(self.cam.getCurrentCameraID())
        return "unknown"

    def setTemperature(self,value):
        self.cam.setParameter("SensorTemperatureSetPoint", value)
        self.cam.sendConfiguration() # In case of the temperature setpoint, commit directly.

    def getTemperature(self) -> float:
        temp = self.cam.getParameter("SensorTemperatureReading")
        self.tempUpdated.emit(temp)
        return temp
    
    def getSetpoint(self) -> float:
        return self.cam.getParameter("SensorTemperatureSetPoint")

    def setExposure(self,value: int):
        #self.cam.set_exposure(value) # pylablib counts in s, call to attribute directly to overwrite
        self.cam.setParameter("ExposureTime", value)
        self._exposure = value
        self._tainted = True

    def getExposure(self) -> int:
        self._exposure =  self.cam.getParameter("ExposureTime")
        return self._exposure

    def setGain(self,value: int):
        if 1<= value <= 3:
            self.cam.setParameter("AdcAnalogGain", value)
            self._tainted = True
        else:
            raise ValueError

    def getGain(self) -> int:
        return self.cam.getParameter("AdcAnalogGain")

    def setADCLowNoise(self,activate: bool):
        self.cam.setParameter("AdcQuality",1 if activate else 2)
        self._tainted = True

    def getADCLowNoise(self) -> bool:
        return self.cam.getParameter("AdcQuality") == 1

    def setSpeed(self,fast: bool):
        self.cam.setParameter("AdcSpeed",2.0 if fast else 0.1)
        self._tainted = True

    def getSpeed(self) -> bool:
        return int(self.cam.getParameter("AdcSpeed")) == 2

    def setROI(self,x0, w, y0, h, xbin=1, ybin=1):
        self.cam.setROI(x0, w, xbin, y0, h, self._imageBin(ybin,h)) # call signature of picam.py
        self._tainted = True

    def getROI(self):
        return self.cam.getROI()

    def setFullChip(self):
        w = self.cam.getParameter("ActiveWidth")
        h = self.cam.getParameter("ActiveHeight")
        self.cam.setROI(0,w,1,0,h,self._imageBin())

    def setImageMode(self,state):
        if not state == self._imageMode:
            self._imageMode = state
            rois=self.getROI()
            self.setROI(*rois[0:4])

    def getImageMode(self):
        return self._imageMode

    def _imageBin(self,ybin=1,height=400):
        return height if not self._imageMode else ybin


    def setFrameCount(self,nframes=1):
        self.cam.setParameter("ReadoutCount",nframes)
        self._tainted = True

    def getFrameCount(self):
        return self.cam.getParameter("ReadoutCount")


    def checkAcquisition(self):
        """ Return True if camera is ready to acquire image """
        if self.cam.isAcquisitionRunning():
            if self._lingering:
                while True:
                    err, _ = self.waitOnFrame(timeout=int(self._exposure)*10)
                    if err == 32: # TimeOut
                        logger.info("An acquisition is running or being processed.")
                        return False
                    if err == 0: # No error
                        continue
                    if err == 27: # AcquisitionNotInProgress
                        self._lingering = False
                        return True
                    logger.error("Camera is in unknown state. Error Message: {}".format(PicamErrorLookup[err]))
                    return False
            logger.info("An acquisition is already running or being processed.")
            return False  
        return True

    def commit(self):
        if self._tainted:
            self.cam.sendConfiguration()
            self._tainted = False

    def getFrame(self,nframes=1,timeout=-1):
        """ Starts exposure for one frame/nframes and then stops. 
        Function will block until Acquisition is finished. """
        # Check if acquisition is running.
        if not self.checkAcquisition():
            return None
        self.commit()
        if timeout==0: # estimate a safe timeout window
            timeout = min(1000,self._exposure*nframes*10)
        res = self.cam.readNFrames(N=nframes,timeout=timeout) 
        if res is None:
            # No data read, timeout likely occured.
            return None       
        if res[0].shape[1] == 1: # spectrum mode
            self.spectrumReady.emit(res[0][-1,0,:])
        else:
            self.imageReady.emit(res[0][-1,:])
        return res[0]

    def startFrame(self,nframes=1):
        """ Starts a continous acquisition. 
        Function will start acquisition and returns True if succesfull. Status needs to be polled. """
        if not self.checkAcquisition():
            return False
        self.commit()
        err = self.cam.startAcquisition()
        if err!=0:
            print(err)
            logger.warning("Error occured when starting Acquisition, Error Message: {}".format(PicamErrorLookup[err]))
            return False
        return True

    def grabFrame(self,timeout=0):
        """ Return all frames in buffer. If no frame remains in buffer, will return None."""
        err, res = self.waitOnFrame(timeout=timeout)
        if res is not None:
            self._lingering = True            
            if res[0].shape[1] == 1: # spectrum mode
                self.spectrumReady.emit(res[0][-1,0,:])
            else:
                self.imageReady.emit(res[0][-1,:])
        return err, res

    def clearFrames(self):
        """ Under certain circumstances it might be better to keep the camera in acquisition when changing experimental parameters (eg time-delay, open/close shutter)
        instead of stopping and setting up an acquisition (this will be true for very short exposurs). The frames taken between then need to be disregarded, which this method is suppose to achieve """
        while self.waitOnFrame()[1] is not None:
            pass

    def clearAcquisition(self):
        for _ in range(5):
            err, _ = self.waitOnFrame()
            if err == 0 or err == 27:
                self._lingering = False
                return True
        return False

    def waitOnFrame(self,timeout=0,frames=1):
        return self.cam.waitForFrame(timeout=timeout,frames=frames)

    def stopFrame(self):
        return self.cam.stopAcquisition()


    def requestAcquisitionLock(self):
        """ Request soft-lock on instance to perform an acquisition. Will release any preview-lock and return an AcquisitionContext. """
        if self.previewRunning:
            self.stopFrame()
            self.releasePreviewLock()

        if self._acquisitionRunning is not None:
            if not self._acquisitionRunning.finished:
                raise RuntimeError

        self._acquisitionRunning = AcquisitionContext()
        self._acquisitionRunning.acquisitionStarted.connect(self.acquisitionStarted)
        self._acquisitionRunning.acquisitionFinished.connect(self.acquisitionFinished)
        self._acquisitionRunning.acquisitionStopped.connect(self.acquisitionStopped)

        return self._acquisitionRunning


    def releaseAcquisitionLock(self):
        """ Release the acquisition soft-lock. Note this does not stop the camera loop, which will need to be called independently. """
        if self._acquisitionRunning is not None:
            self._acquisitionRunning.stop()
        self._acquisitionRunning = None


    def requestPreviewLock(self):
        """ Request soft-lock on instance to perform a preview. Will return None if instance is acuisition-locked and return an AcquisitionContext. """
        if self.acquisitionRunning:
            return None

        if self.previewRunning:
            return self._previewRunning

        self._previewRunning = AcquisitionContext()
        self._previewRunning.acquisitionStarted.connect(self.previewStarted)
        self._previewRunning.acquisitionFinished.connect(self.previewFinished)
        self._previewRunning.acquisitionStopped.connect(self.previewStopped)

        return self._previewRunning

    def releasePreviewLock(self):
        """ Release the preview soft-lock. Note this does not stop the camera loop, which will need to be called independently. """
        if self._previewRunning is not None:
            self._previewRunning.stop()
        self._previewRunning = None


    @property
    def acquisitionRunning(self):
        try:
            return not self._acquisitionRunning.finished
        except AttributeError:
            return False

    @property
    def previewRunning(self):
        try:
            return not self._previewRunning.finished
        except AttributeError:
            return False
    
    





    


