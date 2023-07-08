
from PyQt6 import QtCore, QtWidgets
import logging
import CameraSystem
import StageController


#define data folder
#find desktop location
#Measurement -> Date (Year_Month_Date)-> Experiments, Harmonics -> Experiments -> "Time_zero_All"

#folder = QtCore.QStandardPaths.locate(QtCore.QStandardPaths.DesktopLocation,"Measurement",QtCore.QStandardPaths.LocateDirectory)

#logging setup
#logger = logging.getLogger(__name__)

#GUI
#window = QtWidgets.QApplication.instance()

#connect to camera
CameraSystem.SetupCameraInterface()
CameraSystem.ConnectCamera()


#connect to shutter, delaystage
controller = StageController()
controller.show()

#wait
wait_function = QtWidgets.QApplication.processEvents

#set starting delaystage value, end value & stepcount
setting = dict (delay_start = 0, delay_end = 10, delay_increment = 1)

#cool the camera
CameraSystem.TemperatureControl_Init()
CameraSystem.TemperatureControl_SetTemperature(-30)
temperature = CameraSystem.TemperatureControl_GetTemperature()
logger.info("temperature: {:d} ms".format(temperature))


#set binning mode of the camera
CameraSystem.SetBinningMode()


#loop for image acqusition: open shutter, acquire image, close shutter, acquire image
for x in range (setting["delay_start"], setting["delay_end"], setting["delay_increment"]):
    #controller.shutter.setShutter(True)
    #CameraSystem.OpenShutter()
    CameraSystem.PerformMeasurement_Blocking_DynBitDepth()
    CameraSystem.StartMeasurement_DynBitDepth()
    CameraSystem.GetMeasurementData_DynBitDepth()
    CameraSystem.StopMeasurement()
    #controller.shutter.setShutter(False)

    CameraSystem.PerformMeasurement_Blocking_DynBitDepth()
    CameraSystem.StartMeasurement_DynBitDepth()
    CameraSystem.GetMeasurementData_DynBitDepth()
    CameraSystem.StopMeasurement()

