from ultralytics import YOLO
from scipy.spatial import procrustes
import numpy as np
import cv2
import time
from scheduler.thread_manager import MyThread

__fei_eyes = None
class FeiEyes:
    
    def __init__(self):
    
        """   
        鼻子（0）
        左眼（1），右眼（2）
        左耳（3），右耳（4）
        左肩（5），右肩（6）
        左肘（7），右肘（8）
        左腕（9），右腕（10）
        左髋（11），右髋（12）
        左膝（13），右膝（14）
        左脚踝（15），右脚踝（16）
        """
        self.POSE_PAIRS = [ 
        (3, 5),  (5, 6),  # upper body
        (5, 7), (6, 8), (7, 9), (8, 10),  # lower body
        (11, 12), (11, 13), (12, 14), (13, 15)  # arms
        ]
        self.my_face = np.array([[154.4565, 193.7006],
                [181.8575, 164.8366],
                [117.1820, 164.3602],
                [213.5605, 193.0460],
                [ 62.7056, 193.5217]])
        self.is_running = False
        self.img = None
        
    def is_sitting(self,keypoints):
        left_hip, right_hip = keypoints[11][:2], keypoints[12][:2]
        left_knee, right_knee = keypoints[13][:2], keypoints[14][:2]
        left_ankle, right_ankle = keypoints[15][:2], keypoints[16][:2]

        # 髋部和膝盖的平均位置
        hip_knee_y = (left_hip[1] + right_hip[1] + left_knee[1] + right_knee[1]) / 4

        # 膝盖和脚踝的平均位置
        knee_ankle_y = (left_knee[1] + right_knee[1] + left_ankle[1] + right_ankle[1]) / 4

        # 如果髋部和膝盖的平均位置在膝盖和脚踝的平均位置上方，判定为坐着
        return hip_knee_y < knee_ankle_y

    def is_standing(self,keypoints): 
        head = keypoints[0][:2] 
        left_ankle, right_ankle = keypoints[15][:2], keypoints[16][:2] 
        # 头部位置较高且脚部与地面接触 
        if head[1] > left_ankle[1] and head[1] > right_ankle[1]: 
            return True 
        else:
            return False

    def get_counts(self):
        if not self.is_running:
            return 0,0,0
        return self.person_count, self.stand_count, self.sit_count

    def get_status(self):
        return self.is_running
    
    def get_img(self):
        if self.is_running:
            return self.img
        else:
            return None
    
    def start(self):
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            self.is_running = True
            MyThread(target=self.run, args=[cap]).start()

    def stop(self):
        self.is_running = False

    def run(self, cap):
         model = YOLO("yolov8n-pose.pt")
         while self.is_running:
            time.sleep(0.033)
            ret, frame = cap.read()
            self.img = frame
            operated_frame = frame.copy()
            if not ret:
                break
            results = model.predict(operated_frame, verbose=False)
            person_count = 0
            sit_count = 0
            stand_count = 0
            for res in results:  # loop over results
                for box, cls in zip(res.boxes.xyxy, res.boxes.cls):  # loop over detections
                    x1, y1, x2, y2 = box
                    cv2.rectangle(operated_frame, (int(x1.item()), int(y1.item())), (int(x2.item()), int(y2.item())), (0, 255, 0), 2)
                    cv2.putText(operated_frame, f"{res.names[int(cls.item())]}", (int(x1.item()), int(y1.item()) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)        
                if res.keypoints is not None and res.keypoints.size(0) > 0:  # check if keypoints exist
                    keypoints = res.keypoints[0]

                    #TODO人脸相似性的比较，待优化
                    keypoints_np = keypoints[0:5].cpu().numpy()
                    mtx1, mtx2, disparity = procrustes(keypoints_np[:, :2], self.my_face)
                    #总人数
                    person_count += 1
                    #坐着的人数
                    if self.is_sitting(keypoints):
                        sit_count += 1
                    #站着的人数
                    elif self.is_standing(keypoints):
                        stand_count += 1

                    for keypoint in keypoints:  # loop over keypoints
                        x, y, conf = keypoint
                        if conf > 0.5:  # draw keypoints with confidence greater than 0.5
                            cv2.circle(operated_frame, (int(x.item()), int(y.item())), 3, (0, 0, 255), -1)

                    # Draw lines connecting keypoints
                    for pair in self.POSE_PAIRS:
                        pt1, pt2 = keypoints[pair[0]][:2], keypoints[pair[1]][:2]
                        conf1, conf2 = keypoints[pair[0]][2], keypoints[pair[1]][2]
                        if conf1 > 0.5 and conf2 > 0.5:
                            # cv2.line(operated_frame, (int(pt1[0].item()), int(pt1[1].item())), (int(pt2[0].item()), int(pt2[1].item())), (255, 255, 0), 2)
                            pass
            self.person_count = person_count
            self.sit_count = sit_count
            self.stand_count = stand_count
            cv2.imshow("YOLO v8 Fay Eyes", operated_frame)
            cv2.waitKey(1)

         cap.release()
         cv2.destroyAllWindows()


def new_instance():
    global __fei_eyes
    if __fei_eyes is None:
        __fei_eyes = FeiEyes()
    return __fei_eyes


        

