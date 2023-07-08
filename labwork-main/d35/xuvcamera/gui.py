import os

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5 import uic

import pyqtgraph as pg
from pyqtgraph import GraphicsLayoutWidget, ImageItem

import numpy as np

import logging
logger=logging.getLogger(__name__)

from ..utils.widgets import LabviewQDoubleSpinBox
from ..utils.definitions import ConsoleWindowLogHandler
from ..utils.functions import axes_to_rect

from .xuvcamera import XUVCamera, logger


class XUVCameraGui(QtWidgets.QMainWindow):
    HIST_LEN = 1000
    def __init__(self, *args, device=None,**kwargs):
        super().__init__()
        
        uic.loadUi(os.path.join(os.path.dirname(os.path.abspath(__file__)), "xuvcamera.ui"),self)

        self._initPlotUI()
        self._initTimers()
        self._registerSlots()

        # State variable to block signal/slot feedback when updating
        # UI elements from camera or calls.
        # This is since I couldn't get signalBlocker to work
        self._isUpdatingFromCam = False
        
        # Console handler
        consoleHandler = ConsoleWindowLogHandler()
        consoleHandler.sigLog.connect(self.logView.appendPlainText)
        logger.addHandler(consoleHandler)

        self.count_history = np.zeros(XUVCameraGui.HIST_LEN)
        self._connected = False

        if device is not None:
            self.dev = device
            self._setState("unknown")
            if not isinstance(device,XUVCamera):
                logger.warning("GUI was called with invalid camera reference, assuming local debug mode.")
                self._connected=False
            self.getState()
            
        else:
            logger.info("Initializing Princeton camera")
            self.dev = XUVCamera()
            self.connect()            
            self.getState()

        self._registerSignals()

    def _initPlotUI(self):
        plt_win = self.plotLayoutWidget # Reference to GraphicsLayourWidget defined in xuvcamera.ui

        self.pltImageView = plt_win.addPlot(row=0, col=0,colspan=5) # 2D Image view
        self.pltCountsView = plt_win.addPlot(row=0,col=5) # Counts Tracker
        self.pltSpectrumView = plt_win.addPlot(row=1,col=0,colspan=6) # Spectrum view


        self.pltImageView.setLabel('left','Y')
        self.pltImageView.setLabel('bottom','X')

        self.pltImage = ImageItem(np.random.normal(size=(1340,400)))
        self.pltImageView.addItem(self.pltImage)
        
        # Add colorBar to plot
        # Note: We set the initial value to (100,1800) as these were the limits
        # in the LabView program. Adjust accordingly.
        self.pltImageView.addColorBar( self.pltImage, values=(100,1800), colorMap='cet-r4', limits=(0,2**16-1)) # , interactive=False)

        #self.ImageRoi = pg.ROI([0, 0], [1340, 400], maxBounds=QtCore.QRect(0,0,1340,400), rotatable=False, pen=pg.mkPen('r', width=3))  # (1,9))
        #self.ImageRoi.sigRegionChangeFinished.connect(self._roi_update)  

        # Add ROI Items
        self.ImageRoiItems=dict(
            y_linearregion = pg.LinearRegionItem([0,400], orientation='horizontal', brush=pg.mkBrush(None), hoverBrush=pg.mkBrush(None)),
            x_linearregion = pg.LinearRegionItem([0,1340], orientation='vertical', brush=pg.mkBrush(None), hoverBrush=pg.mkBrush(None)),
            )
        
        for _, item in self.ImageRoiItems.items():
            item.sigRegionChangeFinished.connect(self._roi_update)
            item.setZValue(0)
            self.pltImageView.addItem(item)
        
        # self.pltImageView.addItem(self.ImageRoi)


        self.pltCountsView.setLabel('bottom','Time')
        self.pltCountsView.setLabel('left','Counts')
        self.pltCountsView.showGrid(x=True, y=True)

        self.pltCounts = self.pltCountsView.plot(pen=pg.mkPen('w'))


        self.pltSpectrumView.setLabel('bottom','X')
        self.pltSpectrumView.setLabel('left','Intensity')

        self.pltSpectrum = self.pltSpectrumView.plot(pen=pg.mkPen('w'))
        #self.pltSpectrumView.setXLink(self.pltImageView) # causing issues

        self.pltSpectrumView.setMinimumWidth(400)

        self.lockList = [self.cameraSettings, self.previewSpectrum, self.previewImage]

    def _initTimers(self):
        self._doSpectrum = QtCore.QTimer()
        self._doSpectrum.timeout.connect(self.doSpectrum)
        self._doSpectrum.setSingleShot(True)
        self._doImage = QtCore.QTimer()
        self._doImage.timeout.connect(self.doImage)
        self._doImage.setSingleShot(True)
        self._readTemp = QtCore.QTimer()
        self._readTemp.timeout.connect(self.readTemp)


    def _registerSlots(self):
        self.cameraConnectButton.clicked.connect(self.connect)
        self.cameraTempSpin.valueChanged.connect(self.changeTemperature)
        self.cameraGainBox.currentIndexChanged.connect(self.changeGain)
        self.cameraADCSpeedBox.currentIndexChanged.connect(self.changeSpeed)
        self.cameraADCSelect.currentIndexChanged.connect(self.changeADC)
        self.cameraROILeft.valueChanged.connect(self.setROI)
        self.cameraROIRight.valueChanged.connect(self.setROI)
        self.cameraROITop.valueChanged.connect(self.setROI)
        self.cameraROIBottom.valueChanged.connect(self.setROI)
        self.cameraAutoROI.clicked.connect(self.setROIfromWidget)
        self.cameraFullROI.clicked.connect(self.setROItoFull)
        self.cameraExposureSpin.valueChanged.connect(self.setExposure)

        self.previewSpectrum.clicked.connect(self.startSpectrum)
        self.previewImage.clicked.connect(self.startImage)
        self.previewStop.clicked.connect(self.stop)

    def _registerSignals(self):
        self.dev.tempUpdated.connect(self.temperatureChanged)
        self.dev.spectrumReady.connect(self.updateSpectrum)
        self.dev.imageReady.connect(self.updateImage)
        self.dev.acquisitionStarted.connect(self.interfaceLocked)
        self.dev.acquisitionFinished.connect(self.interfaceUnlocked)
        self.dev.acquisitionStopped.connect(self.interfaceUnlocked)
        self.dev.previewStopped.connect(self.cancelPreview)
        self.dev.previewFinished.connect(self.cancelPreview)

    def _setState(self,text):
        self.cameraStateText.setText(text)

    def temperatureChanged(self,value):
        self.cameraTempText.setText("%.1f" % value)

    def _roi_update(self):
        pass
        # We use the Auto ROI button to update ROIs

    def updateCounts(self,counts):
        self.count_history = np.roll(self.count_history,-1) # copy, slow for large histories, should be fine
        self.count_history[-1] = counts
        self.pltCounts.setData(x=np.arange(len(self.count_history)),y=self.count_history)

    def updateSpectrum(self,spectrum):
        self.pltSpectrum.setData(x=np.arange(len(spectrum)),y=spectrum)
        self.updateCounts(np.mean(spectrum))

    def updateImage(self,image):
        self.pltImage.setImage(image.T, autoRange=False,autoLevels=False)
        self.pltImage.setRect(self.getRect(image.T.shape))

        # self.plotImage.setRect(axes_to_rect())
        self.updateSpectrum(np.mean(image,axis=0))

    def getRect(self,shape):
        return QtCore.QRectF(self.cameraROILeft.value(),self.cameraROIBottom.value(),shape[0],shape[1])

    def interfaceLocked(self):
        for widget in self.lockList:
            widget.setDisabled(True)

    def interfaceUnlocked(self):
        for widget in self.lockList:
            widget.setDisabled(False)



    def getState(self):
        if self._connected:
            self._setState(self.dev.getState())

    def connect(self):
        if not self.dev.acquisitionRunning:
            self.statusbar.showMessage("Connecting...")
            self.dev.connect()
            self._connected = True
            self.statusbar.showMessage("Connected",2000)
            self.setExposure(self.cameraExposureSpin.value())
            self.changeGain(0)
            self.changeSpeed(1)
            self.changeADC(0)
            self.setROItoFull()
            self._readTemp.start(1000)
            self.getState()
        else:
            self.statusbar.showMessage("Acquisition currently running.",2000)

    def changeTemperature(self,value):
        if self._connected and not self.dev.acquisitionRunning:
            self.dev.setTemperature(value)
            self.statusbar.showMessage("Changed temperature Setpoint to %d" % value, 2000)

    def changeGain(self,index):
        if self._connected and not self.dev.acquisitionRunning:
            self.dev.setGain(index+1)

    def changeSpeed(self,index):
        if self._connected and not self.dev.acquisitionRunning:
            self.dev.setSpeed(index==1)

    def changeADC(self,index):
        if self._connected and not self.dev.acquisitionRunning:
            self.dev.setADCLowNoise(index==1)

    def setROI(self):
        x = self.cameraROILeft.value()
        y = self.cameraROIBottom.value()
        w = self.cameraROIRight.value() - x
        h = self.cameraROITop.value() - y
        if self._connected and not self.dev.acquisitionRunning and not self._isUpdatingFromCam:
            self.dev.setROI(x,w,y,h)


    def setROIfromWidget(self):
        axx_min, axx_max = self.ImageRoiItems["x_linearregion"].getRegion()
        axy_min, axy_max = self.ImageRoiItems["y_linearregion"].getRegion()        
        # pos = self.ImageRoi.pos()
        # size = self.ImageRoi.size()
        #with QtCore.QSignalBlocker(self.cameraSettings):
        try:
            self._isUpdatingFromCam = True
            self.cameraROILeft.setValue(int(round(axx_min)))
            self.cameraROIRight.setValue(int(round(axx_max)))
            self.cameraROIBottom.setValue(int(round(axy_min)))
            self.cameraROITop.setValue(int(round(axy_max)))
        finally:
            self._isUpdatingFromCam = False
            
        self.setROI()


    def setROItoFull(self):
        if self._connected and not self.dev.acquisitionRunning:
            self.dev.setFullChip()
            roi = self.dev.getROI()
            try:
                self._isUpdatingFromCam = True
                self.cameraROILeft.setValue(roi[0])
                self.cameraROIRight.setValue(roi[0]+roi[1])
                self.cameraROIBottom.setValue(roi[2])
                self.cameraROITop.setValue(roi[2]+roi[3])
            finally:
                self._isUpdatingFromCam = False


    def setExposure(self,value):
        if self._connected and not self.dev.acquisitionRunning:
            self.dev.setExposure(value)


    def readTemp(self):
        if self._connected and not self.dev.acquisitionRunning:
            _ = self.dev.getTemperature()

    def doSpectrum(self):
        return self.doImage() # Currently no difference in coding, so just do the same


    def doImage(self):
        if self._connected and not self.dev.acquisitionRunning:
            err, res = self.dev.grabFrame()
            if (err == 0 or err==27) and res == None:
                self.dev.startFrame()
            self._doImage.start(1) # loop to self.


    def startSpectrum(self):
        # prepare camera for preview
        if self.dev.requestPreviewLock():
            self.previewImage.setEnabled(False)
            self.previewSpectrum.setEnabled(False)
            self.previewSpectrum.setChecked(True)
            
            self.statusbar.showMessage("Preview Spectrum...")

            self.dev.setImageMode(False)
            self.dev.startFrame() # Start acquisition loop

            self.doSpectrum() # Repeatedly read image/frame

    def startImage(self):
        # prepare camera for preview
        if self.dev.requestPreviewLock():        
            self.previewImage.setEnabled(False)
            self.previewSpectrum.setEnabled(False)
            self.previewImage.setChecked(True)  

            self.statusbar.showMessage("Preview Image...")   

            self.dev.setImageMode(True)
            self.dev.startFrame() # Start acquisition loop

            self.doImage() # Repeatedly read image/frame
            
    def cancelPreview(self):
        self._doImage.stop()
        self.previewImage.setChecked(False)
        self.previewSpectrum.setChecked(False)                
        self.previewImage.setEnabled(True)
        self.previewSpectrum.setEnabled(True)

    def stop(self):
        # Depending on what's going on, do one of the following:
        if self.dev.acquisitionRunning:
            pass # This should launch a dialog warning the user about cancelling a running acquisition

        else:
            if self._doImage.isActive() or self._doSpectrum.isActive():
                self._doImage.stop()
                # self._doSpectrum.stop() # _doSpectrum timer currently unused.                
                
                if self.dev.previewRunning:

                    self.dev.stopFrame()
                    # Bug: Camera gets stuck with lingering acquisition
                    # Let's try to clear acquisition for a few times
                    # But not forever since we don't want to block UI
                    for _ in range(500):
                        if self.dev.clearAcquisition():
                            break
                        QtWidgets.QApplication.processEvents() # sleep
                    
                    self.dev.releasePreviewLock()                    
                    
                self.statusbar.clearMessage()
            else: # FIX: run clearAcquisition on extra stop button presses
                self.dev.clearAcquisition()






