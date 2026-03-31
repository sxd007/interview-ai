import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 600000,
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export interface Interview {
  id: string
  filename: string
  duration?: number
  fps?: number
  resolution?: string
  status: 'pending' | 'queued' | 'processing' | 'completed' | 'failed'
  error_message?: string
  created_at: string
  updated_at: string
  chunk_duration?: number
  chunk_count?: number
  is_chunked?: boolean
  video_url?: string
}

export interface VideoChunk {
  id: string
  interview_id: string
  chunk_index: number
  file_path: string
  global_start: number
  global_end: number
  status: 'pending' | 'processing' | 'review_pending' | 'review_completed' | 'failed'
  audio_path?: string
  error_message?: string
  created_at?: string
  review_pending_at?: string
  reviewed_at?: string
  approved_by?: string
}

export interface Speaker {
  id: string
  label: string
  color?: string
}

export interface Segment {
  id: string
  speaker_id?: string
  speaker_label?: string
  start_time: number
  end_time: number
  transcript?: string
  confidence?: number
  prosody?: Prosody
  emotion_scores?: Record<string, number | string>
  lang?: string
  event?: string
}

export interface Prosody {
  pitch_mean?: number
  pitch_std?: number
  pitch_min?: number
  pitch_max?: number
  pitch_range?: number
  energy_mean?: number
  energy_std?: number
  energy_range?: number
  speech_rate?: number
  pause_ratio?: number
  filler_count?: number
}

export interface EmotionNode {
  id: string
  timestamp: number
  source: 'audio' | 'video' | 'fusion'
  label: string
  intensity: number
  confidence: number
}

export interface FaceFrame {
  id: string
  timestamp: number
  frame_path?: string
  face_bbox?: number[]
  action_units?: Record<string, number>
  emotion_scores?: Record<string, number>
}

export interface Keyframe {
  id: string
  timestamp: number
  frame_idx: number
  scene_len?: number
  frame_path?: string
}

export interface EmotionSummary {
  dominant_emotion: string
  emotion_distribution: Record<string, number>
  stress_signals: number
  avoidance_signals: number
  confidence_score: number
}

export interface SignalItem {
  timestamp: number
  type: string
  intensity: number
  indicator: string
}

export interface EmotionAnalysis {
  interview_id: string
  emotion_nodes: EmotionNode[]
  summary: EmotionSummary
  signals: SignalItem[]
}

export interface Timeline {
  interview_id: string
  duration: number
  speakers: Speaker[]
  segments: Segment[]
  keyframes: Keyframe[]
  face_frames: FaceFrame[]
  emotion_nodes: EmotionNode[]
}

export interface Report {
  interview_id: string
  metadata: Record<string, unknown>
  transcript: string
  emotion_summary: Record<string, unknown>
  signals: Record<string, unknown>[]
  key_moments: Record<string, unknown>[]
}

export interface ProcessConfig {
  video_analysis?: boolean
  face_analysis?: boolean
  audio_denoise?: boolean
  speaker_diarization?: boolean
  speech_to_text?: boolean
  prosody_analysis?: boolean
  emotion_recognition?: boolean
  multimodal_fusion?: boolean
  stt_model?: string
  stt_engine?: 'faster-whisper' | 'sensevoice'
  diarization_engine?: 'pyannote' | 'funasr'
  chunk_enabled?: boolean
  chunk_duration?: number
}

export const interviewApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    api.get<{ total: number; interviews: Interview[] }>('/interviews', { params }),

  get: (id: string) =>
    api.get<Interview>(`/interviews/${id}`),

  upload: async (file: File, onProgress?: (progress: number) => void) => {
    const formData = new FormData()
    formData.append('file', file)

    return api.post<Interview>('/interviews', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded * 100) / e.total))
        }
      },
    })
  },

  delete: (id: string) =>
    api.delete(`/interviews/${id}`),

  getStatus: (id: string) =>
    api.get(`/interviews/${id}/status`),

  process: (id: string, config?: ProcessConfig) =>
    api.post(`/interviews/${id}/process`, config),

  getProgress: (id: string) =>
    api.get(`/interviews/${id}/progress`),
}

export const transcriptApi = {
  get: (id: string) =>
    api.get<{
      interview_id: string
      speakers: Speaker[]
      segments: Segment[]
      full_text: string
    }>(`/interviews/${id}/transcript`),
}

export const emotionApi = {
  get: (id: string) =>
    api.get<EmotionAnalysis>(`/interviews/${id}/emotion`),
}

export const timelineApi = {
  get: (id: string) =>
    api.get<Timeline>(`/interviews/${id}/timeline`),
}

export const keyframesApi = {
  get: (id: string) =>
    api.get<Keyframe[]>(`/interviews/${id}/keyframes`),
}

export const reportApi = {
  get: (id: string) =>
    api.get<Report>(`/interviews/${id}/report`),

  download: (id: string) => {
    return api.get(`/interviews/${id}/report/download`, {
      responseType: 'blob',
    })
  },
}

export interface FusionSummary {
  speaker_id: string
  speaker_label: string
  speaker_color: string
  segment_count: number
  total_duration: number
  prosody: {
    pitch_mean: number
    pitch_std: number
    speech_rate: number
    pause_ratio: number
    filler_count: number
  }
  emotion: {
    dominant_emotion: string
    emotion_counts: Record<string, number>
    segment_count: number
  }
}

export interface FusionAnalysis {
  speaker_summaries: FusionSummary[]
  interview_summary: {
    total_segments: number
    total_face_frames: number
    speaker_count: number
  }
}

export interface PipelineStage {
  id: string
  name: string
  label: string
  label_en: string
  description: string
  status: string
  progress: number
  depends_on: string[]
  affects: string[]
  started_at?: string
  completed_at?: string
  error_message?: string
  result_summary?: Record<string, unknown>
}

export const pipelineApi = {
  runStage: (id: string, stageName: string) =>
    api.post(`/interviews/${id}/pipeline/${stageName}/run`),

  getFusion: (id: string) =>
    api.get<FusionAnalysis>(`/interviews/${id}/analysis/fusion`),

  getStages: (id: string) =>
    api.get<{ stages: PipelineStage[] }>(`/interviews/${id}/pipeline`),

  mergeSpeakers: (id: string) =>
    api.post<{ success: boolean; merged_groups: number; speakers_merged: number }>(
      `/interviews/${id}/pipeline/merge-speakers`
    ),

  getMergeStatus: (id: string) =>
    api.get<{ is_merged: boolean; merged_count: number }>(
      `/interviews/${id}/pipeline/merge-status`
    ),
}

export interface VoicePrintProfile {
  id: string
  name: string
  description?: string
  embedding?: number[]
  sample_count: number
  status: 'pending' | 'ready' | 'trained'
  created_at: string
  updated_at: string
}

export interface VoicePrintSample {
  id: string
  profile_id: string
  audio_path: string
  duration?: number
  embedding?: number[]
  status: 'pending' | 'completed' | 'failed' | 'skipped'
  error_message?: string
  created_at: string
}

export interface VoicePrintMatch {
  id: string
  profile_id: string
  interview_id?: string
  speaker_id?: string
  speaker_label?: string
  confidence: number
  matched_at: string
}

export const voicePrintApi = {
  createProfile: (data: { name: string; description?: string }) =>
    api.post<VoicePrintProfile>('/voice-prints', data),

  listProfiles: (params?: { skip?: number; limit?: number }) =>
    api.get<VoicePrintProfile[]>('/voice-prints', { params }),

  getProfile: (id: string) =>
    api.get<VoicePrintProfile>(`/voice-prints/${id}`),

  updateProfile: (id: string, data: { name?: string; description?: string }) =>
    api.patch<VoicePrintProfile>(`/voice-prints/${id}`, data),

  deleteProfile: (id: string) =>
    api.delete(`/voice-prints/${id}`),

  addSample: async (profileId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<VoicePrintSample>(`/voice-prints/${profileId}/samples`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  listSamples: (profileId: string) =>
    api.get<VoicePrintSample[]>(`/voice-prints/${profileId}/samples`),

  deleteSample: (sampleId: string) =>
    api.delete(`/voice-prints/samples/${sampleId}`),

  getMatches: (profileId: string, limit?: number) =>
    api.get<VoicePrintMatch[]>(`/voice-prints/${profileId}/matches`, { params: { limit } }),

  matchEmbedding: (embedding: number[], threshold: number = 0.7) =>
    api.post<{ profile_id: string | null; profile_name: string | null; confidence: number }>(
      '/voice-prints/match',
      { embedding: { embedding }, threshold }
    ),
}

export default api
