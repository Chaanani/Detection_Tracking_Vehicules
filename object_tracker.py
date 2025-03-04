import os
# comment out below line to enable tensorflow logging outputs
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import time
import tensorflow as tf
physical_devices = tf.config.experimental.list_physical_devices('GPU')
if len(physical_devices) > 0:
    tf.config.experimental.set_memory_growth(physical_devices[0], True)
from absl import app, flags, logging
from absl.flags import FLAGS
import core.utils as utils
from core.yolov4 import filter_boxes
from tensorflow.python.saved_model import tag_constants
from core.config import cfg
from PIL import Image
import cv2
import numpy as np
import matplotlib.pyplot as plt
from tensorflow.compat.v1 import ConfigProto
from tensorflow.compat.v1 import InteractiveSession
# deep sort imports
from deep_sort import preprocessing, nn_matching
from deep_sort.detection import Detection
from deep_sort.tracker import Tracker
from tools import generate_detections as gdet
flags.DEFINE_string('weights', './checkpoints/yolov4-416',
                    'path to weights file')
flags.DEFINE_integer('size', 416, 'resize images to')
flags.DEFINE_boolean('tiny', False, 'yolo or yolo-tiny')
flags.DEFINE_string('model', 'yolov4', 'yolov3 or yolov4')
flags.DEFINE_string('video', './data/video/test.mp4', 'path to input video or set to 0 for webcam')
flags.DEFINE_string('output', None, 'path to output video')
flags.DEFINE_string('output_format', 'XVID', 'codec used in VideoWriter when saving video to file')
flags.DEFINE_float('iou', 0.45, 'iou threshold')
flags.DEFINE_float('score', 0.50, 'score threshold')
flags.DEFINE_boolean('dont_show', False, 'dont show video output')
flags.DEFINE_boolean('info', False, 'show detailed info of tracked objects')
flags.DEFINE_boolean('count', False, 'count objects being tracked on screen')

import math
import datetime
import os
import warnings
from inter_angl import intersect, vector_angle,tlbr_midpoint
show_detections = False
from collections import Counter,deque


def main(_argv):
    # Definition of the parameters
    max_cosine_distance = 0.4
    nn_budget = None
    nms_max_overlap = 1.0
    
    # initialize deep sort
    model_filename = 'model_data/mars-small128.pb'
    encoder = gdet.create_box_encoder(model_filename, batch_size=1)
    # calculate cosine distance metric
    metric = nn_matching.NearestNeighborDistanceMetric("cosine", max_cosine_distance, nn_budget)
    # initialize tracker
    tracker = Tracker(metric)

    # load configuration for object detector
    config = ConfigProto()
    config.gpu_options.allow_growth = True
    session = InteractiveSession(config=config)
    STRIDES, ANCHORS, NUM_CLASS, XYSCALE = utils.load_config(FLAGS)
    input_size = FLAGS.size
    video_path = FLAGS.video

    # load tflite model if flag is set
    if FLAGS.framework == 'tflite':
        interpreter = tf.lite.Interpreter(model_path=FLAGS.weights)
        interpreter.allocate_tensors()
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        print(input_details)
        print(output_details)
    # otherwise load standard tensorflow saved model
   
    Saved_model_loaded=tf.saved_model.load(FLAGS.weights)
    infer = Saved_model_loaded.signatures[tf.saved_model.DEFAULT_SERVING_SIGNATURE_DEF_KEY]
    

    ###################
    ###################
    ###################

    # begin video capture
    try:
        vid = cv2.VideoCapture(int(video_path))
    except:
        vid = cv2.VideoCapture(video_path)

    out = None

    # get video ready to save locally if flag is set
    if FLAGS.output:
        # by default VideoCapture returns float instead of int
        width = int(vid.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(vid.get(cv2.CAP_PROP_FPS))
        codec = cv2.VideoWriter_fourcc(*FLAGS.output_format)
        out = cv2.VideoWriter(FLAGS.output, codec, fps, (width, height))

    frame_num = 0

  
    current_date = datetime.datetime.now().date()
    count_dict = {}  # initiate dict for storing counts

    total_counter = 0
    up_count = 0
    down_count = 0

    class_counter = Counter()  # store counts of each detected class
    already_counted = deque(maxlen=50)  # temporary memory for storing counted IDs
    intersect_info = []  # initialise intersection list

    memory = {}

    # while video is running
    while True:
        return_value, frame = vid.read()
        if return_value:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame)
        else:
            print('Video has ended or failed, try a different video format!')
            break
        frame_num +=1
        print('Frame #: ', frame_num)
        frame_size = frame.shape[:2]
        image_data = cv2.resize(frame, (input_size, input_size))
        image_data = image_data / 255.
        image_data = image_data[np.newaxis, ...].astype(np.float32)
        start_time = time.time()

        batch_data = tf.constant(image_data)
        pred_bbox = infer(batch_data)
        for key, value in pred_bbox.items():
            boxes = value[:, :, 0:4]
            pred_conf = value[:, :, 4:]

        boxes, scores, classes, valid_detections = tf.image.combined_non_max_suppression(boxes=tf.reshape(boxes, (tf.shape(boxes)[0], -1, 1, 4)),scores=tf.reshape(pred_conf, (tf.shape(pred_conf)[0], -1, tf.shape(pred_conf)[-1])),max_output_size_per_class=50,max_total_size=50,iou_threshold=FLAGS.iou,score_threshold=FLAGS.score)
        # convert data to numpy arrays and slice out unused elements
        num_objects = valid_detections.numpy()[0]
        bboxes = boxes.numpy()[0]
        bboxes = bboxes[0:int(num_objects)]
        scores = scores.numpy()[0]
        scores = scores[0:int(num_objects)]
        classes = classes.numpy()[0]
        classes = classes[0:int(num_objects)]

        # format bounding boxes from normalized ymin, xmin, ymax, xmax ---> xmin, ymin, width, height
        original_h, original_w, _ = frame.shape
        bboxes = utils.format_boxes(bboxes, original_h, original_w)

        # store all predictions in one parameter for simplicity when calling functions
        pred_bbox = [bboxes, scores, classes, num_objects]

        # read in all class names from config
        class_names = utils.read_class_names(cfg.YOLO.CLASSES)

        # by default allow all classes in .names file
        #allowed_classes = list(class_names.values())
        
        # custom allowed classes (uncomment line below to customize tracker for only people)
        allowed_classes = ['car','motorbike','bus','truck']

        # loop through objects and use class index to get class name, allow only classes in allowed_classes list
        names = []
        deleted_indx = []
        for i in range(num_objects):
            class_indx = int(classes[i])
            class_name = class_names[class_indx]
            if class_name not in allowed_classes:
                deleted_indx.append(i)
            else:
                names.append(class_name)
        names = np.array(names)
        count = len(names)
        if FLAGS.count:
            cv2.putText(frame, "Objects being tracked: {}".format(count), (5, 35), cv2.FONT_HERSHEY_COMPLEX_SMALL, 2, (0, 255, 0), 2)
            print("Objects being tracked: {}".format(count))
        # delete detections that are not in allowed_classes
        bboxes = np.delete(bboxes, deleted_indx, axis=0)
        scores = np.delete(scores, deleted_indx, axis=0)

        # encode yolo detections and feed to tracker
        features = encoder(frame, bboxes)
        detections = [Detection(bbox, score, class_name, feature) for bbox, score, class_name, feature in zip(bboxes, scores, names, features)]

        #initialize color map
        cmap = plt.get_cmap('tab20b')
        colors = [cmap(i)[:3] for i in np.linspace(0, 1, 20)]

        # run non-maxima supression
        boxs = np.array([d.tlwh for d in detections])
        scores = np.array([d.confidence for d in detections])
        classes = np.array([d.class_name for d in detections])
        indices = preprocessing.non_max_suppression(boxs, classes, nms_max_overlap, scores)
        detections = [detections[i] for i in indices]       

        # Call the tracker
        tracker.predict()
        tracker.update(detections)
        line = [(0, int(0.7 * frame.shape[0])), ( int(0.8 * frame.shape[1]), int(0.7 * frame.shape[0]))]
        cv2.line(frame, line[0], line[1], (0, 255, 255), 2)
        # update tracks
        for track in tracker.tracks:
            if not track.is_confirmed() or track.time_since_update > 1:
                continue 
            bbox = track.to_tlbr()
            track_cls = track.get_class()
            midpoint =tlbr_midpoint(bbox)
            origin_midpoint = (midpoint[0], frame.shape[0] - midpoint[1]) 
            if track.track_id not in memory:
                memory[track.track_id] = deque(maxlen=2)
            memory[track.track_id].append(midpoint)
            previous_midpoint = memory[track.track_id][0]
            origin_previous_midpoint = (previous_midpoint[0], frame.shape[0] - previous_midpoint[1])
            cv2.line(frame, midpoint, previous_midpoint, (0, 255, 0), 2)
            if intersect(midpoint, previous_midpoint, line[0], line[1]) and track.track_id not in already_counted:
                class_counter[track_cls] += 1
                total_counter += 1
                # draw red line
                cv2.line(frame, line[0], line[1], (0, 0, 255), 2)
                already_counted.append(track.track_id)  # Set already counted for ID to true.
                intersection_time = datetime.datetime.now() - datetime.timedelta(microseconds=datetime.datetime.now().microsecond)
                angle =vector_angle(origin_midpoint, origin_previous_midpoint)
                intersect_info.append([track_cls, origin_midpoint, angle, intersection_time])
                if angle > 0:
                     up_count += 1
                if angle < 0:
                     down_count += 1
            cv2.rectangle(frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (255, 255, 255), 2)  # WHITE BOX
            cv2.putText(frame, "ID: " + str(track.track_id), (int(bbox[0]), int(bbox[1])), 0,1.5e-3 * frame.shape[0], (0, 255, 0), 2)
            if not show_detections:
                cv2.putText(frame, str(track_cls), (int(bbox[0]), int(bbox[3])), 0,1e-3 * frame.shape[0], (0, 255, 0), 2)
        if len(memory) > 50:
            del memory[list(memory)[0]]
            # Draw total count.
        cv2.putText(frame, "Total: {} ".format(str(total_counter)), (int(0.05 * frame.shape[1]), int(0.1 * frame.shape[0])), 0,1.5e-3 * frame.shape[0], (0, 255, 255), 2)        
        if show_detections:
            for det in detections:
                bbox = det.to_tlbr()
                score = "%.2f" % (det.confidence * 100) + "%"
                cv2.rectangle(frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (255, 0, 0), 2)  # BLUE BOX
                if len(classes) > 0:
                  det_cls = det.class_name
                  cv2.putText(frame, str(det_cls) + " " + score, (int(bbox[0]), int(bbox[3])), 0,1.5e-3 * frame.shape[0], (0, 255, 0), 2)
        y = 0.2 * frame.shape[0]
        for cls in class_counter:
            class_count = class_counter[cls]
            cv2.putText(frame, str(cls) + " " + str(class_count), (int(0.05 * frame.shape[1]), int(y)), 0,1.5e-3 * frame.shape[0], (0, 255, 255), 2)
            y += 0.05 * frame.shape[0]

        # calculate current minute
        now = datetime.datetime.now()
        rounded_now = now - datetime.timedelta(microseconds=now.microsecond)  # round to nearest second
        current_minute = now.time().second
        if current_minute == 0 and len(count_dict) > 1:
            count_dict = {}  # reset counts every hour
        else:
            # write counts to file for every set interval of the hour
            write_interval = 18
            if current_minute % write_interval == 0:  # write to file once only every write_interval minutes
                if current_minute not in count_dict:
                    count_dict[current_minute] = True
                    total_filename = 'count for  {}.xls'.format(current_date)
                    counts_folder = 'counts/'
                    if not os.access(counts_folder + str(current_date) , os.W_OK):
                        os.makedirs(counts_folder + str(current_date) )
                    total_count_file = open(counts_folder+ total_filename, 'a')
                    print('{} writing...'.format(rounded_now))
                    print('Writing current total count ({}) and directional counts to file.'.format(total_counter))
                    total_count_file.write(',{},{},total:{}'.format(str(rounded_now),str(),str(total_counter)))
                    for cls in class_counter:
                      class_count=class_counter[cls]
                      total_count_file.write(',{}:{}'.format(str(cls),str(class_count)) )
                    total_count_file.write('\n')
                    total_count_file.close()
                    total_counter=0
                    class_counter=Counter()
                    

                    #if class exists in class counter, create file and write counts

                    #if not os.access(counts_folder + str(current_date) + '/classes', os.W_OK):
                     #  os.makedirs(counts_folder + str(current_date) + '/classes')
                    #for cls in class_counter:
                        #class_count= class_counter[cls]
                        #print('Writing current {} count ({}) to file.'.format(cls, class_count))
                        #class_filename = 'Class counts for {}.xls'.format(current_date)
                        #class_count_file = open(counts_folder + str(current_date) + '/classes/' + class_filename, 'a')
                        #class_count_file.write("{}, {}\n".format(rounded_now, str(class_count)))
                        #class_count_file.close()
                    #class_counter=Counter()
        #if FLAGS.info:
         #       print("Tracker ID: {}, Class: {},  BBox Coords (xmin, ymin, xmax, ymax): {}".format(str(track.track_id), track_cls, (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))))

        # calculate frames per second of running detections
        fps = 1.0 / (time.time() - start_time)
        print("FPS: %.2f" % fps)
        result = np.asarray(frame)
        result = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        if not FLAGS.dont_show:
            cv2.imshow("Output Video", result)
        
        # if output flag is set, save video file
        if FLAGS.output:
            out.write(result)
        if cv2.waitKey(1) & 0xFF == ord('q'): break
    cv2.destroyAllWindows()

if __name__ == '__main__':
    try:
        app.run(main)
    except SystemExit:
        pass
