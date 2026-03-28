from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import os
import cv2
import tempfile

from scenedetect import VideoManager, SceneManager, ContentDetector, FrameTimecode


@dataclass
class Keyframe:
    timestamp: float
    frame_idx: int
    scene_len: int
    frame_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "frame_idx": self.frame_idx,
            "scene_len": self.scene_len,
            "frame_path": self.frame_path,
        }


class KeyframeExtractor:
    def __init__(
        self,
        threshold: float = 30.0,
        min_scene_len: int = 15,
        luma_only: bool = False,
    ):
        self.threshold = threshold
        self.min_scene_len = min_scene_len
        self.luma_only = luma_only

    def detect_scenes(
        self,
        video_path: str,
        save_frames: bool = True,
        output_dir: Optional[str] = None,
    ) -> List[Keyframe]:
        video_manager = VideoManager(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(
            ContentDetector(
                threshold=self.threshold,
                min_scene_len=self.min_scene_len,
                luma_only=self.luma_only,
            )
        )

        video_manager.set_downscale_factor()
        video_manager.start()

        scene_manager.detect_scenes(video_manager)

        scene_list = scene_manager.get_scene_list()
        fps = video_manager.get_framerate()

        keyframes: List[Keyframe] = []

        for i, scene in enumerate(scene_list):
            start_frame = scene[0].frame_num
            end_frame = scene[1].frame_num
            timestamp = float(start_frame) / float(fps)
            scene_len = end_frame - start_frame

            frame_path: Optional[str] = None
            if save_frames:
                frame_path = self._extract_frame_at(
                    video_path, start_frame, fps, output_dir, i
                )

            keyframes.append(Keyframe(
                timestamp=timestamp,
                frame_idx=start_frame,
                scene_len=scene_len,
                frame_path=frame_path,
            ))

        video_manager.release()
        return keyframes

    def _extract_frame_at(
        self,
        video_path: str,
        frame_num: int,
        fps: float,
        output_dir: Optional[str],
        index: int,
    ) -> Optional[str]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None

        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            return None

        if output_dir is None:
            output_dir = tempfile.mkdtemp()

        frame_path = os.path.join(output_dir, f"keyframe_{index:04d}.jpg")
        cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return frame_path

    def detect_scenes_fast(
        self,
        video_path: str,
        num_keyframes: int = 20,
    ) -> List[Keyframe]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps

        interval = max(1, total_frames // num_keyframes)

        cap.release()

        video_manager = VideoManager(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(
            ContentDetector(
                threshold=self.threshold,
                min_scene_len=self.min_scene_len,
                luma_only=self.luma_only,
            )
        )

        video_manager.set_downscale_factor()
        video_manager.start()
        scene_manager.detect_scenes(video_manager)
        scene_list = scene_manager.get_scene_list()
        video_manager.release()

        if not scene_list:
            return self._uniform_keyframes(video_path, num_keyframes)

        fps_val = video_manager.get_framerate()

        keyframes: List[Keyframe] = []
        for i, scene in enumerate(scene_list[:num_keyframes]):
            start_frame = scene[0].frame_num
            timestamp = float(start_frame) / float(fps_val)
            end_frame = scene[1].frame_num
            keyframes.append(Keyframe(
                timestamp=timestamp,
                frame_idx=start_frame,
                scene_len=end_frame - start_frame,
            ))

        return keyframes

    def _uniform_keyframes(
        self, video_path: str, num_keyframes: int
    ) -> List[Keyframe]:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

        interval = total_frames / num_keyframes
        keyframes = []
        for i in range(num_keyframes):
            frame_idx = int(i * interval)
            timestamp = frame_idx / fps
            keyframes.append(Keyframe(
                timestamp=timestamp,
                frame_idx=frame_idx,
                scene_len=0,
            ))
        return keyframes


def get_keyframe_extractor(
    threshold: float = 30.0,
    min_scene_len: int = 15,
) -> KeyframeExtractor:
    return KeyframeExtractor(threshold=threshold, min_scene_len=min_scene_len)
