# BuddyBot Vision Package

This package provides modular computer vision capabilities for BuddyBot, optimized for Raspberry Pi 5. It includes camera capture, person detection, following control, and time-to-collision safety monitoring.

## Architecture

The vision system is split into four independent ROS 2 nodes for modularity and performance:

### 1. Camera Node (`camera_node.py`)
**Purpose:** Captures video from camera device and publishes ROS image messages.

**Features:**
- OpenCV VideoCapture with configurable resolution/FPS
- Automatic camera reinitialization on failure
- Optimized QoS settings for video streaming
- Low-latency image publishing

### 2. Detector Node (`detector_node.py`)
**Purpose:** Performs lightweight person detection using MobileNet-SSD.

**Features:**
- OpenCV DNN with TensorFlow MobileNet-SSD v2
- Configurable detection intervals to reduce CPU load
- Publishes best person bounding box
- Optional debug image with detection overlays
- Optimized for CPU inference on Raspberry Pi 5

### 3. Follow Controller Node (`follow_controller_node.py`)
**Purpose:** Computes velocity commands to follow detected person.

**Control Logic:**
- **Angular velocity:** Proportional to center offset (yaw control)
- **Linear velocity:** Based on bounding box height (distance approximation)
- Configurable gains and safety limits
- Deadzones prevent jittery motion

### 4. TTC Node (`ttc_node.py`)
**Purpose:** Estimates time-to-collision using optical flow for collision avoidance.

**Algorithm:**
- Lucas-Kanade optical flow for feature tracking
- TTC estimation from expanding flow patterns
- Emergency alerts when collision imminent
- Efficient processing with configurable intervals

## ROS 2 Interfaces

### Publishers
- `/camera/image_raw` (sensor_msgs/Image): Raw camera images
- `/vision/person_bbox` (std_msgs/Float32MultiArray): Person bounding box [x, y, w, h, confidence]
- `/vision/debug_image` (sensor_msgs/Image): Debug image with detections (optional)
- `/cmd_vel_follow` (geometry_msgs/Twist): Following velocity commands
- `/vision/ttc_alert` (std_msgs/String): TTC emergency alerts

### Subscribers
- `/camera/image_raw` (sensor_msgs/Image): Camera images for processing

## Configuration

All nodes use ROS parameters for configuration. See `config/default.yaml` for complete parameter reference.

### Key Parameters

**Camera:**
- `device`: Camera device path (default: '/dev/video0')
- `width/height/fps`: Camera settings
- `publish_rate`: Image publishing rate

**Detector:**
- `model_config/weights`: Neural network model paths
- `confidence_threshold`: Detection confidence threshold (default: **0.2** — 실내 환경에서 MobileNet-SSD v2 COCO 검출 신뢰도가 0.3~0.49 범위에 집중됨. 0.5 이상으로 올리면 실제 검출이 전부 필터링됨)
- `detection_interval`: Process every N frames (reduces CPU load)
- `publish_debug_image`: 검출 박스가 그려진 프레임을 `/vision/debug_image`로 발행 (기본: True)

**Follow Controller:**
- `center_x_gain`: Angular velocity gain for centering
- `height_gain`: Linear velocity gain for distance
- `target_height_ratio`: Desired person size in frame
- `max_linear/angular_velocity`: Safety velocity limits

**TTC:**
- `ttc_threshold`: Time-to-collision alert threshold (seconds)
- `processing_interval`: Optical flow processing frequency

## Model Setup

### Required Models

Place model files in the `models/` directory:

```bash
cd models/
wget https://github.com/opencv/opencv/raw/4.x/samples/dnn/mobilenet_ssd_v2_coco.pbtxt
wget https://github.com/opencv/opencv/raw/4.x/samples/dnn/mobilenet_ssd_v2_coco.pb
```

### Model Configuration

Model paths are set via ROS parameters:
```yaml
detector:
  model_config: 'models/mobilenet_ssd_v2_coco.pbtxt'
  model_weights: 'models/mobilenet_ssd_v2_coco.pb'
```

## Usage

### Launch Complete System
```bash
ros2 launch buddybot_vision vision.launch.py
```

### Individual Nodes

**Camera only:**
```bash
ros2 run buddybot_vision camera_node
```

**Detector only:**
```bash
ros2 run buddybot_vision detector_node --ros-args -p publish_debug_image:=true
```

**Follow controller only:**
```bash
ros2 run buddybot_vision follow_controller_node
```

**TTC monitoring only:**
```bash
ros2 run buddybot_vision ttc_node
```

### With Custom Parameters
```bash
ros2 run buddybot_vision detector_node --ros-args \
  -p confidence_threshold:=0.7 \
  -p detection_interval:=3
```

## Performance Optimization

### Reducing CPU Load

1. **Increase detection interval:**
   ```bash
   -p detection_interval:=10  # Process every 10th frame
   ```

2. **Lower camera resolution:**
   ```bash
   -p width:=320 -p height:=240
   ```

3. **Reduce TTC processing:**
   ```bash
   -p processing_interval:=5
   ```

4. **Disable debug output:**
   ```bash
   -p publish_debug_image:=false
   ```

### Raspberry Pi 5 Optimizations

- OpenCV DNN automatically uses CPU optimizations
- Models are lightweight (MobileNet-SSD v2)
- Configurable processing intervals prevent overload
- Efficient optical flow algorithms

## Dependencies

- `rclpy`: ROS 2 Python client
- `cv_bridge`: ROS-OpenCV bridge
- `opencv`: Computer vision library
- `sensor_msgs`: ROS sensor messages
- `geometry_msgs`: ROS geometry messages
- `std_msgs`: ROS standard messages

## Troubleshooting

### Camera Issues
- Check device path: `v4l2-ctl --list-devices`
- Verify camera permissions
- Test with: `gst-launch-1.0 v4l2src device=/dev/video0 ! videoconvert ! autovideosink`

### Detection Issues
- Verify model files exist and are readable
- Check model paths in node log: `ros2 run buddybot_vision detector_node --ros-args --log-level info 2>&1 | grep model_`
- Default `confidence_threshold` is 0.2. Do not raise above 0.4 in indoor environments — MobileNet-SSD v2 COCO detects at 0.3–0.49 range indoors
- Enable debug image to visualize detections: `publish_debug_image:=true`

### QoS Notes
- All vision publishers use `BEST_EFFORT, VOLATILE, depth=1` QoS
- Subscribers of `/vision/person_bbox` and `/vision/debug_image` **must** use BEST_EFFORT QoS
- RELIABLE subscriber + BEST_EFFORT publisher = silent incompatibility in ROS 2, no messages delivered
- `panel_server.py` was fixed (2026-05-04) to use BEST_EFFORT for `/vision/person_bbox` subscription

### Performance Issues
- Monitor CPU usage: `top` or `htop`
- Increase processing intervals
- Reduce camera resolution/FPS
- Disable unnecessary debug outputs

## Architecture Notes

- **Modular Design:** Each node runs independently for fault isolation
- **Configurable Parameters:** All thresholds and gains are ROS parameters
- **Safety First:** Velocity limits and deadzones prevent unsafe behavior
- **Efficient Processing:** Interval-based processing reduces computational load
- **Real-time Operation:** Optimized for 30 FPS camera input with low latency