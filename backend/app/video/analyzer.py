import cv2
import librosa
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple
from ..models.schemas import VideoAnalysis, EditStyle


class VideoAnalyzer:
    """Analyseur de vidéos pour extraire des infos"""
    
    def __init__(self, max_duration: float = 300):
        self.max_duration = max_duration
    
    async def analyze(self, filepath: str) -> VideoAnalysis:
        """Analyse complète d'une vidéo"""
        
        try:
            # Ouvrir la vidéo
            cap = cv2.VideoCapture(filepath)
            
            # Extraire les infos de base
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            cap.release()
            
            # Analyser l'audio pour détécter les beats
            beats = self._detect_beats(filepath)
            
            # Analyser les transitions
            transitions = self._detect_transitions(filepath)
            
            # Analyser le mouvement
            motion_intensity = self._analyze_motion(filepath)
            
            # Extraire les couleurs dominantes
            colors = self._extract_colors(filepath)
            
            # Suggérer un style
            suggested_style = self._suggest_style(motion_intensity, len(beats), len(transitions))
            
            return VideoAnalysis(
                duration=duration,
                fps=fps,
                resolution=f"{width}x{height}",
                beats=beats,
                transitions=transitions,
                motion_intensity=motion_intensity,
                dominant_colors=colors,
                suggested_style=suggested_style
            )
        
        except Exception as e:
            print(f"❌ Erreur analyse vidéo: {e}")
            # Retourner une analyse par défaut
            return VideoAnalysis(
                duration=0,
                fps=30,
                resolution="1920x1080",
                beats=[],
                transitions=[],
                motion_intensity=0.5,
                dominant_colors=["#CCCCCC"],
                suggested_style=EditStyle.SMOOTH
            )
    
    def _detect_beats(self, filepath: str) -> List[float]:
        """Détecte les beats dans l'audio"""
        
        try:
            # Charger l'audio
            y, sr = librosa.load(filepath, sr=None)
            
            # Détecte les beats
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            beats = librosa.util.peak_pick(
                onset_env,
                pre_max=3, post_max=3,
                pre_avg=3, post_avg=3,
                delta=0.5, wait=10
            )
            
            # Convertir en secondes
            beat_times = librosa.frames_to_time(beats, sr=sr)
            
            return beat_times.tolist()
        
        except Exception as e:
            print(f"⚠️  Erreur détection beats: {e}")
            return []
    
    def _detect_transitions(self, filepath: str) -> List[Dict[str, Any]]:
        """Détecte les transitions (cuts, dissolves)"""
        
        try:
            cap = cv2.VideoCapture(filepath)
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            transitions = []
            prev_frame = None
            frame_idx = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if prev_frame is not None and frame_idx % 10 == 0:  # Tous les 10 frames
                    # Calculer la différence entre frames
                    diff = cv2.absdiff(prev_frame, frame)
                    mean_diff = np.mean(diff)
                    
                    # Si grande différence, c'est une transition
                    if mean_diff > 30:
                        transitions.append({
                            "time": frame_idx / fps,
                            "type": "cut",
                            "intensity": min(mean_diff / 255, 1.0)
                        })
                
                prev_frame = frame if frame_idx % 10 == 0 else prev_frame
                frame_idx += 1
            
            cap.release()
            return transitions[:10]  # Limiter à 10
        
        except Exception as e:
            print(f"⚠️  Erreur détection transitions: {e}")
            return []
    
    def _analyze_motion(self, filepath: str) -> float:
        """Analyse le mouvement général dans la vidéo"""
        
        try:
            cap = cv2.VideoCapture(filepath)
            
            motion_scores = []
            prev_gray = None
            frame_idx = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_idx % 5 == 0:  # Tous les 5 frames
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    
                    if prev_gray is not None:
                        # Calculer le flux optique
                        flow = cv2.calcOpticalFlowFarneback(
                            prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
                        )
                        
                        # Magnitude du mouvement
                        mag = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)
                        motion_scores.append(np.mean(mag))
                    
                    prev_gray = gray
                
                frame_idx += 1
            
            cap.release()
            
            if motion_scores:
                # Normaliser entre 0-1
                avg_motion = np.mean(motion_scores)
                return min(avg_motion / 50, 1.0)
            
            return 0.5
        
        except Exception as e:
            print(f"⚠️  Erreur analyse mouvement: {e}")
            return 0.5
    
    def _extract_colors(self, filepath: str) -> List[str]:
        """Extrait les couleurs dominantes"""
        
        try:
            cap = cv2.VideoCapture(filepath)
            
            colors = []
            frame_idx = 0
            
            while len(colors) < 5:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_idx % 30 == 0:  # Tous les 30 frames
                    # Redimensionner pour accélérer
                    small = cv2.resize(frame, (100, 100))
                    
                    # Extraire la couleur moyenne
                    avg_color = cv2.mean(small)[:3]
                    hex_color = self._rgb_to_hex(avg_color)
                    colors.append(hex_color)
                
                frame_idx += 1
            
            cap.release()
            return colors or ["#CCCCCC"]
        
        except Exception as e:
            print(f"⚠️  Erreur extraction couleurs: {e}")
            return ["#CCCCCC"]
    
    def _rgb_to_hex(self, rgb: Tuple[float, float, float]) -> str:
        """Convertir RGB en hex"""
        b, g, r = rgb  # OpenCV utilise BGR
        return "#{:02X}{:02X}{:02X}".format(int(r), int(g), int(b))
    
    def _suggest_style(self, motion: float, beats: int, transitions: int) -> EditStyle:
        """Suggère un style basé sur l'analyse"""
        
        if motion > 0.7 and beats > 5:
            return EditStyle.GAMING
        elif transitions > 5:
            return EditStyle.AGGRESSIVE
        elif motion < 0.3:
            return EditStyle.SMOOTH
        elif beats > 10:
            return EditStyle.ANIME
        else:
            return EditStyle.CINEMATIC


# Instance globale
video_analyzer = VideoAnalyzer()
