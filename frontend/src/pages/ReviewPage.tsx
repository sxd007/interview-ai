import { useState, useMemo, useRef } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Card, Typography, Space, Spin, Button, Tag, Table, Modal,
  Select, Divider, message, Alert, Input, InputNumber,
  Popconfirm, List, Badge, Checkbox, Tooltip,
} from 'antd'
import {
  CheckCircleOutlined, EditOutlined,
  MergeOutlined, SaveOutlined, UndoOutlined,
  CheckOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons'
import axios from 'axios'

const { Text } = Typography
const { TextArea } = Input
const api = axios.create({ baseURL: '/api', timeout: 600000 })

const formatTime = (s: number) => {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

const emotionColor = (e: string) => {
  const m: Record<string, string> = {
    happy: 'green', neutral: 'default', sad: 'blue', angry: 'red',
    fearful: 'purple', disgusted: 'volcano', surprised: 'cyan', unknown: 'default',
  }
  return m[e] || 'default'
}

interface ChunkData {
  id: string
  chunk_index: number
  global_start: number
  global_end: number
  status: string
  file_path?: string
}

interface SpeakerData {
  id: string
  label: string
  color: string
  chunk_id?: string
}

interface SegmentData {
  id: string
  speaker_id: string | null
  start_time: number
  end_time: number
  transcript: string | null
  lang: string | null
  event: string | null
  emotion_scores?: Record<string, string | number>
  chunk_id?: string
}

interface PendingChangeData {
  id: string
  chunk_id: string
  change_type: string
  description: string
  created_at: string
}

const changeTypeText: Record<string, string> = {
  speaker_merge: '合并说话人', speaker_rename: '重命名说话人',
  speaker_reassign: '重分配说话人', segment_edit: '编辑段落',
  segment_merge: '合并段落', segment_delete: '删除段落',
  speaker_split: '分裂说话人',
}

export function ReviewPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()
  const urlChunkId = searchParams.get('chunk')

  const [activeChunkId, setActiveChunkId] = useState<string | null>(urlChunkId)
  const [selectedSegmentIds, setSelectedSegmentIds] = useState<string[]>([])
  const [editingSegment, setEditingSegment] = useState<SegmentData | null>(null)
  const [editValues, setEditValues] = useState<Record<string, any>>({})
  const [applyModalOpen, setApplyModalOpen] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const videoRef = useRef<HTMLVideoElement>(null)

  const { data: chunksData, isLoading: chunksLoading } = useQuery({
    queryKey: ['chunks', id],
    queryFn: () => api.get(`/interviews/${id}/chunks`).then(r => r.data),
    enabled: !!id,
    refetchInterval: 10000,
  })

  const interviewId = id!

  const { data: transcriptData } = useQuery({
    queryKey: ['transcript', id],
    queryFn: () => api.get(`/interviews/${interviewId}/transcript`).then(r => r.data),
    enabled: !!interviewId,
  })

  const { data: pendingData } = useQuery({
    queryKey: ['pending-changes', interviewId],
    queryFn: () => api.get(`/interviews/${interviewId}/corrections/pending`).then(r => r.data),
    enabled: !!interviewId,
    refetchInterval: 5000,
  })

  const chunks: ChunkData[] = chunksData?.chunks || []
  const allSpeakers: SpeakerData[] = transcriptData?.speakers || []
  const segments: SegmentData[] = transcriptData?.segments || []
  const pendingChanges: PendingChangeData[] = pendingData?.changes || []

  const activeChunk = useMemo(
    () => chunks.find(c => c.id === activeChunkId) || chunks.find(c => c.status === 'review_pending') || chunks[0],
    [chunks, activeChunkId]
  )

  const speakers: SpeakerData[] = activeChunk
    ? allSpeakers.filter(s => s.chunk_id === activeChunk.id)
    : allSpeakers

  const activeChunkSegments = useMemo(() => {
    if (!activeChunk) return []
    return segments.filter(s =>
      s.chunk_id === activeChunk.id ||
      (s.start_time >= activeChunk.global_start && s.end_time <= activeChunk.global_end)
    ).sort((a, b) => a.start_time - b.start_time)
  }, [segments, activeChunk])

  const activeChunkPending = useMemo(
    () => pendingChanges.filter(c => c.chunk_id === activeChunk?.id),
    [pendingChanges, activeChunk]
  )

  const speakerMap = useMemo(() => Object.fromEntries(speakers.map(s => [s.id, s])), [speakers])

  const addChangeMutation = useMutation({
    mutationFn: (payload: any) => api.post(`/interviews/${interviewId}/corrections/${payload.endpoint}`, payload.body),
    onSuccess: () => {
      message.success('已添加变更')
      queryClient.invalidateQueries({ queryKey: ['pending-changes', interviewId] })
      queryClient.invalidateQueries({ queryKey: ['chunks', id] })
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || '失败'),
  })

  const applyMutation = useMutation({
    mutationFn: () => api.post(`/interviews/${interviewId}/corrections/apply`),
    onSuccess: (r) => {
      message.success(`已应用 ${r.data.applied} 项变更`)
      queryClient.invalidateQueries({ queryKey: ['pending-changes', interviewId] })
      queryClient.invalidateQueries({ queryKey: ['transcript', interviewId] })
      queryClient.invalidateQueries({ queryKey: ['chunks', id] })
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || '应用失败'),
  })

  const discardMutation = useMutation({
    mutationFn: () => api.post(`/interviews/${interviewId}/corrections/discard`),
    onSuccess: () => {
      message.success('已放弃所有变更')
      queryClient.invalidateQueries({ queryKey: ['pending-changes', interviewId] })
      setSelectedSegmentIds([])
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || '放弃失败'),
  })

  const approveMutation = useMutation({
    mutationFn: () => api.post(`/interviews/${interviewId}/chunks/${activeChunk?.id}/approve`),
    onSuccess: () => {
      message.success(`Chunk ${(activeChunk?.chunk_index ?? 0) + 1} 审核通过`)
      queryClient.invalidateQueries({ queryKey: ['chunks', id] })
      queryClient.invalidateQueries({ queryKey: ['pending-changes', interviewId] })
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || '审核失败'),
  })

  const chunkTabItems = chunks.map(chunk => ({
    key: chunk.id,
    label: (
      <Space>
        {chunk.status === 'review_completed'
          ? <CheckCircleOutlined style={{ color: '#52c41a' }} />
          : chunk.status === 'review_pending'
            ? <Badge status="warning" />
            : <Badge status="default" />
        }
        <span>Chunk {chunk.chunk_index + 1}</span>
        <Tag style={{ marginLeft: 4 }}>
          {chunk.status === 'review_completed' ? '通过'
           : chunk.status === 'review_pending' ? '待审'
           : chunk.status === 'processing' ? '处理中'
           : '等待'}
        </Tag>
      </Space>
    ),
    children: null,
  }))

  const segmentColumns = [
    {
      title: '',
      key: 'select',
      width: 40,
      render: (_: any, record: SegmentData) => (
        <Checkbox
          checked={selectedSegmentIds.includes(record.id)}
          onChange={e => {
            if (e.target.checked) setSelectedSegmentIds(prev => [...prev, record.id])
            else setSelectedSegmentIds(prev => prev.filter(x => x !== record.id))
          }}
        />
      ),
    },
    {
      title: '时间',
      key: 'time',
      width: 130,
      render: (_: any, record: SegmentData) => (
        <Text code style={{ fontSize: 12 }}>
          {formatTime(record.start_time)} - {formatTime(record.end_time)}
        </Text>
      ),
    },
    {
      title: '说话人',
      key: 'speaker',
      width: 100,
      render: (_: any, record: SegmentData) => {
        const sp = speakerMap[record.speaker_id || '']
        return sp
          ? <Tag color={sp.color}>{sp.label}</Tag>
          : <Tag>未知</Tag>
      },
    },
    {
      title: '语言',
      key: 'lang',
      width: 50,
      render: (_: any, record: SegmentData) =>
        record.lang && record.lang !== 'zh' ? <Tag>{record.lang}</Tag> : null,
    },
    {
      title: '情绪',
      key: 'emotion',
      width: 70,
      render: (_: any, record: SegmentData) => {
        const e = String(record.emotion_scores?.emotion ?? '')
        return e && e !== 'neutral' ? <Tag color={emotionColor(e)}>{e}</Tag> : null
      },
    },
    {
      title: '文本',
      key: 'text',
      ellipsis: true,
      render: (_: any, record: SegmentData) => (
        <Text style={{ fontSize: 12 }}>{record.transcript || '(无)'}</Text>
      ),
    },
    {
      title: '',
      key: 'action',
      width: 60,
      render: (_: any, record: SegmentData) => (
        <Button size="small" icon={<EditOutlined />}
          onClick={() => {
            setEditingSegment(record)
            setEditValues({})
            setApplyModalOpen(true)
          }}
        />
      ),
    },
  ]

  if (!chunks || chunks.length === 0) {
    if (chunksLoading) return <div style={{ textAlign: 'center', marginTop: 100 }}><Spin size="large" /></div>
    return <div style={{ textAlign: 'center', marginTop: 100 }}><Text>暂无 Chunk 数据</Text></div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%', height: '100vh', overflow: 'hidden' }}>

      <Card
        size="small"
        style={{ marginBottom: 0 }}
        bodyStyle={{ padding: '8px 16px' }}
      >
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Button size="small" onClick={() => navigate(`/interviews/${id}/pipeline`)}>
              返回流水线
            </Button>
            <Text strong>{transcriptData?.speakers?.length || 0} 个说话人 · {segments.length} 个段落</Text>
          </Space>
          <Space>
            <Badge count={pendingChanges.length} style={{ backgroundColor: '#faad14' }}>
              <Button size="small" icon={<EditOutlined />}
                onClick={() => {
                  setApplyModalOpen(true)
                  setEditingSegment(null)
                }}
              >
                变更 ({pendingChanges.length})
              </Button>
            </Badge>
          </Space>
        </Space>
      </Card>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', padding: '0 16px' }}>
        <div style={{ flex: 1, overflow: 'auto', display: 'flex', gap: 8 }}>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <div style={{ width: 400, flexShrink: 0 }}>
                {activeChunk?.file_path && (
                  <div style={{ background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <video
                      key={activeChunk.file_path}
                      ref={videoRef}
                      src={`/data/${activeChunk.file_path.replace(/^data\//, '')}`}
                      controls
                      style={{ maxHeight: 300, maxWidth: '100%', background: '#000' }}
                      onTimeUpdate={() => setCurrentTime((videoRef.current?.currentTime || 0) + (activeChunk?.global_start || 0))}
                    />
                  </div>
                )}
              </div>

              <Card size="small" title="Chunk 列表" bodyStyle={{ padding: 8 }} style={{ flex: 1 }}>
                {chunkTabItems.length > 0 ? (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {chunkTabItems.map(tab => (
                      <Tag
                        key={tab.key}
                        color={activeChunk?.id === tab.key ? 'blue' : 'default'}
                        onClick={() => setActiveChunkId(tab.key)}
                        style={{ cursor: 'pointer', margin: 2 }}
                      >
                        {tab.label}
                      </Tag>
                    ))}
                  </div>
                ) : (
                  <Text type="secondary">暂无可审核的 Chunk</Text>
                )}
              </Card>
            </div>

            {activeChunk && (
            <>
              <div style={{ marginBottom: 8 }}>
                <Space>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {formatTime(activeChunk.global_start)} - {formatTime(activeChunk.global_end)}
                    &nbsp;·&nbsp;{activeChunkSegments.length} 个段落
                    &nbsp;·&nbsp;{activeChunkPending.length} 项待应用变更
                    &nbsp;·&nbsp;当前: {formatTime(currentTime)}
                  </Text>
                </Space>
              </div>

              <div style={{ position: 'relative', height: 40, background: '#f5f5f5', borderRadius: 4, overflow: 'hidden', marginBottom: 8 }}>
                <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, display: 'flex', alignItems: 'center' }}>
                  {activeChunkSegments.map((seg, i) => {
                    const start = seg.start_time - activeChunk.global_start
                    const end = seg.end_time - activeChunk.global_start
                    const duration = activeChunk.global_end - activeChunk.global_start
                    const left = (start / duration) * 100
                    const width = ((end - start) / duration) * 100
                    const isPlaying = currentTime >= seg.start_time && currentTime < seg.end_time
                    const speaker = speakerMap[seg.speaker_id || '']
                    return (
                      <Tooltip key={seg.id} title={
                        <Space direction="vertical" size={0}>
                          <Text style={{ color: '#fff' }}>{speaker?.label || '未知'} ({formatTime(seg.start_time)} - {formatTime(seg.end_time)})</Text>
                          <Text style={{ color: '#fff', fontSize: 11 }} ellipsis>{seg.transcript?.slice(0, 50)}</Text>
                        </Space>
                      }>
                        <div
                          onClick={() => {
                            if (videoRef.current) {
                              videoRef.current.currentTime = seg.start_time - activeChunk.global_start
                            }
                          }}
                          style={{
                            position: 'absolute',
                            left: `${left}%`,
                            width: `${width}%`,
                            height: isPlaying ? 36 : 28,
                            background: isPlaying ? speaker?.color || '#1890ff' : `${speaker?.color || '#1890ff'}88`,
                            borderRadius: 4,
                            cursor: 'pointer',
                            transition: 'height 0.2s',
                            marginLeft: i === 0 ? 0 : 1,
                            marginRight: i === activeChunkSegments.length - 1 ? 0 : 1,
                          }}
                        />
                      </Tooltip>
                    )
                  })}
                </div>
              </div>

              <Table
                size="small"
                dataSource={activeChunkSegments}
                columns={segmentColumns}
                rowKey="id"
                pagination={false}
                scroll={{ y: 400 }}
                style={{ cursor: 'pointer' }}
                rowClassName={(record) => {
                  const isPlaying = currentTime >= record.start_time && currentTime < record.end_time
                  return isPlaying ? 'ant-table-row-active' : ''
                }}
              />

              {activeChunk.status !== 'review_completed' && activeChunk.status !== 'processing' && (
                <div style={{ marginTop: 8 }}>
                  <Space>
                    <Button
                      icon={<MergeOutlined />}
                      disabled={selectedSegmentIds.length < 2}
                      onClick={() => {
                        if (selectedSegmentIds.length < 2) { message.warning('请选择至少2个段落'); return }
                        addChangeMutation.mutate({
                          endpoint: 'merge-segments',
                          body: { segment_ids: selectedSegmentIds },
                        })
                        setSelectedSegmentIds([])
                      }}
                    >
                      合并所选
                    </Button>
                    <Button
                      danger
                      disabled={selectedSegmentIds.length === 0}
                      onClick={() => {
                        addChangeMutation.mutate({
                          endpoint: 'delete-segments',
                          body: { segment_ids: selectedSegmentIds },
                        })
                        setSelectedSegmentIds([])
                      }}
                    >
                      删除所选
                    </Button>
                    <Button onClick={() => setSelectedSegmentIds([])}>
                      清除选择
                    </Button>
                  </Space>
                </div>
              )}
            </>
          )}
          </div>
        </div>

        <div style={{ width: 360, flexShrink: 0, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 12, paddingLeft: 16 }}>
          <Card size="small" title="操作" bodyStyle={{ padding: 12 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                disabled={pendingChanges.length === 0}
                loading={applyMutation.isPending}
                onClick={() => setApplyModalOpen(true)}
                block
              >
                应用变更 ({pendingChanges.length} 项)
              </Button>
              <Button
                danger
                icon={<UndoOutlined />}
                disabled={pendingChanges.length === 0}
                loading={discardMutation.isPending}
                onClick={() => {
                  Modal.confirm({
                    title: '放弃所有变更？',
                    content: '将删除所有待应用的变更，此操作不可撤销。',
                    okText: '确认放弃', okButtonProps: { danger: true },
                    cancelText: '取消',
                    onOk: () => discardMutation.mutate(),
                  })
                }}
                block
              >
                放弃全部
              </Button>

              {activeChunk && activeChunk.status === 'review_pending' && (
                <>
                  <Divider style={{ margin: '8px 0' }} />
                  <Popconfirm
                    title={`确认 Chunk ${activeChunk.chunk_index + 1} 审核通过？`}
                    description={
                      <Space direction="vertical">
                        {pendingChanges.length > 0 && (
                          <Alert type="warning" message={`有 ${pendingChanges.length} 项未应用的变更，应用后将成为标注数据`} />
                        )}
                        <Text>审核通过后将标记该 Chunk 已完成，人工审核数据将被记录为标注数据。</Text>
                      </Space>
                    }
                    onConfirm={() => approveMutation.mutate()}
                    okText="确认通过"
                    cancelText="取消"
                  >
                    <Button
                      type="primary"
                      icon={<CheckOutlined />}
                      loading={approveMutation.isPending}
                      style={{ background: '#52c41a', borderColor: '#52c41a' }}
                      block
                    >
                      确认审核通过
                    </Button>
                  </Popconfirm>
                </>
              )}

              {activeChunk && activeChunk.status === 'review_completed' && (
                <Alert type="success" showIcon icon={<CheckCircleOutlined />}
                  message="该 Chunk 已审核通过" />
              )}
            </Space>
          </Card>

          <Card size="small" title="说话人管理" bodyStyle={{ padding: 12 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              {speakers.map(sp => (
                <div key={sp.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #f0f0f0' }}>
                  <Space>
                    <div style={{ width: 12, height: 12, borderRadius: '50%', background: sp.color }} />
                    <Text>{sp.label}</Text>
                  </Space>
                  <Space>
                    <Button size="small" onClick={() => {
                      const newLabel = prompt(`重命名 "${sp.label}" 为：`, sp.label)
                      if (newLabel && newLabel !== sp.label) {
                        addChangeMutation.mutate({
                          endpoint: 'rename-speaker',
                          body: { speaker_id: sp.id, new_label: newLabel, chunk_id: activeChunk?.id },
                        })
                      }
                    }}>重命名</Button>
                    <Button size="small" onClick={() => {
                      const otherSp = speakers.filter(s => s.id !== sp.id)
                      if (otherSp.length === 0) { message.info('没有其他说话人'); return }
                      const segIds = segments.filter(s => s.speaker_id === sp.id).map(s => s.id)
                      if (segIds.length === 0) { message.info('该说话人无段落'); return }
                      addChangeMutation.mutate({
                        endpoint: 'reassign-speaker',
                        body: { segment_ids: segIds, new_speaker_id: otherSp[0].id },
                      })
                    }}>改归属</Button>
                  </Space>
                </div>
              ))}

              <Divider style={{ margin: '8px 0' }} />

              <Text type="secondary" style={{ fontSize: 12 }}>
                选择多个说话人合并：
              </Text>
              <Select
                mode="multiple"
                placeholder="选择要合并的说话人"
                style={{ width: '100%' }}
                onChange={(vals) => {
                  if (vals.length >= 2) {
                    const target = vals[0]
                    const merged = vals.slice(1)
                    Modal.confirm({
                      title: '确认合并说话人',
                      icon: <ExclamationCircleOutlined />,
                      content: `将 ${merged.length} 个说话人合并到 ${speakerMap[target]?.label || target}？`,
                      okText: '确认合并',
                      cancelText: '取消',
                      onOk: () => {
                        addChangeMutation.mutate({
                          endpoint: 'merge-speakers',
                          body: { target_speaker_id: target, merged_speaker_ids: merged, chunk_id: activeChunk?.id },
                        })
                      },
                    })
                  }
                }}
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
            </Space>
          </Card>

          <Card size="small" title="待应用变更" bodyStyle={{ padding: 8 }}>
            {pendingChanges.length === 0 ? (
              <Text type="secondary" style={{ fontSize: 12 }}>暂无待应用变更</Text>
            ) : (
              <List
                size="small"
                dataSource={pendingChanges.slice(0, 10)}
                renderItem={(item: PendingChangeData) => (
                  <List.Item
                    style={{ padding: '4px 0' }}
                    actions={[
                      <Button key="del" size="small" type="text" danger
                        onClick={() => {
                          api.delete(`/interviews/${interviewId}/corrections/${item.id}`).then(() => {
                            queryClient.invalidateQueries({ queryKey: ['pending-changes', interviewId] })
                          })
                        }}
                      >删除</Button>
                    ]}
                  >
                    <List.Item.Meta
                      title={<Tag style={{ fontSize: 11 }}>{changeTypeText[item.change_type] || item.change_type}</Tag>}
                      description={<Text type="secondary" style={{ fontSize: 11 }}>{item.description}</Text>}
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </div>
      </div>

      <Modal
        title={editingSegment ? '编辑段落' : '变更概览'}
        open={applyModalOpen}
        onCancel={() => { setApplyModalOpen(false); setEditingSegment(null); setEditValues({}) }}
        footer={null}
        width={600}
      >
        {editingSegment ? (
          <Space direction="vertical" style={{ width: '100%', marginTop: 16 }}>
            <div>
              <Text strong>时间：</Text>
              <Space>
                <InputNumber min={0} step={0.1} value={editValues.start_time ?? editingSegment.start_time}
                  onChange={v => setEditValues(p => ({ ...p, start_time: v }))} />
                <Text>→</Text>
                <InputNumber min={0} step={0.1} value={editValues.end_time ?? editingSegment.end_time}
                  onChange={v => setEditValues(p => ({ ...p, end_time: v }))} />
              </Space>
            </div>
            <div>
              <Text strong>说话人：</Text>
              <Select style={{ width: '100%', marginTop: 4 }}
                value={editValues.speaker_id ?? editingSegment.speaker_id}
                onChange={v => setEditValues(p => ({ ...p, speaker_id: v }))}
              >
                {speakers.map(sp => <Select.Option key={sp.id} value={sp.id}>{sp.label}</Select.Option>)}
              </Select>
            </div>
            <div>
              <Text strong>转录文本：</Text>
              <TextArea style={{ marginTop: 4 }} rows={3}
                value={editValues.transcript ?? editingSegment.transcript}
                onChange={e => setEditValues(p => ({ ...p, transcript: e.target.value }))}
              />
            </div>
            <Button type="primary" block
              onClick={() => {
                const changes = Object.keys(editValues)
                if (changes.length === 0) { message.warning('没有修改'); return }
                addChangeMutation.mutate({
                  endpoint: 'edit-segment',
                  body: { segment_id: editingSegment.id, changes: editValues },
                })
                setApplyModalOpen(false)
                setEditingSegment(null)
                setEditValues({})
              }}
            >
              确认修改
            </Button>
          </Space>
        ) : (
          <div>
            <Alert type="info" style={{ marginBottom: 16 }}
              message={`将应用 ${pendingChanges.length} 项变更。应用后，受影响的段落将重新生成，同时生成标注数据记录。`}
            />
            <List
              size="small"
              dataSource={pendingChanges}
              renderItem={(item: PendingChangeData) => (
                <List.Item>
                  <List.Item.Meta
                    title={<Space><Tag>{changeTypeText[item.change_type] || item.change_type}</Tag></Space>}
                    description={<Text type="secondary">{item.description}</Text>}
                  />
                </List.Item>
              )}
            />
            <Divider />
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => setApplyModalOpen(false)}>取消</Button>
              <Button type="primary" icon={<SaveOutlined />}
                loading={applyMutation.isPending}
                onClick={() => applyMutation.mutate()}
              >
                确认应用
              </Button>
            </Space>
          </div>
        )}
      </Modal>
    </div>
  )
}
