#!/usr/bin/env python

import matplotlib.pyplot as plt
import numpy as np
import time
import cv2
from real_lab.perception.vision.camera import Camera
from real_lab.robot.ur_robot import URRobot
from scipy import optimize  
from mpl_toolkits.mplot3d import Axes3D
import os
import sys
import termios  

def press_any_key(msg):
    fd = sys.stdin.fileno()
    old_ttyinfo = termios.tcgetattr(fd) 
    new_ttyinfo = old_ttyinfo[:] 
    new_ttyinfo[3] &= ~termios.ICANON 
    new_ttyinfo[3] &= ~termios.ECHO 
    sys.stdout.write(msg)
    sys.stdout.flush()
    termios.tcsetattr(fd, termios.TCSANOW, new_ttyinfo) 
    os.read(fd, 7) 
    termios.tcsetattr(fd, termios.TCSANOW, old_ttyinfo) 


# User options (change me)  ***
# --------------- Setup options ---------------
robot_ip = '192.168.1.102' # IP and port to robot arm as TCP client
workspace_limits = np.asarray([[-0.88, -0.58], [-0.315, -0.115], [0.2, 0.35]]) # Cols: min max, Rows: x y z (define workspace limits in robot coordinates)
calib_grid_step = 0.05
checkerboard_offset_from_tool = [0,0,0] # Measure the offset from the center point of the checkerboard to the tool center point in the robot coordinates
tool_orientation = [1.326,-1.233,-1.117] # [0,-2.22,2.22] # [2.22,2.22,0] maintain angle of the gripper during calibration
home_joint_config = [np.deg2rad(24.19), np.deg2rad(-61.34), np.deg2rad(90.15), np.deg2rad(-201.58), np.deg2rad(-41.24), np.deg2rad(173.29)]
calibration_dir = "./calibrate_pictures"
calibration_param_dir = "./real_param"
# ---------------------------------------------

if not os.path.exists(calibration_dir):
    os.makedirs(calibration_dir)
if not os.path.exists(calibration_param_dir):
    os.makedirs(calibration_param_dir)

# Construct 3D calibration grid across workspace
gridspace_x = np.linspace(workspace_limits[0][0], workspace_limits[0][1], 1 + (workspace_limits[0][1] - workspace_limits[0][0])/calib_grid_step)
gridspace_y = np.linspace(workspace_limits[1][0], workspace_limits[1][1], 1 + (workspace_limits[1][1] - workspace_limits[1][0])/calib_grid_step)
gridspace_z = np.linspace(workspace_limits[2][0], workspace_limits[2][1], 1 + (workspace_limits[2][1] - workspace_limits[2][0])/calib_grid_step)
calib_grid_x, calib_grid_y, calib_grid_z = np.meshgrid(gridspace_x, gridspace_y, gridspace_z) 
# Generate a grid point coordinate matrix, the input x, y, z is the horizontal and vertical coordinate column vector of the grid point (not matrix) The output X, Y, Z is the coordinate matrix
# Put the first and second coordinates of the elements in the Cartesian product of the two arrays into two matrices respectively
num_calib_grid_pts = calib_grid_x.shape[0]*calib_grid_x.shape[1]*calib_grid_x.shape[2]
calib_grid_x.shape = (num_calib_grid_pts,1)
calib_grid_y.shape = (num_calib_grid_pts,1)
calib_grid_z.shape = (num_calib_grid_pts,1)
calib_grid_pts = np.concatenate((calib_grid_x, calib_grid_y, calib_grid_z), axis=1)

measured_pts = []
observed_pts = []
observed_pix = []

# Move robot to home pose
print('Connecting to robot...')
robot = URRobot(workspace_limits, robot_ip, False, home_joint_config)
# robot.open_gripper()
press_any_key("place the calibration board and press any key to continue")
print("\n")
robot.close_gripper()
press_any_key("press any key to continue")
print("\n")

# Slow down robot
robot.joint_acc = 0.5
robot.joint_vel = 0.8

# Make robot gripper point upwards ***
robot.move_joints([np.deg2rad(-6.64), np.deg2rad(-114.31), np.deg2rad(150.22), np.deg2rad(-215.36), np.deg2rad(-79.74), np.deg2rad(179.91)])

# Move robot to each calibration point in workspace
print('Collecting data...')
for calib_pt_idx in range(num_calib_grid_pts):
    tool_position = calib_grid_pts[calib_pt_idx,:]
    robot.move_to(tool_position, tool_orientation, acc=0.5)
    time.sleep(1)
    
    # Find checkerboard center
    checkerboard_size = (3,3) # *** modify the size according to the checkerboard  (3,3)
    # checkerboard_size is the size of corner not the calibrate board size
    refine_criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    camera_color_img, camera_depth_img = robot.get_camera_data()
    bgr_color_data = cv2.cvtColor(camera_color_img, cv2.COLOR_BGR2RGB)  # Color space transform
    gray_data = cv2.cvtColor(bgr_color_data, cv2.COLOR_RGB2GRAY)
    checkerboard_found, corners = cv2.findChessboardCorners(gray_data, checkerboard_size, None, cv2.CALIB_CB_ADAPTIVE_THRESH)
    # corners： marked out footprints
    if checkerboard_found:
        corners_refined = cv2.cornerSubPix(gray_data, corners, checkerboard_size, (-1,-1), refine_criteria)

        # get center conrer index
        mid_corner_ind = np.trunc((checkerboard_size[0] * checkerboard_size[1]) / 2)

        # Get observed checkerboard center 3D point in camera space
        checkerboard_pix = np.round(corners_refined[int(mid_corner_ind),0,:]).astype(int) # ****
        checkerboard_z = camera_depth_img[checkerboard_pix[1]][checkerboard_pix[0]]
        checkerboard_x = np.multiply(checkerboard_pix[0]-robot.cam_intrinsics[0][2],checkerboard_z/robot.cam_intrinsics[0][0])
        checkerboard_y = np.multiply(checkerboard_pix[1]-robot.cam_intrinsics[1][2],checkerboard_z/robot.cam_intrinsics[1][1])
        if checkerboard_z == 0:
            continue

        # Save calibration point and observed checkerboard center
        observed_pts.append([checkerboard_x,checkerboard_y,checkerboard_z])
        # tool_position[2] += checkerboard_offset_from_tool
        tool_position = tool_position + checkerboard_offset_from_tool

        measured_pts.append(tool_position)
        observed_pix.append(checkerboard_pix)

        # Draw and display the corners
        # vis = cv2.drawChessboardCorners(robot.camera.color_data, checkerboard_size, corners_refined, checkerboard_found)
        vis = cv2.drawChessboardCorners(bgr_color_data, (1,1), corners_refined[int(mid_corner_ind),:,:], checkerboard_found)  # ****
        cv2.imwrite(os.path.join(calibration_dir,'%06d.png' % len(measured_pts)), vis)
        cv2.imshow('Calibration',vis)
        cv2.waitKey(10)

# Move robot back to home pose
robot.go_home()

measured_pts = np.asarray(measured_pts)
observed_pts = np.asarray(observed_pts)
observed_pix = np.asarray(observed_pix)
world2camera = np.eye(4)

# Estimate rigid transform with SVD (from Nghia Ho)
def get_rigid_transform(A, B):
    assert len(A) == len(B)
    N = A.shape[0]; # Total points
    centroid_A = np.mean(A, axis=0)
    centroid_B = np.mean(B, axis=0)
    AA = A - np.tile(centroid_A, (N, 1)) # Centre the points
    BB = B - np.tile(centroid_B, (N, 1))
    H = np.dot(np.transpose(AA), BB) # Dot is matrix multiplication for array
    U, S, Vt = np.linalg.svd(H)
    R = np.dot(Vt.T, U.T)
    if np.linalg.det(R) < 0: # Special reflection case
       Vt[2,:] *= -1
       R = np.dot(Vt.T, U.T)
    t = np.dot(-R, centroid_A.T) + centroid_B.T
    return R, t

def get_rigid_transform_error(z_scale):
    global measured_pts, observed_pts, observed_pix, world2camera, camera

    # Apply z offset and compute new observed points using camera intrinsics
    observed_z = observed_pts[:,2:] * z_scale
    observed_x = np.multiply(observed_pix[:,[0]]-robot.cam_intrinsics[0][2],observed_z/robot.cam_intrinsics[0][0])
    observed_y = np.multiply(observed_pix[:,[1]]-robot.cam_intrinsics[1][2],observed_z/robot.cam_intrinsics[1][1])
    new_observed_pts = np.concatenate((observed_x, observed_y, observed_z), axis=1)

    # Estimate rigid transform between measured points and new observed points
    R, t = get_rigid_transform(np.asarray(measured_pts), np.asarray(new_observed_pts))
    t.shape = (3,1)
    world2camera = np.concatenate((np.concatenate((R, t), axis=1),np.array([[0, 0, 0, 1]])), axis=0)

    # Compute rigid transform error
    registered_pts = np.dot(R,np.transpose(measured_pts)) + np.tile(t,(1,measured_pts.shape[0]))
    error = np.transpose(registered_pts) - new_observed_pts
    error = np.sum(np.multiply(error,error))
    rmse = np.sqrt(error/measured_pts.shape[0]);
    return rmse

# Optimize z scale w.r.t. rigid transform error
print('Calibrating...')
z_scale_init = 1
optim_result = optimize.minimize(get_rigid_transform_error, np.asarray(z_scale_init), method='Nelder-Mead')
camera_depth_offset = optim_result.x

# Save camera optimized offset and camera pose
print('Saving...')
np.savetxt(os.path.join(calibration_param_dir,'camera_depth_scale.txt'), camera_depth_offset, delimiter=' ')
get_rigid_transform_error(camera_depth_offset)
camera_pose = np.linalg.inv(world2camera)
np.savetxt(os.path.join(calibration_param_dir,'camera_pose.txt'), camera_pose, delimiter=' ')
print('Done.')

# DEBUG CODE -----------------------------------------------------------------------------------

# np.savetxt('measured_pts.txt', np.asarray(measured_pts), delimiter=' ')
# np.savetxt('observed_pts.txt', np.asarray(observed_pts), delimiter=' ')
# np.savetxt('observed_pix.txt', np.asarray(observed_pix), delimiter=' ')
# measured_pts = np.loadtxt('measured_pts.txt', delimiter=' ')
# observed_pts = np.loadtxt('observed_pts.txt', delimiter=' ')
# observed_pix = np.loadtxt('observed_pix.txt', delimiter=' ')

# fig = plt.figure()
# ax = fig.add_subplot(111, projection='3d')
# ax.scatter(measured_pts[:,0],measured_pts[:,1],measured_pts[:,2], c='blue')

# print(camera_depth_offset)
# R, t = get_rigid_transform(np.asarray(measured_pts), np.asarray(observed_pts))
# t.shape = (3,1)
# camera_pose = np.concatenate((np.concatenate((R, t), axis=1),np.array([[0, 0, 0, 1]])), axis=0)
# camera2robot = np.linalg.inv(camera_pose)
# t_observed_pts = np.transpose(np.dot(camera2robot[0:3,0:3],np.transpose(observed_pts)) + np.tile(camera2robot[0:3,3:],(1,observed_pts.shape[0])))

# ax.scatter(t_observed_pts[:,0],t_observed_pts[:,1],t_observed_pts[:,2], c='red')

# new_observed_pts = observed_pts.copy()
# new_observed_pts[:,2] = new_observed_pts[:,2] * camera_depth_offset[0]
# R, t = get_rigid_transform(np.asarray(measured_pts), np.asarray(new_observed_pts))
# t.shape = (3,1)
# camera_pose = np.concatenate((np.concatenate((R, t), axis=1),np.array([[0, 0, 0, 1]])), axis=0)
# camera2robot = np.linalg.inv(camera_pose)
# t_new_observed_pts = np.transpose(np.dot(camera2robot[0:3,0:3],np.transpose(new_observed_pts)) + np.tile(camera2robot[0:3,3:],(1,new_observed_pts.shape[0])))

# ax.scatter(t_new_observed_pts[:,0],t_new_observed_pts[:,1],t_new_observed_pts[:,2], c='green')

# plt.show()