# Python Library for Real-World Robot
This is a library based on the UR robot and other packages will continued to be add later.
## Hardware
- UR5 (RTDE)
- Robotiq Gripper (TCP/RTU)
- Wrist camera and force sensor suits of Robotiq
- Mech-eye
- ZED
- Realsense
- Xtion Pro live
- ...

## Installation
This implementation requires the following dependencies (tested on Ubuntu 16.04 LTS, Ubuntu 16.04 LTS and Ubuntu 20.04 LTS):
* Python 3
You can quickly install/update these dependencies by running the following (replace `pip` with `pip3` for Python 3):
  `python setup.py install`
If you use need to use realsense, you can download from the official library([RealSense](https://github.com/IntelRealSense/librealsense)).
If you want to control UR5/UR3 Robot, you can rtde packages([ur_-rtde](https://sdurobotics.gitlab.io/ur_rtde/installation/installation.html)).You can also quickly install rtde by this way:
 `pip install --user ur_rtde`

## Attention
 If you want to control Gripper via RTU, you should first run
 `sudo chmod +777 /dev/ttyUSB0`
 If your background is black, you shoud leave the edge of calibrate board blank.

## Calibrating Camera Extrinsics
We provide a simple calibration script to estimate camera extrinsics with respect to robot base coordinates. You can choose different checkerboards and change the variables `checkerboard_size`.

### Instructions:
1. Predefined 3D locations are sampled from a 3D grid of points in the robot's workspace. To modify these locations, change the variables `workspace_limits` and `calib_grid_step` at the top of `calibrate.py`.

2. Measure the offset between the midpoint of the checkerboard pattern to the tool center point in robot coordinates (variable `checkerboard_offset_from_tool`). This offset can change depending on the orientation of the tool (variable `tool_orientation`) as it moves across the predefined locations. Change both of these variables respectively at the top of `calibrate.py`. 

3. At the top of `calibrate.py`, change variable `robot_ip` to point to the network IP address of your UR5 robot controller which can communicate with UR Robot.

4. With caution, run the following to move the robot and calibrate:

    ```shell
    python calibrate.py
    ```