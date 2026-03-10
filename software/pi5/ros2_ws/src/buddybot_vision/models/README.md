# Vision Models

This directory contains neural network models used by the BuddyBot vision system.

## Required Models

### MobileNet-SSD v2 (Person Detection)

**Files:**
- `mobilenet_ssd_v2_coco.pbtxt` - Model configuration
- `mobilenet_ssd_v2_coco.pb` - Model weights

**Download:**
```bash
# Download from OpenCV Zoo
wget https://github.com/opencv/opencv/raw/4.x/samples/dnn/mobilenet_ssd_v2_coco.pbtxt
wget https://github.com/opencv/opencv/raw/4.x/samples/dnn/mobilenet_ssd_v2_coco.pb
```

**Alternative Sources:**
- TensorFlow Model Zoo
- OpenCV DNN samples

## Model Optimization

For Raspberry Pi 5, the models are automatically optimized for CPU inference using OpenCV DNN backend.

## Configuration

Model paths are configured via ROS parameters in the detector node:
- `model_config`: Path to .pbtxt file
- `model_weights`: Path to .pb file

## Performance Notes

- MobileNet-SSD v2 provides good balance of accuracy and speed
- Detection interval can be adjusted to reduce CPU load
- Consider quantization for further optimization if needed