from ultralytics import YOLO
import torch
from tqdm import tqdm
import cv2
import os
import logging
from collections import defaultdict
from queue import Queue
from threading import Thread, Lock
from statistics import median
import json

logging.getLogger('ultralytics').setLevel(logging.CRITICAL)

# Load configuration from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

# Fetch inference settings from config
inference_config = config["inference"]

output_dir = inference_config["output_dir"]
debug = inference_config["debug"]
log_output_only = inference_config["log_output_only"]
enable_preprocessing = inference_config["enable_preprocessing"]
histogram_equalization_weight = inference_config["histogram_equalization_weight"]
frame_check_interval = inference_config["frame_check_interval"]
grace_period_val = inference_config["grace_period_val"]
min_detect_percent = inference_config["min_detect_percent"]
default_confidence_threshold = inference_config["default_confidence_threshold"]
user_defined_confidence_thresholds = inference_config["user_defined_confidence_thresholds"]
model_path = inference_config["model_path"]

model = YOLO(model_path)

#-----------------------------------
# Create necessary directories
os.makedirs(output_dir, exist_ok=True)
print_lock = Lock()

def log_detection_window(log_queue, object_name, timestamp, frame_count, window_length, detection_percentage, confidence_values, saved_to_output):
    if log_output_only and not saved_to_output:
        return

    avg_confidence = sum(confidence_values) / max(len(confidence_values), 1)
    median_confidence = median(confidence_values) if confidence_values else 0
    peak_confidence = max(confidence_values, default=0)

    log_message = (
        f"\n==== Detection Window for '{object_name}' ====\n"
        f" - Timestamp: {timestamp:.2f} seconds\n"
        f" - Frame count: {frame_count}\n"
        f" - Window length: {window_length} frames\n"
        f" - Detection percentage: {detection_percentage:.2f}\n"
        f" - Average confidence level: {avg_confidence:.2f}\n"
        f" - Median confidence level: {median_confidence:.2f}\n"
        f" - Peak confidence level: {peak_confidence:.2f}\n"
        f" - Saved to output: {'Yes' if saved_to_output else 'No'}\n"
    )
    log_queue.put(log_message)

def get_confidence_threshold(object_name):
    return user_defined_confidence_thresholds.get(object_name, default_confidence_threshold)

def initialize_video_writer(object_name, filename, frame_width, frame_height, fps, video_output_dir):
    output_filename = os.path.join(video_output_dir, f'{object_name}-{os.path.splitext(filename)[0]}.mp4')
    return cv2.VideoWriter(output_filename, cv2.VideoWriter_fourcc(*'mp4v'), fps, (frame_width, frame_height))

def frame_reader(cap, queue):
    while True:
        success, frame = cap.read()
        if not success:
            break
        if enable_preprocessing:
            frame = apply_histogram_equalization(frame)
        queue.put(frame)
    queue.put(None)

def frame_writer(queue, video_writer):
    while True:
        item = queue.get()
        if item is None:
            break
        frame, object_name = item
        video_writer[object_name].write(frame)
        
def apply_histogram_equalization(frame):
    ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
    ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
    equalized_frame = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)
    
    # Blend the equalized image with the original image using the weight factor
    blended_frame = cv2.addWeighted(frame, 1 - histogram_equalization_weight, equalized_frame, histogram_equalization_weight, 0)
    
    return blended_frame
    
def create_directories(path_list):
    for path in path_list:
        os.makedirs(path, exist_ok=True)
        
def logger_thread(log_queue, log_filepath):
    with open(log_filepath, 'w') as log_file:
        while True:
            log_message = log_queue.get()
            if log_message is None:
                break
            log_file.write(log_message)

#---------------------------------
# Main program
def main(video_path, position=1, input_directory="vods"):
    # Get the video name and define output directories
    filename = os.path.basename(video_path)
    video_name = os.path.splitext(filename)[0]
    video_output_dir = os.path.join(output_dir, video_name)
    debug_dir = os.path.join(video_output_dir, "debug")

    create_directories([output_dir, video_output_dir, debug_dir])

    # Start the logger thread
    log_queue = Queue()
    log_filepath = os.path.join(debug_dir, f'{video_name}.log')
    logger_thread_instance = Thread(target=logger_thread, args=(log_queue, log_filepath))
    logger_thread_instance.start()

    print(f"Processing video: {filename}")
    video_path = os.path.join(input_directory, filename)
    
    detection_windows = defaultdict(list)
    currently_detected = defaultdict(bool)
    gracep_counters = defaultdict(int)
    video_writers = {}
    confidence_values = defaultdict(list)
    # Initialize dictionary to store frames for each detected object
    object_frames = defaultdict(list)
    
    cap = cv2.VideoCapture(video_path)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if not cap.isOpened():
        print(f"Error: Couldn't open video file {video_path}")
        return

    video_name = os.path.basename(video_path)
    with print_lock:
        progress_bar = tqdm(total=total_frames, position=position, leave=True, desc=video_name)
    
    log_filepath = os.path.join(debug_dir, f'{video_name}.log')
    debug_video_output = None
    if debug:
        debug_video_output = cv2.VideoWriter(os.path.join(debug_dir, f'{video_name}-debug.mp4'), cv2.VideoWriter_fourcc(*'mp4v'), fps, (frame_width, frame_height))
    
    frame_num = 0
    detected_object_ids = set()
    saved_objects = set()

    frame_queue = Queue(maxsize=10)
    writer_queue = Queue(maxsize=10)
    reader_thread = Thread(target=frame_reader, args=(cap, frame_queue))
    writer_thread = Thread(target=frame_writer, args=(writer_queue, video_writers))
    reader_thread.start()
    writer_thread.start()

    with open(log_filepath, 'w') as log_file:
        
        object_names = model.names
        while True:
            frame = frame_queue.get()
            if frame is None:
                break

            run_model = frame_num % frame_check_interval == 0

            if run_model:
                try:
                    results = model(frame)
                    detected_objects = set()
                    for i, conf in enumerate(results[0].boxes.conf.cpu().numpy()):
                        object_id = int(results[0].boxes.cls[i].cpu().numpy())
                        object_name = results[0].names.get(object_id)
                        if conf >= get_confidence_threshold(object_name):
                            detected_objects.add(object_id)
                            confidence_values[object_id].append(conf)

                except Exception as e:
                    print(f"Error processing frame {frame_num}: {e}")
                    # Skipping the current frame
                    frame_num += 1
                    progress_bar.update(1)
                    continue

                # Update the frame with detection results if in debug mode
                if debug:
                    frame = results[0].plot()
            else:
                detected_objects = set()

            # Write the (potentially updated) frame to the debug video
            if debug:
                debug_video_output.write(frame)
            
            for object_id in currently_detected:
                if currently_detected[object_id]:
                    object_frames[object_id].append(frame)
            
            for object_id in detected_objects:
                detection_windows[object_id].append(frame_num)
                gracep_counters[object_id] = grace_period_val * frame_check_interval

            for object_id in gracep_counters:
                object_name = object_names[object_id] if object_id < len(object_names) else f"Error! Unknown object {object_id}"

                if object_id not in detected_objects and run_model:
                    if gracep_counters[object_id] > 0:
                        detection_windows[object_id].append(-1)
                        gracep_counters[object_id] -= frame_check_interval
                    else:
                        gracep_counters[object_id] = 0

            for object_id, window in detection_windows.items():
                object_name = object_names.get(object_id, f"Error! Unknown object {object_id}")

                if gracep_counters[object_id] > 0:
                    currently_detected[object_id] = True
                else:
                    if currently_detected[object_id]:
                        detection_percentage = sum(1 for f in window if f >= 0) / max(len(window), 1)
                        last_valid_frame = max((f for f in window if f >= 0), default=frame_num)
                        timestamp = last_valid_frame / fps
                        saved_to_output = detection_percentage >= min_detect_percent
                        
                        # Write the frames to the output file if the detection percentage meets the threshold
                        if saved_to_output:
                            saved_objects.add(object_name)
                            if object_name not in video_writers:
                                video_writers[object_name] = initialize_video_writer(object_name, filename, frame_width, frame_height, fps, video_output_dir)
                            for output_frame in object_frames[object_id]:
                                writer_queue.put((output_frame, object_name))

                        log_detection_window(
                            log_queue=log_queue,
                            object_name=object_name,
                            timestamp=timestamp,
                            frame_count=len([f for f in window if f >= 0]),
                            window_length=len(window),
                            detection_percentage=detection_percentage,
                            confidence_values=confidence_values[object_id],
                            saved_to_output=saved_to_output,
                        )
                        
                         # Clear the list of frames for the object at the end of the detection window
                        object_frames[object_id] = []

                        detection_windows[object_id] = []
                        currently_detected[object_id] = False
                        confidence_values[object_id] = []

            with print_lock:
                progress_bar.update(1)
            frame_num += 1
            
        detected_object_names = [object_names.get(object_id, f"Error! Unknown object {object_id}") for object_id in detected_object_ids]
        with print_lock:
            progress_bar.close()
        
        writer_queue.put(None)
        writer_thread.join()
        
        for writer in video_writers.values():
            writer.release()
        
        # Organizing the output
        with print_lock:
            print(f"\n------------\nProcessed video: {filename}")
            detected_object_names = [object_names.get(object_id, f"Error! Unknown object {object_id}") for object_id in detected_object_ids]
            #if detected_object_names:
                #print("Detected objects:")
                #for object_name in detected_object_names:
                    #print(f" - {object_name}")
                #print("\n=------------------\n")
            #else:
                #print("No objects detected.\n")
    
    if debug:    
        debug_video_output.release()
    cap.release()
    log_queue.put(None)
        
if __name__ == '__main__':
    main()
