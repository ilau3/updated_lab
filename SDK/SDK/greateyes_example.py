# -*- coding: utf-8 -*-
"""
Created on Wed Mar 18 11:22:47 2020

@author: marcel
"""

import numpy as np
from PIL import Image
import sys
import greateyesSDK as ge
import time
import matplotlib
from matplotlib.pyplot import imshow, show, colorbar

# --------------------------------------------------------------------------------------------------------

# 1 Options for this example script
# --------------------------------------------------------------------------------------------------------

connectionType = ge.connectionType_Ethernet  # or ge.ConnectionType_USB instead
CameraIP = '192.168.1.234'  # only needed for Ethernet cameras
showImages = True  # displays all new images using matplotlib
saveSampleImage = True
CameraSensorCooling = False  # before setting this True, please ensure that it is safe to cool the CCD sensor.
# I.e. if you are using a camera with vacuum flange or inVacuum type, make sure the chip is evacuated
# and the pressure is at least 1e-4 mbars or lower.
t_exp = 1  # ms
DoBurstModeTest = True


# --------------------------------------------------------------------------------------------------------

# 2 function declarations
# --------------------------------------------------------------------------------------------------------

# This function starts a measurement and once it is finished, calls the image data from the greateyes SDK.
# It uses the non-blocking functions, so python is operating in the meantime
def Camera_PerformMeasurement(prints=True):
	if (ge.StartMeasurement_DynBitDepth() == True):
		if prints:
			print('   measurement started')
			print('   waiting, while DLL is busy')
		t_meas = 0
		global t_exp
		t_crit = t_exp / 1000 + 10  # seconds for measurement timeout
		dt = 0.01
		while ge.DllIsBusy():
			time.sleep(dt)
			t_meas = t_meas + dt
			if (t_meas >= t_crit):  # if measurement takes took long
				if ge.StopMeasurement() == True:
					print('measurement stopped, measurement took too long')
		if prints:
			print('   ...finished\n')
		imageArray = ge.GetMeasurementData_DynBitDepth()
		return imageArray


def display_image(imageArray):
	imshow(imageArray)
	colorbar()
	show()


# --------------------------------------------------------------------------------------------------------

# 3 main
# --------------------------------------------------------------------------------------------------------

def main():
	connectionSetupWorked = None
	image = None
	image_blocking = None
	NumberOfOutputModes = None

	# Check greateyes DLL is working
	print('DLL Version:')
	print(ge.GetDLLVersion())
	ge.DisconnectCamera()
	ge.DisconnectCameraServer()

	# setup camera connection
	print('\n-----------------------------------------------------\n')
	print('setting up connection')

	if connectionType == ge.connectionType_USB:
		print('   using USB connection')
		connectionSetupWorked = ge.SetupCameraInterface(connectionType)
	elif connectionType == ge.connectionType_Ethernet:
		print('using TCP connection on ip address:', CameraIP)
		connectionSetupWorked = ge.SetupCameraInterface(connectionType, ipAddress=CameraIP)
		if connectionSetupWorked:
			connectionSetupWorked = ge.ConnectToSingleCameraServer()
	else:
		print('unexpected connectionType index')

	if connectionSetupWorked == True:
		print('   ok')
	else:
		print('   failed')
		print('   Status:', ge.StatusMSG)
		sys.exit()

	print('\n-----------------------------------------------------\n')
	print('attempting to connect to camera')
	CameraConnected = False
	N_Cams = ge.GetNumberOfConnectedCams()
	print('   ' + str(N_Cams), 'camera(s) detected')

	if (N_Cams == 1):
		print('\n-----------------------------------------------------\n')
		print('connecting')
		CameraModel = []
		CameraConnected = ge.ConnectCamera(model=CameraModel, addr=0)
		if (CameraConnected == True):
			CameraModelID = CameraModel[0]
			CameraModelStr = CameraModel[1]
			print('   connected to camera ' + CameraModelStr)
			print('\n-----------------------------------------------------\n')
			print('initializing camera')
			if (ge.InitCamera(addr=0) == True):
				print('Status:' + ge.StatusMSG)
				print('   ok')
				Cooling_limits = ge.TemperatureControl_Init()
				ge.SetBitDepth(4)
				print('Switching off LED: ' + str(ge.SetLEDStatus(False)))
				ge.OpenShutter(1)
				time.sleep(1)
				ge.OpenShutter(0)
			else:
				print('   failed')
				print('   Status:', ge.StatusMSG)
				ge.DisconnectCamera()
				sys.exit()
		else:
			print('   failed')
			print('   Status:', ge.StatusMSG)
			ge.DisconnectCamera()
			if connectionType == ge.connectionType_Ethernet:
				ge.DisconnectCameraServer()
			sys.exit()
	else:
		print('   failed. Number of cameras is not 1.')

	# Get camera information
	if CameraConnected:
		print('\n-----------------------------------------------------\n')
		print('Gathering Camera information:')
		print('   Firmware Version:', ge.GetFirmwareVersion())
		print('   Image Size:', ge.GetImageSize()[0:2])
		print('   Digital Resolution:', ge.GetImageSize()[2] * 8, 'bit')
		print('   Pixel Size: ', ge.GetSizeOfPixel(), 'um')
		print('   Camera is busy:', ge.DllIsBusy())
		print('   max. Exposure time:', ge.GetMaxExposureTime(), 'ms')
		print('   max. binning x:', ge.GetMaxBinningX(), 'y:', ge.GetMaxBinningY())
		print('   camera supports capacity mode:', ge.SupportedSensorFeature(ge.sensorFeature_capacityMode))
		print('   camera supports horizontal hardware binning:', ge.SupportedSensorFeature(ge.sensorFeature_binningX))
		print('   camera supports horizontal hardware cropping:', ge.SupportedSensorFeature(ge.sensorFeature_cropX))
		print('   camera provides the following output mode(s):')
		NumberOfOutputModes = ge.GetNumberOfSensorOutputModes()
		for i in range(NumberOfOutputModes):
			print('      mode ' + str(i) + ':', ge.GetSensorOutputModeStrings(i))
		ge.SetupSensorOutputMode(NumberOfOutputModes-1)

	# Set Measurement Parameters
	if CameraConnected:
		print('\n-----------------------------------------------------\n')
		print('setting measurement parameters:')
		if (ge.SetExposure(t_exp) == True):
			print('   exposure time set to', t_exp, 'ms')

	# take image
	if CameraConnected:
		print('\n-----------------------------------------------------\n')
		print('taking single shot non-blocking:')
		image = Camera_PerformMeasurement()
		print('   measurement time:   ', '{:6.3f}'.format(ge.GetLastMeasTimeNeeded()), 'seconds')
		print('   mean intensity:     ', '{:6.3f}'.format(np.mean(image)), 'ADU')
		print('   standard deviation: ', '{:6.3f}'.format(np.std(image)), 'ADU')
		if showImages:
			display_image(image)

		print('\n-----------------------------------------------------\n')
		print('taking single shot blocking:')
		print('   measurement started')
		image_blocking = ge.PerformMeasurement_Blocking_DynBitDepth()
		print('   ...finished\n')
		print('   measurement time:   ', '{:6.3f}'.format(ge.GetLastMeasTimeNeeded()), 'seconds')
		print('   mean intensity:     ', '{:6.3f}'.format(np.mean(image_blocking)), 'ADU')
		print('   standard deviation: ', '{:6.3f}'.format(np.std(image_blocking)), 'ADU')
		if showImages:
			display_image(image_blocking)

	# save image to hard disk
	if CameraConnected and saveSampleImage:
		save_image = Image.fromarray(image)
		save_image.save("geExample_TestImage.tif")

	# temperature management
	if CameraConnected and CameraSensorCooling:
		print('\n-----------------------------------------------------\n')
		print('initializing sensor cooling')
		Cooling_limits = ge.TemperatureControl_Init()
		print('   Temperature values shall be in this range:')
		print('      lowest possible setpoint =', Cooling_limits[0], '°C')
		print('      highest possible setpoint =', Cooling_limits[1], '°C')
		print('   Actual Temperatures are:')
		print('      CCD (TEC frontside):', ge.TemperatureControl_GetTemperature(0), '°C')
		print('      TEC backside:', ge.TemperatureControl_GetTemperature(1), '°C')
		print('   Setting -20 °C, monitoring for 2 minutes')
		Temperature_SetPoint = -20
		if ge.TemperatureControl_SetTemperature(Temperature_SetPoint) == True:
			for i in range(120):
				print('  ', i, 's   T_CCD:', ge.TemperatureControl_GetTemperature(0), '°C', '   T_back:',
				      ge.TemperatureControl_GetTemperature(1), '°C')
				time.sleep(1)
		if ge.TemperatureControl_SwitchOff() == True:
			print('Sensor cooling switched off')

	# mode testing
	print('\n-----------------------------------------------------\n')
	print('testing available camera modes')
	if CameraConnected:
		if DoBurstModeTest:
			# burst mode
			print('\n   Burst Mode')
			if ge.SetupBurstMode(5) == True:
				if ge.ActivateBurstMode(True) == True:
					image = Camera_PerformMeasurement(prints=False)
					print('   image size:         ', image.shape)
					print('   measurement time:   ', '{:6.3f}'.format(ge.GetLastMeasTimeNeeded()), 'seconds')
					print('   checked: burst mode with 5 Images')
					if showImages:
						display_image(image)
				else:
					print('   Error while activating burst')
				ge.ActivateBurstMode(False)
			else:
				print('   Error while setting up burst mode')

		# binning mode
		print('\n   Binning Modes')
		for i in range(1, 11):
			if ge.SetBinningMode(i, i) == True:
				image = ge.PerformMeasurement_Blocking_DynBitDepth()  # Camera_PerformMeasurement(prints=False)
				print('  ', i, 'x', i, 'binning   measurement time:', '{:6.3f}'.format(ge.GetLastMeasTimeNeeded()),
				      'seconds   image size:', image.shape)
				if showImages:
					display_image(image)
			else:
				print('   Error while setting binning', i)
		print('   checked: binning modes 1-10')
		ge.SetBinningMode(1, 1)

		# crop mode
		print('\n   Crop Mode')
		if ge.SetupCropMode2D(500, 100) == True:
			if ge.ActivateCropMode(True) == True:
				image = ge.PerformMeasurement_Blocking_DynBitDepth()  # Camera_PerformMeasurement(prints=False)
				print('   image size:         ', image.shape)
				print('   measurement time:   ', '{:6.3f}'.format(ge.GetLastMeasTimeNeeded()), 'seconds')
				print('   checked: crop mode with 500 columns and 100 lines \n')
				if showImages:
					display_image(image)
			else:
				print('   Error while activating crop')
			ge.ActivateCropMode(False)
		else:
			print('   Error while setting crop mode')

		# readout frequency
		print('\n   500 kHz readout')
		if ge.SetReadOutSpeed(ge.readoutSpeed_500_kHz) == True:
			image = Camera_PerformMeasurement(prints=False)
			print('   measurement time:   ', '{:6.3f}'.format(ge.GetLastMeasTimeNeeded()), 'seconds')
			print('   checked: 500 kHz pixel frequency')
			if showImages:
				display_image(image)
			ge.SetReadOutSpeed(ge.readoutSpeed_1_MHz)
		else:
			print('   Error while setting 500 kHz')

		# gain mode
		print('\n   Gain Mode')
		if ge.SetupGain(1) == True:
			image = Camera_PerformMeasurement(prints=False)
			print('   measurement time:   ', '{:6.3f}'.format(ge.GetLastMeasTimeNeeded()), 'seconds')
			print('   mean intensity:     ', '{:6.3f}'.format(np.mean(image_blocking)), 'ADU')
			print('   standard deviation: ', '{:6.3f}'.format(np.std(image_blocking)), 'ADU')
			print('   checked: high gain mode')
			if showImages:
				display_image(image)
			ge.SetupGain(0)
		else:
			print('   Setup Gain function returned False.\n   Supposably this camera does not support gain switching.')

		# capacity mode
		print('\n   Capacity Mode')
		if ge.SetupCapacityMode(True) == True:
			image = Camera_PerformMeasurement(prints=False)
			print('   measurement time:   ', '{:6.3f}'.format(ge.GetLastMeasTimeNeeded()), 'seconds')
			print('   mean intensity:     ', '{:6.3f}'.format(np.mean(image_blocking)), 'ADU')
			print('   standard deviation: ', '{:6.3f}'.format(np.std(image_blocking)), 'ADU')
			print('   checked: extended capacity mode')
			if showImages:
				display_image(image)
			ge.SetupCapacityMode(False)
		else:
			print(
				'   Setup capacity mode function returned False.\n   Supposably this camera does not support capacity mode switching.')

		# Output Modes
		if NumberOfOutputModes > 1:
			print('\n   Output Modes')
			for i in range(NumberOfOutputModes):
				print('   mode ' + str(i) + ':', ge.GetSensorOutputModeStrings(i))
				ge.SetupSensorOutputMode(i)
				image = Camera_PerformMeasurement(prints=False)
				print('   measurement time:   ', '{:6.3f}'.format(ge.GetLastMeasTimeNeeded()), 'seconds')
				print('   mean intensity:     ', '{:6.3f}'.format(np.mean(image_blocking)), 'ADU')
				print('   standard deviation: ', '{:6.3f}'.format(np.std(image_blocking)), 'ADU')
			ge.SetupSensorOutputMode(0)
			print('   checked: output modes')

	# disconnecting camera
	print('\n-----------------------------------------------------\n')
	print('disconnecting')
	if (ge.DisconnectCamera() == True):
		print('   done')
	if connectionType == ge.connectionType_Ethernet:
		if ge.DisconnectCameraServer() == True:
			print('   CameraServer connection closed')
	else:
		print('   failed')
		print('   Status:', ge.StatusMSG)
		sys.exit()
