# -*- coding: utf-8 -*-
"""vehicle_objects_and_violation_detection_yolov5m.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1vxPRf-iHPYoee8K08slu_G3Vg4fdw5st
"""

import firebase_admin
from firebase_admin import credentials, storage, firestore # database
import pyrebase # for the storage
from keras.models import load_model
from collections import deque
from timebudget import timebudget
from multiprocessing import Pool
from datetime import datetime
import pytz
import matplotlib.pyplot as plt
import numpy as np
import argparse
import pickle
import cv2
import os
import time 
import re
import torch
import statistics
from google.colab.patches import cv2_imshow

# 1-Define Global Parameters for vhicle detection

#The constants INPUT_WIDTH and INPUT_HEIGHT are for the blob size. 
#The BLOB stands for Binary Large Object. It contains the data in readable raw format. 
#The image must be converted to a blob so the network can process it. 
#In our case, it is a 4D array object with the shape (1, 3, 640, 640).

#SCORE_THRESHOLD: To filter low probability class scores.
#NMS_THRESHOLD: To remove overlapping bounding boxes.
#CONFIDENCE_THRESHOLD: Filters low probability detections.

# Constants.
INPUT_WIDTH = 640
INPUT_HEIGHT = 640
SCORE_THRESHOLD = 0.7
NMS_THRESHOLD = 0.7
CONFIDENCE_THRESHOLD = 0.7

# Text parameters.
FONT_FACE = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.5
THICKNESS = 1

# Colors
BLACK  = (0,0,0)
BLUE   = (255,178,50)
YELLOW = (0,255,255)
RED = (0,0,255)

# 2-Draw YOLOv5 Inference Label

#The function draw_label annotates the class names anchored to the top left corner of the bounding box. 
#The code is fairly simple. We pass the text string as a label in the argument, 
#which is passed to the OpenCV function getTextSize().
#It returns the bounding box size that the text string would take up. 
#These dimension values are used to draw a black background rectangle on which the label is rendered by putText() function.

def draw_label(input_image, label, left, top):
    """Draw text onto image at location."""
    
    # Get text size.
    text_size = cv2.getTextSize(label, FONT_FACE, FONT_SCALE, THICKNESS)
    dim, baseline = text_size[0], text_size[1]
    # Use text size to create a BLACK rectangle. 
    cv2.rectangle(input_image, (left, top), (left + dim[0], top + dim[1] + baseline), BLACK, cv2.FILLED);
    # Display text inside the rectangle.
    cv2.putText(input_image, label, (left, top + dim[1]), FONT_FACE, FONT_SCALE, YELLOW, THICKNESS, cv2.LINE_AA)

# 3-PRE-PROCESSING YOLOv5 Model

#The function pre–process takes the image and the network as arguments. 
#At first, the image is converted to a blob. Then it is set as input to the network. 
#The function getUnconnectedOutLayerNames() provides the names of the output layers. 
#It has features of all the layers, through which the image is forward propagated to acquire the detections. 
#After processing, it returns the detection results.

def pre_process(input_image, net):
      # Create a 4D blob from a frame.
      blob = cv2.dnn.blobFromImage(input_image, 1/255, (INPUT_WIDTH, INPUT_HEIGHT), [0,0,0], 1, crop=False)

      # Sets the input to the network.
      net.setInput(blob)
      # Runs the forward pass to get output of the output layers.
      output_layers = net.getUnconnectedOutLayersNames()
      outputs = net.forward(output_layers)
      # print(outputs[0].shape)

      return outputs

#POST-PROCESSING YOLOv5 Prediction Output
#https://learnopencv.com/object-detection-using-yolov5-and-opencv-dnn-in-c-and-python/#Download-Code

#A. Filter Good Detections given by YOLOv5 Models
# 1-Loop through detections.
# 2-Filter out good detections.
# 3-Get the index of the best class score.
# 4-Discard detections with class scores lower than the threshold value.

#B. Remove Overlapping Boxes Predicted by YOLOv5
#After filtering good detections, we are left with the desired bounding boxes. 
#However, there can be multiple overlapping bounding boxes, 
#This is solved by performing Non-Maximum Suppression. 
#The function NMSBoxes() takes a list of boxes, calculates IOU (Intersection Over Union), 
#and decides to keep the boxes depending on the NMS_THRESHOLD.

def post_process(input_image, outputs):
    # Lists to hold respective values while unwrapping.
    class_ids = []
    confidences = []
    boxes = []
    detected_vehicles = []

    # Rows.
    rows = outputs[0].shape[1]

    image_height, image_width = input_image.shape[:2]

    # Resizing factor.
    x_factor = image_width / INPUT_WIDTH
    y_factor =  image_height / INPUT_HEIGHT

    # Iterate through 25200 detections.
    for r in range(rows):
      row = outputs[0][0][r]
      confidence = row[4]

      # Discard bad detections and continue.
      if confidence >= CONFIDENCE_THRESHOLD:
        classes_scores = row[5:]

        # Get the index of max class score.
        class_id = np.argmax(classes_scores)

        #  Continue if the class score is above threshold.
        if (classes_scores[class_id] > SCORE_THRESHOLD):
          confidences.append(confidence)
          class_ids.append(class_id)

          cx, cy, w, h = row[0], row[1], row[2], row[3]

          left = int((cx - w/2) * x_factor)
          top = int((cy - h/2) * y_factor)
          width = int(w * x_factor)
          height = int(h * y_factor)
          
          box = np.array([left, top, width, height])
          boxes.append(box)

    # Perform non maximum suppression to eliminate redundant overlapping boxes with
    # lower confidences.
    indices = cv2.dnn.NMSBoxes(boxes, confidences, CONFIDENCE_THRESHOLD, NMS_THRESHOLD)
    for i in indices:
      box = boxes[i]
      left = box[0]
      top = box[1]
      width = box[2]
      height = box[3]
      cv2.rectangle(input_image, (left, top), (left + width, top + height), BLUE, 3*THICKNESS)
      label = "{}:{:.2f}".format(classes[class_ids[i]], confidences[i])
      detected_vehicles.append(classes[class_ids[i]])
      draw_label(input_image, label, left, top)

    return input_image, detected_vehicles

# Load class names.
classesFile = "/content/drive/MyDrive/Colab Notebooks/coco.names"
classes = None
with open(classesFile, 'rt') as f:
	classes = f.read().rstrip('\n').split('\n')

# Give the weight files to the model and load the network using them.
modelWeights = "/content/drive/MyDrive/Colab Notebooks/yolov5m.onnx"
net = cv2.dnn.readNetFromONNX (modelWeights)

#setUp 
cred = credentials.Certificate("/content/drive/MyDrive/rasd-d3906-firebase-adminsdk-1djor-9976e852c3.json")
firebase_admin.initialize_app(cred , {'storageBucket':'rasd-d3906.appspot.com'}) # run once ( database config )


firebaseConfig={
      "apiKey": "AIzaSyAN6rb8AKV_qMYknz38SVBZPcp3DGYWzzs",
      "authDomain": "rasd-d3906.firebaseapp.com",
      "databaseURL": "https://rasd-d3906.firebaseio.com",
      "projectId": "rasd-d3906",
      "storageBucket": "rasd-d3906.appspot.com",
      "messagingSenderId": "631946154635",
      "appId": "1:631946154635:android:57200f3f24d236d430fa8e",
      'serviceAccount': '/content/drive/MyDrive/rasd-d3906-firebase-adminsdk-1djor-9976e852c3.json'
      }
# firebase = pyrebase.initialize_app(firebaseConfig) # for storage configure 
# storage = firebase.storage() #storage

db1=firestore.client()
result = db1.collection('drivers').get() #get the number of users
numUsers = len(result)
# print("numUsers", numUsers)

#get the users ids
users = []
for i in range(numUsers):
  users.append(result[i].to_dict()['id'])

print(users)

def calcDecision(trueCountArray):
  # calc mean and median and see the variance
  if(len(trueCountArray) > 0):
    x = statistics.median(trueCountArray)
    y = statistics.mean(trueCountArray)
    print("median , mean",x,y)
    if (abs(x-y)<2):
      return True
    else:
      return False
  else:
    return False

# print_results(video, filename)
def print_results(video, filename, limit=None):
        trueCount = 0

        #print("video.name",filename)
        #print("video",video)

        print("Loading model ...")      
        model = load_model('/content/drive/MyDrive/TEST_DATA/All_Model_MobileNetV2_newNormal2.h5')
        Q = deque(maxlen=128)
        vs = cv2.VideoCapture(video)
        writer = None
        (W, H) = (None, None)
        count = 1
        frameCounter = 0
        predCountArray = []
        trueCountArray = []
        decision = False
        

        while True:
          # read the next frame from the file
          (grabbed, frame) = vs.read()
          frameCounter += 1
          # if the frame was not grabbed, then we have reached the end of the stream
          if not grabbed:
                break
          # print("frameCounter",frameCounter)
          if frameCounter == 30:
            print("last frame per seond")
            output = frame.copy()
            # Process image.
            detections = pre_process(frame, net)
            output,detected_vehicles_arr = post_process(frame.copy(), detections)
            # Put efficiency information. The function getPerfProfile returns the overall time for inference(t) and the timings for each of the layers(in layersTimes)
            t, _ = net.getPerfProfile()
            label = 'Inference time: %.2f ms' % (t * 1000.0 / cv2.getTickFrequency())
            if (classes[2] or classes[3] or classes[5]or classes[7]) in detected_vehicles_arr:
              print('vehicle found')
            else:
              print('vehicle not found')
              frameCounter = 0
              continue
            
             
            # if the frame dimensions are empty, grab them
            if W is None or H is None:
              (H, W) = frame.shape[:2]

            # clone the output frame, then convert it from BGR to RGB
            # ordering, resize the frame to a fixed 128x128, and then
            # perform mean subtraction    
            # output = frame.copy()
            # cv2.putText(output, label, (20, 40), FONT_FACE, FONT_SCALE, RED, THICKNESS, cv2.LINE_AA)
              
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (128, 128)).astype("float32")
            frame = frame.reshape(128, 128, 3) / 255

            # make predictions on the frame and then update the predictions queue
            preds = model.predict(np.expand_dims(frame, axis=0))[0]
            print("preds",preds)
            Q.append(preds)

            # perform prediction averaging over the current history of previous predictions
            results = np.array(Q).mean(axis=0)
            i = (preds > 0.50)[0]
            label = i

            text_color = (0, 255, 0) # default : green

            if label: # Violence prob
                text_color = (0, 0, 255) # red
                trueCount = trueCount + 1 # added by dhai
                predCountArray.append("True")

            else:
               text_color = (0, 255, 0)
               predCountArray.append("False")

            text = "Violation: {}".format(label)
            FONT = cv2.FONT_HERSHEY_SIMPLEX 
            cv2.putText(output, text, (35, 50), FONT,1.25, text_color, 3)
            # check if the video writer is None
            if writer is None:
              # initialize our video writer
              fourcc = cv2.VideoWriter_fourcc(*"mp4v")
              writer = cv2.VideoWriter(os.path.split(filename)[1], fourcc, 30,(W, H), True)
        
            # write the output frame to disk
            writer.write(output)
            frameCounter = 0

        # release the file pointersq
        print("[INFO] cleaning up...")
        

        if(len(predCountArray) > 0):
          for i in range(0,len(predCountArray)):
            # print("i",i)
            if (predCountArray[i] == "True"):          
              trueCountArray.append(i+1)
              
          print("predCountArray",predCountArray)
          print("trueCountArray",trueCountArray)
          decision = calcDecision(trueCountArray)
          print("decision for file: ",os.path.split(filename), " ",decision)

    




     

        if(decision == "False"): # change the thrshold 
          storage.delete(filename, token = any) # delete the video ( if it is not violation )
          # print("deleted")
        else:
          blob = storage.bucket.blob(filename) 
          new_name =os.path.split(filename)[0]+"/"+"1_" +os.path.split(filename)[1] # change the name from filename ----> 1_filename (to indicate it is violation)
          #print(new_name)
          storage.bucket.rename_blob(blob, new_name=os.path.split(filename)[0]+"/"+"1_" +os.path.split(filename)[1]) # rename the file 
          #rename bucket
          datetime_ist = datetime.now(pytz.timezone('Asia/Riyadh'))
          drivers = db.collection("drivers")

          # add pending report
          # add an empty document
          doc_ref = drivers.document(filename.split("/")[0]).collection('reports').document() # filename.split("/")[0] --> driver doc id 
          #set all the fields of the pending report
          print(doc_ref)
          addReport = doc_ref.set({
              'addInfo': 'null',
              'id': doc_ref.id,
              'status': 0,
              'v_type': 'null',
              'date': datetime_ist.strftime('%Y:%m:%d'),
              'time': datetime_ist.strftime('%H:%M:%S '),
          })
          # add the video to the report (sub collection)
          VideoDoc = drivers.document(filename.split("/")[0]).collection('reports').document(doc_ref.id).collection('video').document() # doc_ref.id --> report id 
          addVideo = VideoDoc.set({
              'id': VideoDoc.id,
              'video_url': storage.child(new_name).get_url(None)
          })

#   print('--------------in predictViolation', uid)

firebase = pyrebase.initialize_app(firebaseConfig) # for storage configure 
storage = firebase.storage() #storage
print("in predict")
db=firestore.client()
all_files = storage.list_files()
for file in all_files:
  if (os.path.split(file.name)[1] != ''):
    strv = os.path.split(file.name)[1] #get the video file name
    match = strv[0]
    # if(match == '1'):
    #   print("not allowed")
    # else: 
    print_results(storage.child(file.name).get_url(None), file.name) # calling the model (the video not proccessed eat)
