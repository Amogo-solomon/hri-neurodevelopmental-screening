import cv2
import hashlib
import os
import asyncio
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import structlog

logger = structlog.get_logger()

# Try to import MediaPipe for pose detection
try:
    import mediapipe as mp
    try:
        from mediapipe.python.solutions import pose as mp_pose
        HAS_MEDIAPIPE = True
        logger.info("MediaPipe imported successfully (0.10.x)")
    except ImportError:
        try:
            mp_pose = mp.solutions.pose
            HAS_MEDIAPIPE = True
            logger.info("MediaPipe imported successfully (old API)")
        except AttributeError:
            HAS_MEDIAPIPE = False
            logger.warning("MediaPipe import failed - no solutions module")
except ImportError as e:
    HAS_MEDIAPIPE = False
    logger.warning(f"MediaPipe not installed: {e}. Falling back to fixed SoM positions.")

# Try to import YOLO
try:
    from ultralytics import YOLO
    HAS_YOLO = True
    logger.info("YOLO imported successfully")
except ImportError as e:
    HAS_YOLO = False
    logger.warning(f"YOLO not installed: {e}. Using fallback robot detection.")


class VideoProcessor:
    """Handles video ingestion, validation, and frame extraction."""

    SUPPORTED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

    def __init__(self, upload_dir: str):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize MediaPipe Pose if available
        self.pose = None
        if HAS_MEDIAPIPE:
            try:
                self.pose = mp_pose.Pose(
                    static_image_mode=True,
                    model_complexity=1,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                logger.info("MediaPipe Pose initialized successfully")
            except Exception as e:
                logger.warning(f"MediaPipe initialization failed: {e}")
                self.pose = None
        
        # Initialize YOLO for robot detection
        self.yolo_model = None
        self.yolo_initialized = False
        self._init_yolo()

    def _init_yolo(self):
        """Initialize YOLO model for robot detection."""
        if not HAS_YOLO:
            return
        
        try:
            # Load YOLOv8n (nano) or YOLOv8s (small) - you can change to 'yolov8s.pt' for better accuracy
            # The model will be automatically downloaded on first use
            self.yolo_model = YOLO('yolov8n.pt')  # You can also use 'yolov8s.pt', 'yolov8m.pt', etc.
            self.yolo_initialized = True
            logger.info("YOLO initialized successfully")
        except Exception as e:
            logger.warning(f"YOLO initialization failed: {e}. Using fallback robot detection.")
            self.yolo_initialized = False

    def _detect_robot_yolo(self, frame) -> Optional[Tuple[int, int, int, int]]:
        """
        Detect robot using YOLO object detection.
        Returns bbox of detected robot or None.
        """
        if not self.yolo_initialized or self.yolo_model is None:
            return None
        
        try:
            h, w = frame.shape[:2]
            
            # Run YOLO inference
            results = self.yolo_model(frame, verbose=False)
            
            if len(results) == 0:
                return None
            
            # Get detections
            result = results[0]
            boxes = result.boxes
            
            if boxes is None:
                return None
            
            # Look for robot-related objects
            robot_classes = {
                'person': 0,
                'cell phone': 67,
                'tv': 62,
                'remote': 74,
                'keyboard': 76,
                'mouse': 77,
                'laptop': 73,
                'camera': 63,
                'toaster': 70,
                'microwave': 71,
                'clock': 87,
                'vase': 88,
                'scissors': 89,
                'teddy bear': 79,
                'hair drier': 83,
                'toothbrush': 84,
                'sports ball': 32,
                'bottle': 39,
                'cup': 41,
            }
            
            best_box = None
            best_confidence = 0
            
            for box in boxes:
                # Get class ID and confidence
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                
                # Get class name
                class_name = self.yolo_model.names[class_id] if class_id in self.yolo_model.names else ''
                
                # Check if detection is a robot or robot-like object
                is_robot = False
                
                # Check for known robot classes
                if class_name.lower() == 'robot':
                    is_robot = True
                elif class_name.lower() == 'person':
                    # Check if person is on the right side (robot character)
                    x1, y1, x2, y2 = box.xyxy[0]
                    center_x = (x1 + x2) / 2
                    if center_x > w * 0.5:
                        is_robot = True
                elif class_name.lower() in ['cell phone', 'camera', 'laptop', 'tv']:
                    # These could be robot parts
                    if confidence > 0.3:
                        is_robot = True
                
                if is_robot and confidence > 0.3 and confidence > best_confidence:
                    x1, y1, x2, y2 = box.xyxy[0]
                    x = int(x1)
                    y = int(y1)
                    rw = int(x2 - x1)
                    rh = int(y2 - y1)
                    
                    # Add padding
                    padding = 30
                    x = max(0, x - padding)
                    y = max(0, y - padding)
                    rw = min(w - x, rw + padding * 2)
                    rh = min(h - y, rh + padding * 2)
                    
                    best_box = (x, y, rw, rh)
                    best_confidence = confidence
            
            if best_box:
                logger.debug(f"Robot detected at {best_box} with confidence {best_confidence:.2f}")
                return best_box
            
            return None
            
        except Exception as e:
            logger.debug(f"YOLO detection error: {e}")
            return None

    def _detect_robot_color(self, frame) -> Optional[Tuple[int, int, int, int]]:
        """
        Fallback: Detect robot using color detection.
        """
        h, w = frame.shape[:2]
        
        try:
            # Convert to HSV
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Define color ranges for robot detection
            # ADJUST THESE VALUES BASED ON YOUR ROBOT'S COLOR!
            color_ranges = [
                # Red range 1
                (np.array([0, 50, 50]), np.array([10, 255, 255])),
                # Red range 2
                (np.array([170, 50, 50]), np.array([180, 255, 255])),
                # Blue (for robots with blue accents)
                (np.array([100, 50, 50]), np.array([130, 255, 255])),
                # Orange (common robot color)
                (np.array([10, 50, 50]), np.array([20, 255, 255])),
            ]
            
            masks = []
            for lower, upper in color_ranges:
                masks.append(cv2.inRange(hsv, lower, upper))
            
            # Combine all masks
            mask = np.zeros_like(masks[0])
            for m in masks:
                mask = cv2.bitwise_or(mask, m)
            
            # Apply morphology to clean up
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            
            # Find contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Filter contours by size
                min_area = (w * h) * 0.01  # At least 1% of frame
                valid_contours = [c for c in contours if cv2.contourArea(c) > min_area]
                
                if valid_contours:
                    # Get the largest valid contour
                    largest = max(valid_contours, key=cv2.contourArea)
                    x, y, rw, rh = cv2.boundingRect(largest)
                    padding = 30
                    return (max(0, x - padding), max(0, y - padding),
                            min(w - x, rw + padding*2), min(h - y, rh + padding*2))
            
            return None
            
        except Exception as e:
            logger.debug(f"Color detection error: {e}")
            return None

    def _detect_robot(self, frame) -> Tuple[int, int, int, int]:
        """
        Detect robot using multiple methods.
        Priority: YOLO > Color Detection > Fixed Position
        """
        h, w = frame.shape[:2]
        
        # Method 1: YOLO detection
        robot_box = self._detect_robot_yolo(frame)
        if robot_box is not None:
            logger.debug("Robot detected using YOLO")
            return robot_box
        
        # Method 2: Color detection (fallback)
        robot_box = self._detect_robot_color(frame)
        if robot_box is not None:
            logger.debug("Robot detected using color detection")
            return robot_box
        
        # Method 3: Fixed position (last resort)
        logger.debug("No robot detected, using fixed position")
        return (int(w*0.60), int(h*0.10), int(w*0.35), int(h*0.70))

    def validate_video(self, filepath: str) -> dict:
        """Extract metadata from video file."""
        cap = cv2.VideoCapture(filepath)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {filepath}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        duration = frame_count / fps if frame_count > 0 else 0

        if duration == 0:
            cap.set(cv2.CAP_PROP_POS_AVI_RATIO, 1)
            duration = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        if duration == 0:
            file_size = os.path.getsize(filepath)
            duration = (file_size * 8) / (4 * 1_000_000)
            logger.warning(
                "duration_estimated_from_filesize",
                filepath=filepath,
                estimated_seconds=round(duration, 1),
            )

        cap.release()

        logger.info(
            "video_validated",
            filepath=Path(filepath).name,
            fps=fps,
            frame_count=frame_count,
            duration_s=round(duration, 1),
            resolution=f"{width}x{height}",
        )

        return {
            "fps": fps,
            "frame_count": frame_count,
            "width": width,
            "height": height,
            "duration_seconds": duration,
        }

    def compute_sha256(self, filepath: str) -> str:
        """SHA-256 checksum for data integrity (NHS DSP Toolkit compliance)."""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def extract_frames(
        self,
        filepath: str,
        target_fps: float = 1.0,
        max_frames: int = 5,
        resize_width: int = 640,
    ) -> List[Tuple[float, str]]:
        """Extract up to max_frames frames evenly-spaced across the video."""
        video_id = Path(filepath).stem
        frames_dir = self.upload_dir / "frames" / video_id
        frames_dir.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(filepath)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {filepath}")

        native_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        extracted = []

        if total_frames > 0:
            n_to_sample = min(max_frames, total_frames)
            if n_to_sample <= 1:
                target_indices = [0]
            else:
                step = total_frames / n_to_sample
                target_indices = [int(i * step) for i in range(n_to_sample)]

            logger.info(
                "extracting_frames_even_spread",
                video=Path(filepath).name,
                total_frames=total_frames,
                sampling=n_to_sample,
            )

            for saved, frame_idx in enumerate(target_indices):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, min(frame_idx + 1, total_frames - 1))
                    ret, frame = cap.read()
                if not ret:
                    continue

                frame = self._resize(frame, resize_width)
                timestamp = frame_idx / native_fps
                frame_path = str(frames_dir / f"frame_{saved:04d}_{timestamp:.2f}s.jpg")
                cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                extracted.append((timestamp, frame_path))

        else:
            interval = max(1, int(native_fps / target_fps))
            frame_idx = 0
            saved = 0

            logger.warning(
                "extracting_frames_interval_fallback",
                video=Path(filepath).name,
                interval=interval,
            )

            while cap.isOpened() and saved < max_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % interval == 0:
                    frame = self._resize(frame, resize_width)
                    timestamp = frame_idx / native_fps
                    frame_path = str(frames_dir / f"frame_{saved:04d}_{timestamp:.2f}s.jpg")
                    cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    extracted.append((timestamp, frame_path))
                    saved += 1
                frame_idx += 1

        cap.release()
        logger.info("frames_extracted", video_id=video_id, count=len(extracted))
        return extracted

    def _resize(self, frame, max_width: int):
        """Resize frame to max_width keeping aspect ratio."""
        h, w = frame.shape[:2]
        if w > max_width:
            ratio = max_width / w
            frame = cv2.resize(frame, (max_width, int(h * ratio)))
        return frame

    def _detect_pose(self, frame) -> Optional[Dict]:
        """Detect pose landmarks using MediaPipe."""
        if self.pose is None:
            return None

        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.pose.process(rgb_frame)
            if results.pose_landmarks:
                return results
            return None
        except Exception as e:
            logger.debug(f"pose_detection_failed: {e}")
            return None

    def _get_keypoint(self, landmarks, idx: int, h: int, w: int) -> Tuple[int, int]:
        """Convert normalized keypoint to pixel coordinates."""
        if idx >= len(landmarks.landmark):
            return None, None
        kp = landmarks.landmark[idx]
        return int(kp.x * w), int(kp.y * h)

    def apply_som_marks(self, frame_path: str, frame_idx: int) -> Tuple[str, dict]:
        """
        Apply Set-of-Mark (SoM) visual prompting overlay.
        
        ULTRA MINIMALIST design - NO backgrounds, NO overlays:
        - NO black backgrounds
        - NO semi-transparent fills
        - Just thin coloured borders (1px)
        - Just small text (no background boxes)
        - White text outline for readability on any background
        """
        frame = cv2.imread(frame_path)
        if frame is None:
            return frame_path, {}

        h, w = frame.shape[:2]

        # ── Detect robot FIRST ──────────────────────────────────────────────────
        robot_box = self._detect_robot(frame)

        # ── Try to detect pose ──────────────────────────────────────────────────
        results = self._detect_pose(frame)
        
        if results:
            # ── Data-Driven SoM: Use detected landmarks ──────────────────────
            logger.debug(f"using_pose_based_som", frame=Path(frame_path).name)
            
            landmarks = results.pose_landmarks
            
            # Keypoint indices for MediaPipe
            NOSE = 0
            LEFT_EYE = 1
            RIGHT_EYE = 2
            LEFT_SHOULDER = 11
            RIGHT_SHOULDER = 12
            LEFT_ELBOW = 13
            RIGHT_ELBOW = 14
            LEFT_WRIST = 15
            RIGHT_WRIST = 16
            LEFT_HIP = 23
            RIGHT_HIP = 24
            
            # Get keypoint positions
            nose_x, nose_y = self._get_keypoint(landmarks, NOSE, h, w)
            left_eye_x, left_eye_y = self._get_keypoint(landmarks, LEFT_EYE, h, w)
            right_eye_x, right_eye_y = self._get_keypoint(landmarks, RIGHT_EYE, h, w)
            l_shoulder_x, l_shoulder_y = self._get_keypoint(landmarks, LEFT_SHOULDER, h, w)
            r_shoulder_x, r_shoulder_y = self._get_keypoint(landmarks, RIGHT_SHOULDER, h, w)
            l_elbow_x, l_elbow_y = self._get_keypoint(landmarks, LEFT_ELBOW, h, w)
            r_elbow_x, r_elbow_y = self._get_keypoint(landmarks, RIGHT_ELBOW, h, w)
            l_wrist_x, l_wrist_y = self._get_keypoint(landmarks, LEFT_WRIST, h, w)
            r_wrist_x, r_wrist_y = self._get_keypoint(landmarks, RIGHT_WRIST, h, w)
            l_hip_x, l_hip_y = self._get_keypoint(landmarks, LEFT_HIP, h, w)
            r_hip_x, r_hip_y = self._get_keypoint(landmarks, RIGHT_HIP, h, w)
            
            # ── Build SoM regions from detections ─────────────────────────────
            som_regions = []
            
            # Region 1: Face/Gaze (around nose and eyes)
            face_points = [(nose_x, nose_y), (left_eye_x, left_eye_y), (right_eye_x, right_eye_y)]
            face_points = [p for p in face_points if p[0] is not None and p[1] is not None]
            if face_points:
                face_x = min(p[0] for p in face_points) - 15
                face_y = min(p[1] for p in face_points) - 20
                face_w = max(p[0] for p in face_points) - min(p[0] for p in face_points) + 30
                face_h = max(p[1] for p in face_points) - min(p[1] for p in face_points) + 40
                face_w = max(face_w, 50)
                face_h = max(face_h, 60)
            else:
                face_x, face_y, face_w, face_h = int(w*0.25), int(h*0.10), int(w*0.25), int(h*0.25)
            
            # Region 2: Left Hand (around left wrist)
            if l_wrist_x is not None and l_wrist_y is not None:
                left_hand_box = (l_wrist_x - 20, l_wrist_y - 20, 40, 40)
            else:
                left_hand_box = (int(w*0.15), int(h*0.50), int(w*0.15), int(h*0.15))
            
            # Region 3: Right Hand (around right wrist)
            if r_wrist_x is not None and r_wrist_y is not None:
                right_hand_box = (r_wrist_x - 20, r_wrist_y - 20, 40, 40)
            else:
                right_hand_box = (int(w*0.55), int(h*0.50), int(w*0.15), int(h*0.15))
            
            # Region 4: Torso/Posture (between shoulders and hips)
            torso_points = [(l_shoulder_x, l_shoulder_y), (r_shoulder_x, r_shoulder_y),
                          (l_hip_x, l_hip_y), (r_hip_x, r_hip_y)]
            torso_points = [p for p in torso_points if p[0] is not None and p[1] is not None]
            if torso_points:
                torso_x = min(p[0] for p in torso_points) - 10
                torso_y = min(p[1] for p in torso_points) - 10
                torso_w = max(p[0] for p in torso_points) - min(p[0] for p in torso_points) + 20
                torso_h = max(p[1] for p in torso_points) - min(p[1] for p in torso_points) + 20
                torso_w = max(torso_w, 60)
                torso_h = max(torso_h, 80)
            else:
                torso_x, torso_y, torso_w, torso_h = int(w*0.20), int(h*0.30), int(w*0.30), int(h*0.35)
            
            # Region 5: Robot Zone
            # robot_box is already detected at the start of this method
            
            som_regions = [
                {"id": 1, "label": "Face/Gaze", "bbox": (face_x, face_y, face_w, face_h)},
                {"id": 2, "label": "Left Hand", "bbox": left_hand_box},
                {"id": 3, "label": "Right Hand", "bbox": right_hand_box},
                {"id": 4, "label": "Torso/Posture", "bbox": (torso_x, torso_y, torso_w, torso_h)},
                {"id": 5, "label": "Robot Zone", "bbox": robot_box},
            ]
            
        else:
            # ── Fallback: Fixed SoM positions ─────────────────────────────────
            logger.debug(f"using_fixed_som_fallback", frame=Path(frame_path).name)
            
            som_regions = [
                {"id": 1, "label": "Face/Gaze", "bbox": (int(w*0.25), int(h*0.10), int(w*0.25), int(h*0.25))},
                {"id": 2, "label": "Left Hand", "bbox": (int(w*0.15), int(h*0.45), int(w*0.15), int(h*0.20))},
                {"id": 3, "label": "Right Hand", "bbox": (int(w*0.55), int(h*0.45), int(w*0.15), int(h*0.20))},
                {"id": 4, "label": "Torso/Posture", "bbox": (int(w*0.20), int(h*0.30), int(w*0.30), int(h*0.35))},
                {"id": 5, "label": "Robot Zone", "bbox": robot_box},
            ]

        # ── Draw the SoM regions - MINIMALIST: NO BACKGROUNDS ────────────────
        colours = {
            1: (0, 100, 255),    # Orange - Face
            2: (0, 200, 100),    # Green - Left Hand
            3: (100, 200, 0),    # Yellow-green - Right Hand
            4: (255, 100, 0),    # Blue - Torso
            5: (200, 0, 200),    # Purple - Robot
        }

        # ── ONLY thin borders + small text - NO overlays, NO backgrounds ──
        region_map = {}
        for r in som_regions:
            rid = r["id"]
            x, y, rw, rh = r["bbox"]
            c = colours[rid]
            
            # ONLY thin border (1px) - NO fill, NO overlay
            cv2.rectangle(frame, (x, y), (x + rw, y + rh), c, 1)
            
            # ── Place label OUTSIDE the box - NO BACKGROUND ──────────────────
            label_y = y - 8  # Position ABOVE the box
            
            # If label would go off-screen, place it inside with small text
            if label_y < 5:
                label_y = y + 5
                # Small number inside (NO background)
                cv2.putText(frame, str(rid), (x + 4, y + 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, c, 1)
                # Small label inside (NO background)
                cv2.putText(frame, r["label"][:3], (x + 18, y + 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, c, 1)
            else:
                # Label above the box - NO BACKGROUND, just text
                # Number with white outline for readability on any background
                cv2.putText(frame, str(rid), (x + 2, y - 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)  # White outline
                cv2.putText(frame, str(rid), (x + 2, y - 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, c, 1)  # Color on top
                
                # Label text above the box - NO BACKGROUND
                cv2.putText(frame, r["label"], (x + 18, y - 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)  # White outline
                cv2.putText(frame, r["label"], (x + 18, y - 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, c, 1)  # Color on top
            
            region_map[rid] = r["label"]

        # Save the SoM frame
        som_path = frame_path.replace(".jpg", "_som.jpg")
        cv2.imwrite(som_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        
        return som_path, region_map

    def cleanup_frames(self, video_id: str):
        """Remove extracted frames after analysis (GDPR data minimisation)."""
        frames_dir = self.upload_dir / "frames" / video_id
        if frames_dir.exists():
            import shutil
            shutil.rmtree(frames_dir, ignore_errors=True)