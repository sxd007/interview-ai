import { useState, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Card, Typography, Space, Spin, Tag, Button, Divider, Slider, Row, Col, Empty } from 'antd'
import { PlayCircleOutlined, PauseCircleOutlined, StepBackwardOutlined, StepForwardOutlined, ClockCircleOutlined, TeamOutlined } from '@ant-design/icons'
import { interviewApi, transcriptApi, pipelineApi } from '../services/api'

const { Text } = Typography

const formatTime = (seconds: number) => {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

const emotionColor = (emotion: string) => {
  const map: Record<string, string> = { happy: 'green', neutral: 'default', sad: 'blue', angry: 'red', fearful: 'purple', disgusted: 'volcano', surprised: 'cyan', unknown: 'default' }
  return map[emotion] || 'default'
}

interface Segment { id: string; speaker_id?: string; speaker_label?: string; start_time: number; end_time: number; transcript?: string; prosody?: any; emotion_scores?: any }
interface Speaker { id: string; label: string; color?: string }
interface FusionSummary { speaker_id: string; speaker_label: string; speaker_color: string; segment_count: number; total_duration: number; prosody: any; emotion: any }

export function InterviewPlayerPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const videoRef = useRef<HTMLVideoElement>(null)
  const timelineRef = useRef<HTMLDivElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [timelineWidth, setTimelineWidth] = useState(0)
  const [activeSegmentId, setActiveSegmentId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('transcript')

  const { data: interviewData, isLoading: interviewLoading } = useQuery({ queryKey: ['interview', id], queryFn: () => interviewApi.get(id!), enabled: !!id })
  const { data: transcriptData, isLoading: transcriptLoading } = useQuery({ queryKey: ['transcript', id], queryFn: () => transcriptApi.get(id!), enabled: !!id })
  const { data: fusionData } = useQuery({ queryKey: ['fusion', id], queryFn: () => pipelineApi.getFusion(id!), enabled: !!id })

  const interview = interviewData?.data
  const speakers: Speaker[] = transcriptData?.data?.speakers || []
  const segments: Segment[] = transcriptData?.data?.segments || []
  const fusionSummaries: FusionSummary[] = fusionData?.data?.speaker_summaries || []

  useEffect(() => {
    if (segments.length > 0 && currentTime > 0) {
      const active = segments.find(seg => currentTime >= seg.start_time && currentTime < seg.end_time)
      if (active && active.id !== activeSegmentId) setActiveSegmentId(active.id)
    }
  }, [currentTime, segments])

  useEffect(() => {
    const updateWidth = () => {
      if (timelineRef.current) {
        const timelineEl = timelineRef.current.querySelector('[data-timeline]') as HTMLElement
        if (timelineEl) setTimelineWidth(timelineEl.offsetWidth)
      }
    }
    updateWidth()
    window.addEventListener('resize', updateWidth)
    return () => window.removeEventListener('resize', updateWidth)
  }, [speakers, activeTab])

  const indicatorLeft = timelineWidth > 0 ? 90 + (currentTime / (duration || 1)) * timelineWidth : 0

  const handleTimeUpdate = () => { if (videoRef.current) setCurrentTime(videoRef.current.currentTime) }
  const handleLoadedMetadata = () => { if (videoRef.current) setDuration(videoRef.current.duration) }
  const handlePlayPause = () => { if (videoRef.current) { isPlaying ? videoRef.current.pause() : videoRef.current.play(); setIsPlaying(!isPlaying) } }
  const handleSeek = (value: number) => { if (videoRef.current) { videoRef.current.currentTime = value; setCurrentTime(value) } }
  const handleSkip = (seconds: number) => { if (videoRef.current) { const newTime = Math.max(0, Math.min(duration, videoRef.current.currentTime + seconds)); videoRef.current.currentTime = newTime; setCurrentTime(newTime) } }
  const handleSegmentClick = (segment: Segment) => { if (videoRef.current) { videoRef.current.currentTime = segment.start_time; setCurrentTime(segment.start_time); videoRef.current.play(); setIsPlaying(true) } }

  if (interviewLoading || transcriptLoading) return <div style={{ textAlign: 'center', marginTop: 100 }}><Spin size="large" /><Text type="secondary" style={{ display: 'block', marginTop: 16 }}>加载中...</Text></div>
  if (!interview) return <Empty description="访谈不存在"><Button type="primary" onClick={() => navigate('/interviews')}>返回列表</Button></Empty>

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ padding: '12px 24px', borderBottom: '1px solid #f0f0f0', background: '#fff' }}>
        <Space><Button onClick={() => navigate(`/interviews/${id}`)}>← 返回详情</Button><Text strong>{interview.filename}</Text><Tag color="green">完成</Tag></Space>
      </div>

      <Card bodyStyle={{ padding: 0 }}>
        <div style={{ position: 'relative', background: '#000' }}>
          {interview.video_url ? <video ref={videoRef} src={interview.video_url} style={{ width: '100%', maxHeight: '40vh', display: 'block' }} onTimeUpdate={handleTimeUpdate} onLoadedMetadata={handleLoadedMetadata} onPlay={() => setIsPlaying(true)} onPause={() => setIsPlaying(false)} onEnded={() => setIsPlaying(false)} /> : <div style={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#000' }}><Text style={{ color: '#fff' }}>视频不可用</Text></div>}
        </div>
        <div style={{ padding: '8px 16px', background: '#fafafa' }}>
          <Slider min={0} max={duration || 100} value={currentTime} onChange={handleSeek} tipFormatter={(v) => formatTime(v || 0)} />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Space><Button type="text" icon={<StepBackwardOutlined />} onClick={() => handleSkip(-10)} /><Button type="primary" shape="circle" icon={isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />} onClick={handlePlayPause} size="large" /><Button type="text" icon={<StepForwardOutlined />} onClick={() => handleSkip(10)} /><Text type="secondary">{formatTime(currentTime)} / {formatTime(duration)}</Text></Space>
            <Space><Tag icon={<TeamOutlined />}>{speakers.length} 说话人</Tag><Tag icon={<ClockCircleOutlined />}>{segments.length} 段落</Tag></Space>
          </div>
        </div>
      </Card>

      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '0 24px', borderBottom: '1px solid #f0f0f0' }}>
          <Space size="middle">
            {[{ key: 'transcript', label: '转录文本' }, { key: 'timeline', label: '时间轴' }, { key: 'analysis', label: '分析结果' }].map(tab => (
              <div key={tab.key} onClick={() => setActiveTab(tab.key)} style={{ padding: '12px 0', cursor: 'pointer', borderBottom: activeTab === tab.key ? '2px solid #1890ff' : '2px solid transparent', color: activeTab === tab.key ? '#1890ff' : '#666' }}>{tab.label}</div>
            ))}
          </Space>
        </div>
        <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
          {activeTab === 'transcript' && <div>{segments.map(seg => { const speaker = speakers.find(s => s.id === seg.speaker_id); const isActive = seg.id === activeSegmentId; return <div key={seg.id} onClick={() => handleSegmentClick(seg)} style={{ padding: '8px 12px', marginBottom: 8, borderRadius: 4, background: isActive ? '#e6f7ff' : '#fafafa', border: isActive ? '1px solid #1890ff' : '1px solid #f0f0f0', cursor: 'pointer' }}><Space><Text type="secondary" style={{ fontSize: 12 }}>{formatTime(seg.start_time)}</Text><Tag color={speaker?.color || 'default'}>{seg.speaker_label || speaker?.label || '未知'}</Tag>{seg.emotion_scores?.dominant_emotion && <Tag color={emotionColor(seg.emotion_scores.dominant_emotion)}>{seg.emotion_scores.dominant_emotion}</Tag>}</Space><div style={{ marginTop: 4 }}><Text>{seg.transcript || '(无转录)'}</Text></div></div> })}</div>}

          {activeTab === 'timeline' && (
            <div ref={timelineRef} style={{ position: 'relative' }}>
              {speakers.map((speaker, idx) => {
                const speakerSegments = segments.filter(s => s.speaker_id === speaker.id)
                const totalTime = speakerSegments.reduce((acc, s) => acc + (s.end_time - s.start_time), 0)
                const isCurrentSpeaker = speakerSegments.some(seg => currentTime >= seg.start_time && currentTime < seg.end_time)
                return (
                  <div key={speaker.id} style={{ display: 'flex', alignItems: 'center', background: isCurrentSpeaker ? '#fff1f0' : (idx % 2 === 0 ? '#fafafa' : '#f5f5f5'), borderBottom: '1px solid #e8e8e8' }}>
                    <div style={{ width: 90, padding: '4px 8px', flexShrink: 0 }}><Space size={4}><div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: speaker.color }} /><Text ellipsis style={{ fontSize: 11 }}>{speaker.label}</Text></Space></div>
                    <div data-timeline style={{ flex: 1, height: 24, position: 'relative', cursor: 'pointer' }} onClick={(e) => { const rect = e.currentTarget.getBoundingClientRect(); const ratio = (e.clientX - rect.left) / rect.width; const seekTime = ratio * duration; if (videoRef.current) { videoRef.current.currentTime = seekTime; setCurrentTime(seekTime) } }}>
                      {[0, 0.25, 0.5, 0.75, 1].map(r => <div key={r} style={{ position: 'absolute', left: `${r * 100}%`, top: 0, bottom: 0, width: 1, background: '#e0e0e0' }} />)}
                      {speakerSegments.map(seg => { const left = duration > 0 ? (seg.start_time / duration) * 100 : 0; const width = duration > 0 ? ((seg.end_time - seg.start_time) / duration) * 100 : 0; const isActive = seg.id === activeSegmentId; return <div key={seg.id} onClick={(e) => { e.stopPropagation(); handleSegmentClick(seg) }} style={{ position: 'absolute', left: `${left}%`, width: `${width}%`, height: '100%', backgroundColor: speaker.color, opacity: isActive ? 1 : 0.7 }} /> })}
                    </div>
                    <div style={{ width: 50, textAlign: 'right', padding: '0 8px' }}><Text type="secondary" style={{ fontSize: 10 }}>{formatTime(totalTime)}</Text></div>
                  </div>
                )
              })}
              <div style={{ display: 'flex', alignItems: 'center', padding: '4px 0', borderTop: '2px solid #1890ff' }}>
                <div style={{ width: 90, padding: '0 8px' }}><Text type="secondary" style={{ fontSize: 10 }}>时间刻度</Text></div>
                <div style={{ flex: 1, position: 'relative', height: 16 }}>
                  {[0, 0.25, 0.5, 0.75].map(r => <div key={r} style={{ position: 'absolute', left: `${r * 100}%`, transform: 'translateX(-50%)', top: 0 }}><Text type="secondary" style={{ fontSize: 10 }}>{formatTime(duration * r)}</Text></div>)}
                  <div style={{ position: 'absolute', right: 0, top: 0 }}><Text type="secondary" style={{ fontSize: 10 }}>{formatTime(duration)}</Text></div>
                </div>
                <div style={{ width: 50 }} />
              </div>
              {timelineWidth > 0 && <div style={{ position: 'absolute', left: indicatorLeft, top: 0, bottom: 0, width: 2, background: '#ff4d4f', zIndex: 100, pointerEvents: 'none', boxShadow: '0 0 4px rgba(255,77,79,0.5)' }} />}
            </div>
          )}

          {activeTab === 'analysis' && (
            <Row gutter={16}>
              {fusionSummaries.map(speaker => (
                <Col span={24} key={speaker.speaker_id} style={{ marginBottom: 16 }}>
                  <Card size="small">
                    <Space><div style={{ width: 16, height: 16, borderRadius: '50%', backgroundColor: speaker.speaker_color }} /><Text strong>{speaker.speaker_label}</Text><Tag>{formatTime(speaker.total_duration)}</Tag></Space>
                    <Divider style={{ margin: '12px 0' }} />
                    <Row gutter={16}>
                      <Col span={8}><Text type="secondary">主导情绪</Text><div><Tag color={emotionColor(speaker.emotion?.dominant_emotion)}>{speaker.emotion?.dominant_emotion || 'neutral'}</Tag></div></Col>
                      <Col span={8}><Text type="secondary">语速</Text><div><Text>{speaker.prosody?.speech_rate?.toFixed(1) || '-'} 字/秒</Text></div></Col>
                      <Col span={8}><Text type="secondary">停顿比例</Text><div><Text>{((speaker.prosody?.pause_ratio || 0) * 100).toFixed(1)}%</Text></div></Col>
                    </Row>
                  </Card>
                </Col>
              ))}
            </Row>
          )}
        </div>
      </div>
    </div>
  )
}
