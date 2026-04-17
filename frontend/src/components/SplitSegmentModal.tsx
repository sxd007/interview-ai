import { useState, useMemo, useEffect } from 'react'
import { Modal, Input, Select, InputNumber, Space, Divider, Alert, Typography, Tag, Button } from 'antd'
import { ScissorOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons'

const { Text } = Typography
const { TextArea } = Input

interface SegmentData {
  id: string
  speaker_id: string | null
  start_time: number
  end_time: number
  transcript: string | null
}

interface SpeakerData {
  id: string
  label: string
  color: string
}

interface SplitSegmentModalProps {
  open: boolean
  segment: SegmentData | null
  speakers: SpeakerData[]
  onSplit: (data: SplitData) => void
  onCancel: () => void
  loading?: boolean
}

export interface SplitData {
  splitType: 'text' | 'time'
  splitTime?: number
  splitTextPosition?: number
  speakerId1: string
  speakerId2: string
  text1?: string
  text2?: string
  multipleSplits?: SplitPoint[]
}

interface SplitPoint {
  position: number
  speakerId: string
  text?: string
}

const formatTime = (s: number) => {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

export function SplitSegmentModal({
  open,
  segment,
  speakers,
  onSplit,
  onCancel,
  loading = false,
}: SplitSegmentModalProps) {
  const [splitMode, setSplitMode] = useState<'single' | 'multiple'>('single')
  const [splitType, setSplitType] = useState<'text' | 'time'>('text')
  const [splitTextPosition, setSplitTextPosition] = useState(0)
  const [splitTime, setSplitTime] = useState(0)
  const [speakerId1, setSpeakerId1] = useState<string>('')
  const [speakerId2, setSpeakerId2] = useState<string>('')
  const [text1, setText1] = useState('')
  const [text2, setText2] = useState('')
  const [splitPoints, setSplitPoints] = useState<SplitPoint[]>([])
  const [selectedSplitIndex, setSelectedSplitIndex] = useState<number | null>(null)

  const transcript = segment?.transcript || ''
  const duration = segment ? segment.end_time - segment.start_time : 0

  useEffect(() => {
    if (segment && open) {
      const mid = Math.floor(transcript.length / 2)
      setSplitTime((segment.start_time + segment.end_time) / 2)
      setSplitTextPosition(mid)
      setSpeakerId1(segment.speaker_id || speakers[0]?.id || '')
      setSpeakerId2(speakers[1]?.id || speakers[0]?.id || '')
      setText1(transcript.slice(0, mid))
      setText2(transcript.slice(mid))
      setSplitPoints([])
      setSelectedSplitIndex(null)
    }
  }, [segment?.id, open])

  const estimatedSplitTime = useMemo(() => {
    if (splitType === 'time') {
      return splitTime
    }
    if (!segment || !transcript) {
      return segment ? (segment.start_time + segment.end_time) / 2 : 0
    }
    const ratio = splitTextPosition / transcript.length
    return segment.start_time + duration * ratio
  }, [splitType, splitTime, splitTextPosition, segment, transcript, duration])

  const handleTextClick = (e: React.MouseEvent<HTMLTextAreaElement>) => {
    const textarea = e.target as HTMLTextAreaElement
    const position = textarea.selectionStart
    
    if (splitMode === 'single') {
      setSplitTextPosition(position)
      setText1(transcript.slice(0, position))
      setText2(transcript.slice(position))
    } else {
      if (selectedSplitIndex !== null) {
        const newSplitPoints = [...splitPoints]
        newSplitPoints[selectedSplitIndex] = {
          ...newSplitPoints[selectedSplitIndex],
          position,
          text: transcript.slice(
            selectedSplitIndex === 0 ? 0 : splitPoints[selectedSplitIndex - 1].position,
            position
          )
        }
        setSplitPoints(newSplitPoints)
        setSelectedSplitIndex(null)
      } else {
        const sortedPositions = [...splitPoints.map(sp => sp.position), position].sort((a, b) => a - b)
        const newSplitPoints = sortedPositions.map((pos, idx) => ({
          position: pos,
          speakerId: speakers[idx % speakers.length]?.id || speakers[0]?.id || '',
          text: transcript.slice(idx === 0 ? 0 : sortedPositions[idx - 1], pos)
        }))
        setSplitPoints(newSplitPoints)
      }
    }
  }

  const handleTextSelect = (e: React.SyntheticEvent<HTMLTextAreaElement>) => {
    const textarea = e.target as HTMLTextAreaElement
    const position = textarea.selectionStart
    
    if (splitMode === 'single') {
      setSplitTextPosition(position)
      setText1(transcript.slice(0, position))
      setText2(transcript.slice(position))
    }
  }

  const addSplitPoint = () => {
    const newPosition = Math.floor(transcript.length / (splitPoints.length + 2))
    const sortedPositions = [...splitPoints.map(sp => sp.position), newPosition].sort((a, b) => a - b)
    const newSplitPoints = sortedPositions.map((pos, idx) => ({
      position: pos,
      speakerId: speakers[idx % speakers.length]?.id || speakers[0]?.id || '',
      text: transcript.slice(idx === 0 ? 0 : sortedPositions[idx - 1], pos)
    }))
    setSplitPoints(newSplitPoints)
  }

  const removeSplitPoint = (index: number) => {
    const newSplitPoints = splitPoints.filter((_, idx) => idx !== index)
    setSplitPoints(newSplitPoints)
  }

  const updateSplitPointSpeaker = (index: number, speakerId: string) => {
    const newSplitPoints = [...splitPoints]
    newSplitPoints[index] = { ...newSplitPoints[index], speakerId }
    setSplitPoints(newSplitPoints)
  }

  const handleOk = () => {
    if (!segment) return

    if (splitMode === 'multiple' && splitPoints.length > 0) {
      const sortedSplitPoints = [...splitPoints].sort((a, b) => a.position - b.position)
      const data: SplitData = {
        splitType: 'text',
        speakerId1: segment.speaker_id || speakers[0]?.id || '',
        speakerId2: sortedSplitPoints[0]?.speakerId || speakers[0]?.id || '',
        multipleSplits: sortedSplitPoints
      }
      onSplit(data)
    } else {
      const data: SplitData = {
        splitType,
        speakerId1,
        speakerId2,
      }

      if (splitType === 'text') {
        data.splitTextPosition = splitTextPosition
        data.text1 = text1
        data.text2 = text2
      } else {
        data.splitTime = splitTime
      }

      onSplit(data)
    }
  }

  const speaker1 = speakers.find(s => s.id === speakerId1)
  const speaker2 = speakers.find(s => s.id === speakerId2)

  const renderTextPreview = () => {
    if (splitMode === 'multiple' && splitPoints.length > 0) {
      const sortedSplitPoints = [...splitPoints].sort((a, b) => a.position - b.position)
      const parts: { start: number; end: number; speakerId: string }[] = []
      
      let lastPos = 0
      sortedSplitPoints.forEach((sp, idx) => {
        parts.push({
          start: lastPos,
          end: sp.position,
          speakerId: idx === 0 ? segment?.speaker_id || speakers[0]?.id || '' : sortedSplitPoints[idx - 1]?.speakerId || speakers[0]?.id || ''
        })
        lastPos = sp.position
      })
      parts.push({
        start: lastPos,
        end: transcript.length,
        speakerId: sortedSplitPoints[sortedSplitPoints.length - 1]?.speakerId || speakers[0]?.id || ''
      })

      return (
        <Space direction="vertical" style={{ width: '100%' }}>
          {parts.map((part, idx) => {
            const speaker = speakers.find(s => s.id === part.speakerId)
            const text = transcript.slice(part.start, part.end)
            const startTime = segment ? segment.start_time + (part.start / transcript.length) * duration : 0
            const endTime = segment ? segment.start_time + (part.end / transcript.length) * duration : 0
            
            return (
              <div key={idx} style={{ padding: 12, background: '#f5f5f5', borderRadius: 4 }}>
                <Space direction="vertical" style={{ width: '100%' }}>
                  <div>
                    <Tag color={speaker?.color}>{speaker?.label || '未知'}</Tag>
                    <Text code>{formatTime(startTime)} - {formatTime(endTime)}</Text>
                  </div>
                  <Text>{text}</Text>
                </Space>
              </div>
            )
          })}
        </Space>
      )
    }

    return null
  }

  return (
    <Modal
      title={
        <Space>
          <ScissorOutlined />
          <span>分割段落</span>
        </Space>
      }
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      okText="确认分割"
      cancelText="取消"
      width={800}
      confirmLoading={loading}
    >
      {segment && (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <Alert
            type="info"
            message="将一个段落分割为多个独立的段落，可以分配不同的说话人"
            showIcon
          />

          <div>
            <Text strong>原始段落信息：</Text>
            <Space style={{ marginLeft: 16 }}>
              <Text code>{formatTime(segment.start_time)} - {formatTime(segment.end_time)}</Text>
              {speaker1 && <Tag color={speaker1.color}>{speaker1.label}</Tag>}
              <Text type="secondary">{transcript.slice(0, 30)}...</Text>
            </Space>
          </div>

          <Divider orientation="left">分割模式</Divider>

          <Space>
            <Text>选择分割模式：</Text>
            <Select
              value={splitMode}
              onChange={setSplitMode}
              style={{ width: 200 }}
              options={[
                { label: '单次分割（一分为二）', value: 'single' },
                { label: '多次分割（一分为多）', value: 'multiple' },
              ]}
            />
          </Space>

          {splitMode === 'single' && (
            <>
              <Divider orientation="left">分割方式</Divider>

              <Space>
                <Text>选择分割方式：</Text>
                <Select
                  value={splitType}
                  onChange={setSplitType}
                  style={{ width: 200 }}
                  options={[
                    { label: '文本分割（推荐）', value: 'text' },
                    { label: '时间分割', value: 'time' },
                  ]}
                />
              </Space>

              {splitType === 'text' && (
                <>
                  <div>
                    <Text strong>点击文本标记分割点：</Text>
                    <Text type="secondary" style={{ marginLeft: 8 }}>
                      （点击或选择文本位置）
                    </Text>
                  </div>
                  <TextArea
                    value={transcript}
                    rows={4}
                    onClick={handleTextClick}
                    onSelect={handleTextSelect}
                    placeholder="点击文本标记分割点"
                    readOnly
                    style={{ cursor: 'pointer' }}
                  />
                  <Space>
                    <Text type="secondary">分割位置：第 {splitTextPosition} 个字符</Text>
                    <Text type="secondary">|</Text>
                    <Text type="secondary">
                      估算时间：{formatTime(estimatedSplitTime)}
                    </Text>
                  </Space>
                </>
              )}

              {splitType === 'time' && (
                <div>
                  <Text strong>输入分割时间点：</Text>
                  <Space style={{ marginLeft: 16 }}>
                    <InputNumber
                      min={segment.start_time}
                      max={segment.end_time}
                      step={0.1}
                      value={splitTime}
                      onChange={(v) => setSplitTime(v || 0)}
                      formatter={v => formatTime(Number(v || 0))}
                      parser={v => {
                        if (!v) return 0
                        const parts = v.split(':')
                        if (parts.length === 2) {
                          return Number(parts[0]) * 60 + Number(parts[1])
                        }
                        return Number(v)
                      }}
                    />
                    <Text type="secondary">
                      ({segment.start_time.toFixed(1)}s - {segment.end_time.toFixed(1)}s)
                    </Text>
                  </Space>
                </div>
              )}

              <Divider orientation="left">说话人分配</Divider>

              <Space style={{ width: '100%' }} direction="vertical">
                <div>
                  <Text strong>第一部分说话人：</Text>
                  <Select
                    style={{ width: '100%', marginTop: 8 }}
                    value={speakerId1}
                    onChange={setSpeakerId1}
                    placeholder="选择说话人"
                  >
                    {speakers.map(sp => (
                      <Select.Option key={sp.id} value={sp.id}>
                        <Space>
                          <div style={{ width: 8, height: 8, borderRadius: '50%', background: sp.color }} />
                          {sp.label}
                        </Space>
                      </Select.Option>
                    ))}
                  </Select>
                </div>

                <div>
                  <Text strong>第二部分说话人：</Text>
                  <Select
                    style={{ width: '100%', marginTop: 8 }}
                    value={speakerId2}
                    onChange={setSpeakerId2}
                    placeholder="选择说话人"
                  >
                    {speakers.map(sp => (
                      <Select.Option key={sp.id} value={sp.id}>
                        <Space>
                          <div style={{ width: 8, height: 8, borderRadius: '50%', background: sp.color }} />
                          {sp.label}
                        </Space>
                      </Select.Option>
                    ))}
                  </Select>
                </div>
              </Space>

              <Divider orientation="left">分割预览</Divider>

              <Space direction="vertical" style={{ width: '100%' }}>
                <div style={{ padding: 12, background: '#f5f5f5', borderRadius: 4 }}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div>
                      <Tag color={speaker1?.color}>{speaker1?.label || '未知'}</Tag>
                      <Text code>{formatTime(segment.start_time)} - {formatTime(estimatedSplitTime)}</Text>
                    </div>
                    <Text>{splitType === 'text' ? text1 : '(需手动编辑)'}</Text>
                  </Space>
                </div>

                <div style={{ padding: 12, background: '#f5f5f5', borderRadius: 4 }}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div>
                      <Tag color={speaker2?.color}>{speaker2?.label || '未知'}</Tag>
                      <Text code>{formatTime(estimatedSplitTime)} - {formatTime(segment.end_time)}</Text>
                    </div>
                    <Text>{splitType === 'text' ? text2 : '(需手动编辑)'}</Text>
                  </Space>
                </div>
              </Space>
            </>
          )}

          {splitMode === 'multiple' && (
            <>
              <Divider orientation="left">标记分割点</Divider>

              <div>
                <Text strong>点击文本添加分割点：</Text>
                <Text type="secondary" style={{ marginLeft: 8 }}>
                  （可以添加多个分割点）
                </Text>
              </div>

              <TextArea
                value={transcript}
                rows={4}
                onClick={handleTextClick}
                placeholder="点击文本标记分割点"
                readOnly
                style={{ cursor: 'pointer' }}
              />

              <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                <Text type="secondary">已标记 {splitPoints.length} 个分割点</Text>
                <Button
                  type="dashed"
                  icon={<PlusOutlined />}
                  onClick={addSplitPoint}
                  size="small"
                >
                  添加分割点
                </Button>
              </Space>

              {splitPoints.length > 0 && (
                <>
                  <Divider orientation="left">分割点设置</Divider>

                  <Space direction="vertical" style={{ width: '100%' }}>
                    {splitPoints.map((sp, idx) => {
                      const prevPos = idx === 0 ? 0 : splitPoints[idx - 1].position
                      const text = transcript.slice(prevPos, sp.position)
                      
                      return (
                        <div key={idx} style={{ padding: 12, background: '#fafafa', borderRadius: 4, border: '1px solid #e8e8e8' }}>
                          <Space direction="vertical" style={{ width: '100%' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <Text strong>分割点 {idx + 1}</Text>
                              <Button
                                type="text"
                                danger
                                size="small"
                                icon={<DeleteOutlined />}
                                onClick={() => removeSplitPoint(idx)}
                              />
                            </div>
                            <Space>
                              <Text type="secondary">位置：第 {sp.position} 个字符</Text>
                              <Text type="secondary">|</Text>
                              <Text type="secondary">文本：{text.slice(0, 20)}...</Text>
                            </Space>
                            <div>
                              <Text strong>说话人：</Text>
                              <Select
                                style={{ width: '100%', marginTop: 8 }}
                                value={sp.speakerId}
                                onChange={(v) => updateSplitPointSpeaker(idx, v)}
                                placeholder="选择说话人"
                                size="small"
                              >
                                {speakers.map(s => (
                                  <Select.Option key={s.id} value={s.id}>
                                    <Space>
                                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: s.color }} />
                                      {s.label}
                                    </Space>
                                  </Select.Option>
                                ))}
                              </Select>
                            </div>
                          </Space>
                        </div>
                      )
                    })}
                  </Space>
                </>
              )}

              <Divider orientation="left">分割预览</Divider>

              {renderTextPreview()}
            </>
          )}
        </Space>
      )}
    </Modal>
  )
}
