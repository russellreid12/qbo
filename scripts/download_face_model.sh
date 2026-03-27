#!/bin/bash
# Download OpenCV DNN face detection model for QBO robot
# This is the Caffe-based SSD face detector (~10MB total)

set -e

MODEL_DIR="/opt/qbo/models"
mkdir -p "$MODEL_DIR"

PROTO_URL="https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
MODEL_URL="https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel"

PROTO_FILE="$MODEL_DIR/deploy.prototxt"
MODEL_FILE="$MODEL_DIR/res10_300x300_ssd_iter_140000.caffemodel"

echo "Downloading DNN face detection model to $MODEL_DIR ..."

if [ -f "$PROTO_FILE" ]; then
    echo "  deploy.prototxt already exists, skipping."
else
    echo "  Downloading deploy.prototxt ..."
    curl -L -o "$PROTO_FILE" "$PROTO_URL"
fi

if [ -f "$MODEL_FILE" ]; then
    echo "  caffemodel already exists, skipping."
else
    echo "  Downloading res10_300x300_ssd_iter_140000.caffemodel (~10MB) ..."
    curl -L -o "$MODEL_FILE" "$MODEL_URL"
fi

echo "Done! Model files are in $MODEL_DIR"
echo "  $PROTO_FILE"
echo "  $MODEL_FILE"
