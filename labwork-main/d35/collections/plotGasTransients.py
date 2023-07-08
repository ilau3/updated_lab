"""
A GUI to evaluate Gas Transients
"""
from PyQt5 import QtWidgets, QtCore, QtGui, uic
import pyqtgraph as pg
from pyqtgraph import GraphicsLayoutWidget, ImageItem

import numpy as np
import h5py
import os, sys
from time import strftime, localtime

import logging
import warnings
from ..utils.definitions import ConsoleWindowLogHandler
from ..utils.functions import find_index, axes_to_rect, highpass

from scipy.stats import exponnorm, norm, expon
from scipy.optimize import curve_fit, OptimizeWarning
from scipy.ndimage import uniform_filter1d

class GasTransientsGui(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__()
        
        uic.loadUi(os.path.join(os.path.dirname(os.path.abspath(__file__)), "plotGasTransients.ui"),self)

        self._initPlotUI()
        self._registerSlots()

        self.logger = logging.getLogger(__name__)
        # Console handler
        consoleHandler = ConsoleWindowLogHandler()
        consoleHandler.sigLog.connect(self.logView.appendPlainText)
        self.logger.addHandler(consoleHandler)


        self.fileModel = QtWidgets.QFileSystemModel()
        try:
            rootDir = kwargs["dir"]
        except KeyError:
            rootDir = QtCore.QStandardPaths.locate(QtCore.QStandardPaths.DesktopLocation,"XUVData",QtCore.QStandardPaths.LocateDirectory) # Find XUVData folder on Desktop
        
        # Check if directory exists.
        self.fileModel.setRootPath(rootDir)

        self.directoryPath.setText(rootDir)
        self.fileListView.setModel(self.fileModel)
        self.fileListView.setRootIndex(self.fileModel.index(rootDir))

        # Init variables
        self.data_y = None
        self.data_x = None
        self.data_im = None
        self.data_im_display = None

        # Create a thread that we'll use to run the fits in.
        self.fitThread = QtCore.QThread()
        self.use_thread = False # Debug mode

    def _initPlotUI(self):
        plt_win = self.plotLayoutWidget # Reference to GraphicsLayourWidget defined in xuvcamera.ui

        self.pltImageView = plt_win.addPlot(row=0, col=0) # 2D Image view
        self.pltTimeView = plt_win.addPlot(row=0,col=1) # Time Marginals
        self.pltSpectrumView = plt_win.addPlot(row=1,col=0) # Spectrum Marginals
        self.pltFitView = plt_win.addPlot(row=1,col=1) # Traces & Fit results


        self.pltImageView.setLabel('left','Delay')
        self.pltImageView.setLabel('bottom','X')

        self.pltImage = ImageItem(np.random.normal(size=(1340,100)))
        self.pltImageView.addItem(self.pltImage)
        
        # Add colorBar to plot
        self.pltImageCBar = self.pltImageView.addColorBar( self.pltImage, values=(-1000,1000), colorMap='CET-L9', limits=(-4000,4000)) # , interactive=False)

        # Add ROI Items
        self.pltImageViewItems=dict(
            y_linearregion = pg.LinearRegionItem([0,100], orientation='horizontal', brush=pg.mkBrush(None), hoverBrush=pg.mkBrush(None)),
            x_linearregion = pg.LinearRegionItem([25,1340], orientation='vertical', brush=pg.mkBrush(None), hoverBrush=pg.mkBrush(None)),
            background_region = pg.LinearRegionItem([0,10], orientation='horizontal', pen=pg.mkPen('b'), brush=pg.mkBrush(None), hoverBrush=pg.mkBrush(None)),
            )
        
        for _, item in self.pltImageViewItems.items():
            item.sigRegionChangeFinished.connect(self.plotMarginals)
            item.setZValue(0)
            self.pltImageView.addItem(item)


        self.pltTimeView.showGrid(x=True, y=True)
        self.pltTime = self.pltTimeView.plot(pen=pg.mkPen('w'))

        self.pltSpectrum = self.pltSpectrumView.plot(pen=pg.mkPen('w'))
        self.pltSpectrumView.setXLink(self.pltImageView)
        # self.pltTimeView.setYLink(self.pltImageView)

        # self.pltSpectrumView.setMinimumWidth(400)

        
        self.fitLineA = self.pltFitView.plot(pen=pg.mkPen('w'))
        self.fitLineB = self.pltFitView.plot(pen=pg.mkPen('y'))
        self.fitScatterA =self.pltFitView.plot(pen=None,symbolPen=pg.mkPen(None),symbolBrush='w')
        self.fitScatterB =self.pltFitView.plot(pen=None,symbolPen=pg.mkPen(None),symbolBrush='y')
        


    def _registerSlots(self):
        self.fileListView.clicked.connect(self.selectFile)
        self.fileListView.doubleClicked.connect(self.selectDirectory)
        self.browsePathButton.clicked.connect(self.browsePath)
        self.runFitButton.clicked.connect(self.fit)
        self.refreshPlot.clicked.connect(self.refresh)


    def selectFile(self,modelIndex):
        if self.fileModel.isDir(modelIndex):
            # single click on a folder nop.
            return

        if "gasTransient" in self.fileModel.fileName(modelIndex):
            self.loadFile(self.fileModel.filePath(modelIndex))
        else:
            self.logger.info("Won't load {} since it doesn't pass the filter.".format(self.fileModel.fileName(modelIndex)))

    def selectDirectory(self,modelIndex):
        if self.fileModel.isDir(modelIndex):
            self.fileListView.setRootIndex(modelIndex)
            self.directoryPath.setText(self.fileListView.filePath(modelIndex))
        else:
            # double click on a file, delegate to selectFile
            self.selectFile(modelIndex)

    def loadFile(self,filePath):
        # load a file, update plots, run fitting if enabled
        with h5py.File(filePath,'r') as f:
            try:
                if not f.attrs['experiment_type']=="gasTransient":
                    self.logger.warning("Loaded File does not appear to be a Gas Transient")

                f_data = f['data/res0'] # Hardcode for now, in reality might be more complex and we'd need to traverse the tree
                fileDict = dict(
                    name=os.path.basename(filePath),
                    info=f.attrs['fileinfo'],
                    timestamp=f.attrs['timestamp'],
                    delayPoints=len(f['data/res0'].attrs["delays"],),
                    experimentType=f.attrs['experiment_type'])
                self.data_y = f_data.attrs['delays']
                try:
                    self.data_x = f_data.attrs['x_axis']
                except KeyError:
                    self.data_x = np.arange(f_data.shape[-1])
                self.data_im = np.zeros(f_data.shape)
                f_data.read_direct(self.data_im)
            except KeyError:
                self.logger.error("File is missing information, aboard.")
                return

        self.updateFileInfo(**fileDict)
        self.process()
        self.resetRoi()        
        self.updatePlots()

    def updateFileInfo(self,name="",timestamp=0,delayPoints=0,experimentType="",**kwargs):
        self.lFileName.setText(name)
        self.lDelayPoints.setText("{:d}".format(delayPoints))
        self.lExperimentType.setText(experimentType)
        self.lTimeStamp.setText(strftime("%a, %d %b %Y %H:%M:%S",localtime(timestamp)))

    def resetRoi(self):
        with QtCore.QSignalBlocker(self.pltImageView) as _:
            self.pltImageViewItems["y_linearregion"].setBounds((np.min(self.data_y),np.max(self.data_y)))
            self.pltImageViewItems["x_linearregion"].setBounds((np.min(self.data_x),np.max(self.data_x)))
            self.pltImageViewItems["background_region"].setBounds((np.min(self.data_y),np.max(self.data_y)))

    def process(self):
        data_in = self.data_im
        # check if multiple frames in array or multiple scans:
        if len(data_in.shape)>2:
            delay_axis = -1
            pixel_axis = -1
            for n,dim in enumerate(data_in.shape):
                if dim == len(self.data_y):
                    delay_axis = n
                if dim == len(self.data_x):
                    pixel_axis = n
            axes = list(range(0,len(data_in.shape)))
            try:
                axes.remove(delay_axis)
                axes.remove(pixel_axis)
                data_in = np.mean(data_in,axis=axes)
            except ValueError:
                self.logger.error("Could not parse input data array")
                return
        # do average per line
        if self.averageIntensities.isChecked():
            data_in = (data_in.T/np.mean(data_in,axis=1)).T
        # calculate log10
        data_in = np.log10(data_in)
        # do highpass
        if self.highpass.isChecked():
            data_in = highpass(data_in,self.highpassBandwidth.value())

        # subtract a portion of the data.
        if self.subtractBackground.isChecked():
            axy_min, axy_max = self.pltImageViewItems["background_region"].getRegion()
            iy_min, iy_max = find_index(self.data_y,[axy_min, axy_max])
            x_mean = np.mean(data_in[iy_min:iy_max,:], axis=0)
            data_in -= x_mean
        # done
        self.data_im_display = data_in

    def refresh(self):
        self.process()
        self.updatePlots()

    def updatePlots(self):
        self.plotImage()
        self.plotMarginals()

        # self.fit() # is called from plotMarginals.

    def plotImage(self):
        try:
            self.pltImage.setImage(self.data_im_display.T*1000)
            self.pltImage.setRect(axes_to_rect(self.data_x, self.data_y))
        except:
            self.logger.exception("Error while updating image:")
            raise


    def plotMarginals(self):
        try:
            # find indices
            axx_min, axx_max = self.pltImageViewItems["x_linearregion"].getRegion()
            axy_min, axy_max = self.pltImageViewItems["y_linearregion"].getRegion()
            ix_min, ix_max = find_index(self.data_x,[axx_min, axx_max])
            iy_min, iy_max = find_index(self.data_y,[axy_min, axy_max])
            print(ix_min,ix_max,iy_min,iy_max)
            # calculate marginals
            x_mean = np.mean(self.data_im_display[iy_min:iy_max,:], axis=0)
            y_mean = np.mean(self.data_im_display[:,ix_min:ix_max], axis=1)
            # plot marginals
            if self.useSVDForFit.isChecked() and self.useSVDForPlot.isChecked():
                self.pltTime.setData(self.data_y.squeeze(),self.processForFit())
            else:
                self.pltTime.setData(self.data_y.squeeze(),y_mean)
            self.pltSpectrum.setData(self.data_x.squeeze(),x_mean)
            # auto scale cmap if requested
            if self.autoScaleOnUpdate.isChecked():
                self.pltImageCBar.setLevels((np.min(self.data_im_display[:,ix_min:ix_max]),np.max(self.data_im_display[:,ix_min:ix_max])))
            # run a fit
            self.fit()
        except:
            print(self.data_x)
            self.logger.exception("Error while updating marginal plots:")
            raise

    def processForFit(self):
        try:
            # find indices
            axx_min, axx_max = self.pltImageViewItems["x_linearregion"].getRegion()
            ix_min, ix_max = find_index(self.data_x,[axx_min, axx_max])
            # are we doing SVD?
            if self.useSVDForFit.isChecked():
                U, s, V = np.linalg.svd(self.data_im_display[:,ix_min:ix_max])
                s_idx = self.svdIndex.value()
                data = U[:,s_idx]*s[s_idx]
                return data
            # calculate marginals
            y_mean = np.mean(self.data_im_display[:,ix_min:ix_max], axis=1)
            return y_mean
        except:
            self.logger.exception("Error preparing data for fit:")
            raise
            return None

    def fit(self):
        if not self.runFit.isChecked():
            return
        data = self.processForFit()

        if data is None:
            # unable to get meaningful data at this time
            return

        if self.fitThread.isRunning():
            self.logger.warning("Fit is still running, delay call")
            # an older fit is still running, we could try to cancel it.
            self.fitThread.quit()
            ## wait for it to quit, this will lock the GUI FIXME
            ## self.fitThread.wait()
            # instead of waiting for thread to finish, schedule self to run once fitThread finishes.
            self.fitThread.finished.connect(self.fit)
            return

        # make sure we disconnect the finished signal
        try:
            self.fitThread.finished.disconnect(self.fit)
        except:
            pass

        # create a new worker object
        fitWorker = fitGasTransient()


        # set options etc.
        fitWorker.data = data
        fitWorker.x_values = self.data_y
        # setup thread, connect signals
        if self.use_thread:
            fitWorker.moveToThread(self.fitThread)
            self.fitThread.started.connect(fitWorker.runFit)
            fitWorker.fitFinished.connect(self.dispatchFitResult)
            # execute thread
            self.fitThread.start()
        else:
            fitWorker.runFit()
            self.dispatchFitResult(fitWorker.report)


    def dispatchFitResult(self,report):
        self._lastResult = report
        self.plotFit(report)
        self.updateFitInfo(report)

    def plotFit(self,report):
        try:
            x = report["x"]
            if self.centerPlotOnTimeZero.isChecked():
                # shift x by t0
                x-=report["opt"][0]/6.6
            if self.plotFitInFs.isChecked():
                x*=6.6
            self.fitScatterA.setData(x,report["y"])
            self.fitLineA.setData(x,fitGasTransient.gauss_mod(report["x"]*6.6,*report["opt"]))
            if self.extractGauss.isChecked():
                # subtract full model from data, then add back in the fitted gauss profile
                res = report["y"]-fitGasTransient.gauss_mod(report["x"]*6.6,*report["opt"])+fitGasTransient.gauss(report["x"]*6.6,*report["opt"])
                self.fitScatterB.setData(x,res)
                self.fitLineB.setData(x,fitGasTransient.gauss(report["x"]*6.6,*report["opt"]))
                #self.fitLineB.setData(x,fitGasTransient.expodecay(report["x"]*6.6,*report["opt"]))
            else:
                self.fitScatterB.setData([],[])
                self.fitLineB.setData([],[])
        except:
            self.logger.exception("Error while plotting results from fit:")    
            raise

    def updateFitInfo(self,report):
        self.eFWHM.setText("{:.1f}±{:.1f}".format(report["opt"][1],report["err"][1]))
        self.eTimeZero.setText("{:.1f}±{:.1f}".format(report["opt"][0]/6.6,report["err"][0]/6.6))
        self.eAmplitude.setText("{:.1f}±{:.1f}".format(report["opt"][2],report["err"][1]))
        self.eGamma.setText("{:.1f}±{:.1f}".format(report["opt"][3],report["err"][3]))  
        self.eResidual.setText("{:.1f}".format(report["residual"]))      

    def browsePath(self):
        # display a dialog to select a path.
        pass


class fitGasTransient(QtCore.QObject):
    fitFinished = QtCore.pyqtSignal(dict)
    def __init__(self):
        super().__init__()
        self.data = None
        self.fix_decay = False # TODO: Implement fixing the decay.
        self.decay = 10
        self.t0 = 10
        self.force_invert = False
        self.try_invert = True
        self.x_values = None
        self.unbound = False
        self.maxfev = 10000

    def gauss_mod(x,c,s,a,bg,l=3e-3):
        s/=(2*np.sqrt(2*np.log(2))) # FWHM to sigma
        k = 1/(s*l)
        return exponnorm.pdf(-x,k,loc=-c,scale=s)*a+bg

    def gauss(x,c,s,a,bg,*args):
        s/=(2*np.sqrt(2*np.log(2)))
        return norm.pdf(-x,loc=-c,scale=s)

    def expodecay(x,c,s,a,bg,l=3e-3):
        ex = expon.pdf(-x,loc=-c,scale=1/l)*a+bg
        return ex


    def runFit(self):
        delay_vector_fs = 6.6*self.x_values
        data = self.data

        # guess sign and correct data
        sig1 = np.sign(np.max(uniform_filter1d(data[:],5,mode="nearest")))
        if self.force_invert:
            sig1 = -sig1        
        data *= sig1

        fit = fitGasTransient.gauss_mod
        if self.fix_decay:
            # Order of parameters: t0, FWHM, Amplitude, bg, [Gamma]
            inital_guess = [np.mean(delay_vector_fs),15.0,0.2,0.0]
        else:
            inital_guess = [np.mean(delay_vector_fs),15.0,0.2,0.0,3e-2]

        """ Set bounds
        Bind t0 to be on the scanned range, 
        the FWHM to be shorter than the scanned range and longer than the single cycle limit
        the amplitude to be positive. """
        bounds_max = [np.max(delay_vector_fs),np.max(delay_vector_fs)-np.min(delay_vector_fs), np.inf, np.inf]
        bounds_min = [np.min(delay_vector_fs),2.6,0,-np.inf]
        # Optionally, the decay to be not faster than 0.6fs and larger than 0
        if not self.fix_decay:
            bounds_max.append(1)
            bounds_min.append(0)

        error = error1 = False
        # First Run
        with warnings.catch_warnings():
            warnings.simplefilter("error", OptimizeWarning)
            try:
                              
                popt,pcov=curve_fit(fit,delay_vector_fs,data,p0=inital_guess,maxfev=self.maxfev,bounds=(bounds_min,bounds_max))
                A=popt
                Aerr=(np.sqrt(np.diag(pcov)))
                residual= np.sum(np.abs((data-fit(delay_vector_fs,*popt))))
                

            except OptimizeWarning:
                residual=np.inf
                error=True
                
            except RuntimeError:
                residual=np.inf
                error=True

        if self.try_invert:
            with warnings.catch_warnings():
                warnings.simplefilter("error", OptimizeWarning)
                try:
                                  
                    popt,pcov=curve_fit(fit,delay_vector_fs,-data,p0=inital_guess,maxfev=self.maxfev,bounds=(bounds_min,bounds_max))
                    if np.sum(np.abs((-data-fit(delay_vector_fs,*popt))))<residual:
                        # Second fit was better
                        A=popt
                        Aerr=(np.sqrt(np.diag(pcov)))
                        residual= np.sum(np.abs((-data-fit(delay_vector_fs,*popt))))
                        data*=-1
                    

                except OptimizeWarning:
                    if error==0: # First run worked, this one didn't
                        pass
                    residual=np.inf 
                    error=1
                    
                except RuntimeError:
                    if error==0:
                        pass
                    residual=np.inf
                    error=1

        self.report= dict(
            x=self.x_values,
            y=data,
            opt=A,
            err=Aerr,
            residual=residual)
        self.fitFinished.emit(self.report)


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = GasTransientsGui()
    window.show()
    app.exec_()

if __name__ == '__main__':
    main()
