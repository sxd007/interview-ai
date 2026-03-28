export interface Interview {
  id: string
  filename: string
  duration?: number
  fps?: number
  resolution?: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  error_message?: string
  created_at: string
  updated_at: string
}

export interface Speaker {
  id: string
  label: string
  color?: string
}

export interface AudioSegment {
  id: string
  speaker_id?: string
  start_time: number
  end_time: number
  transcript?: string
  confidence?: number
  prosody?: Prosody
  emotion_scores?: Record<string, number>
}

export interface Prosody {
  pitch_mean?: number
  pitch_std?: number
  energy_mean?: number
  speech_rate?: number
  pause_ratio?: number
}

export interface FaceFrame {
  id: string
  timestamp: number
  frame_path?: string
  face_bbox?: number[]
  action_units?: Record<string, number>
  emotion_scores?: Record<string, number>
}

export interface EmotionNode {
  id: string
  timestamp: number
  source: 'audio' | 'video' | 'fusion'
  label: string
  intensity: number
  confidence: number
}

export interface Signal {
  timestamp: number
  type: string
  intensity: number
  indicator: string
}

export interface EmotionSummary {
  dominant_emotion: string
  emotion_distribution: Record<string, number>
  stress_signals: number
  avoidance_signals: number
  confidence_score: number
}
