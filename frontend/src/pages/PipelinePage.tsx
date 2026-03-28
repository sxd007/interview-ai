import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Card, Typography, Space, Spin, Button, Tag, Divider, message,
  Alert, Statistic, Row, Col,
} from 'antd'
import {
  CheckCircleOutlined, SyncOutlined,
  VideoCameraOutlined, PlayCircleOutlined,
  ClockCircleOutlined, LoadingOutlined,
  EditOutlined, CheckCircleFilled, CloseCircleFilled,
  BarChartOutlined,
} from '@ant-design/icons'
import axios from 'axios'

const { Text } = Typography
const api = axios.create({ baseURL: '/api', timeout: 600000 })

interface ChunkData {
  id: string
  chunk_index: number
  global_start: number
  global_end: number
  status: string
  file_path?: string
  error_message?: string
}

const formatTime = (s: number) => {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  return `${m}:${String(sec).padStart(2, '0')}`
}

const chunkStatusIcon = (status: string): React.ReactNode => {
  const map: Record<string, React.ReactNode> = {
    pending: <ClockCircleOutlined style={{ color: '#999' }} />,
    processing: <LoadingOutlined style={{ color: '#1890ff' }} />,
    review_pending: <EditOutlined style={{ color: '#faad14' }} />,
    review_completed: <CheckCircleFilled style={{ color: '#52c41a' }} />,
    failed: <CloseCircleFilled style={{ color: '#f5222d' }} />,
  }
  return map[status] || <ClockCircleOutlined />
}

const chunkStatusText: Record<string, string> = {
  pending: '等待中',
  processing: '处理中',
  review_pending: '待审核',
  review_completed: '审核通过',
  failed: '失败',
}

const chunkStatusColor: Record<string, string> = {
  pending: 'default',
  processing: 'processing',
  review_pending: 'warning',
  review_completed: 'success',
  failed: 'error',
}


export function PipelinePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: interviewData, isLoading: interviewLoading } = useQuery({
    queryKey: ['interview', id],
    queryFn: () => api.get(`/interviews/${id}`).then(r => r.data),
    enabled: !!id,
    refetchInterval: 5000,
  })

  const { data: chunksData, isLoading: chunksLoading } = useQuery({
    queryKey: ['chunks', id],
    queryFn: () => api.get(`/interviews/${id}/chunks`).then(r => r.data),
    enabled: !!id,
    refetchInterval: 5000,
  })

  const runAllChunksMutation = useMutation({
    mutationFn: () => 
      api.post(`/interviews/${id}/process`, { 
        chunk_enabled: true, 
        chunk_duration: 600,
      }),
    onSuccess: () => {
      message.success('Chunk 处理已启动')
      queryClient.invalidateQueries({ queryKey: ['chunks', id] })
      queryClient.invalidateQueries({ queryKey: ['interview', id] })
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || '启动失败'),
  })

  const runGlobalStageMutation = useMutation({
    mutationFn: (stageName: string) =>
      api.post(`/interviews/${id}/pipeline/${stageName}/run`),
    onSuccess: () => {
      message.success('阶段执行完成')
      queryClient.invalidateQueries({ queryKey: ['chunks', id] })
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || '执行失败'),
  })

  const interview = interviewData || {}
  const chunks: ChunkData[] = chunksData?.chunks || []
  const isChunked = chunksData?.is_chunked || false
  const allPending = chunks.length > 0 && chunks.every(c => c.status === 'pending')

  useEffect(() => {
    if (interview?.status === 'queued' && allPending && !runAllChunksMutation.isPending) {
      console.log('[PipelinePage] Auto-triggering processing for queued interview')
      runAllChunksMutation.mutate()
    }
  }, [interview?.status, allPending])

  if (interviewLoading || chunksLoading) {
    return <div style={{ textAlign: 'center', marginTop: 100 }}><Spin size="large" /></div>
  }

  const reviewedCount = chunks.filter(c => c.status === 'review_completed').length
  const pendingReviewCount = chunks.filter(c => c.status === 'review_pending').length
  const allReviewed = chunks.length > 0 && reviewedCount === chunks.length

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {chunks.length > 0 && chunks[0]?.file_path && (
        <Card bodyStyle={{ padding: 0 }}>
          <video
            key={chunks[0].file_path}
            src={`/data/${chunks[0].file_path.replace(/^data\//, '')}`}
            controls
            style={{ width: '100%', maxHeight: 400, background: '#000' }}
          />
        </Card>
      )}
      <Card
        title={
          <Space>
            <VideoCameraOutlined />
            <span>{interview.filename || '访谈'}</span>
            {isChunked && (
              <Tag color="blue">{chunks.length} 个 Chunk</Tag>
            )}
          </Space>
        }
        extra={
          <Space>
            <Button onClick={() => navigate(`/interviews/${id}`)}>返回详情</Button>
          </Space>
        }
      >
        <Row gutter={16}>
          <Col span={6}>
            <Statistic
              title="视频时长"
              value={formatTime(interview.duration || 0)}
              prefix={<VideoCameraOutlined />}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="Chunk 状态"
              value={`${reviewedCount}/${chunks.length}`}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: allReviewed ? '#52c41a' : pendingReviewCount > 0 ? '#faad14' : '#999' }}
              suffix={allReviewed ? '全部审核' : pendingReviewCount > 0 ? '待审核' : ''}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="深度分析"
              value={allReviewed ? '可执行' : '待审核完成'}
              prefix={<BarChartOutlined />}
              valueStyle={{ color: allReviewed ? '#1890ff' : '#999' }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="当前状态"
              value={interview.status === 'queued' ? '处理队列中' : interview.status === 'processing' ? '处理中' : interview.status === 'completed' ? '已完成' : '等待中'}
              valueStyle={{
                color: interview.status === 'completed' ? '#52c41a'
                       : interview.status === 'failed' ? '#f5222d'
                       : interview.status === 'queued' || interview.status === 'processing' ? '#1890ff' : '#999'
              }}
            />
          </Col>
        </Row>
      </Card>

      {isChunked ? (
        <>
          <Card title="Chunk 处理进度">
            <Space wrap style={{ width: '100%', gap: 12 }}>
              {chunks.map((chunk: any) => (
                <Card
                  key={chunk.id}
                  size="small"
                  style={{
                    width: 200,
                    borderColor:
                      chunk.status === 'review_pending' ? '#faad14'
                      : chunk.status === 'review_completed' ? '#52c41a'
                      : chunk.status === 'processing' ? '#1890ff'
                      : '#f0f0f0',
                    borderWidth: chunk.status === 'review_pending' ? 2 : 1,
                  }}
                  bodyStyle={{ padding: 12 }}
                >
                  <Space>
                    {chunkStatusIcon(chunk.status)}
                    <Text strong>Chunk {chunk.chunk_index + 1}</Text>
                  </Space>
                  <div style={{ marginTop: 4 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {formatTime(chunk.global_start)} - {formatTime(chunk.global_end)}
                    </Text>
                  </div>
                  <div style={{ marginTop: 4 }}>
                    <Tag color={chunkStatusColor[chunk.status] || 'default'} style={{ marginRight: 4 }}>
                      {chunkStatusText[chunk.status] || chunk.status}
                    </Tag>
                  </div>
                  {chunk.status === 'review_pending' && (
                    <Button
                      type="primary"
                      size="small"
                      block
                      style={{ marginTop: 8 }}
                      icon={<EditOutlined />}
                      onClick={() => navigate(`/interviews/${id}/review?chunk=${chunk.id}`)}
                    >
                      进入审核
                    </Button>
                  )}
                  {chunk.status === 'review_completed' && (
                    <Button
                      size="small"
                      block
                      style={{ marginTop: 8 }}
                      onClick={() => navigate(`/interviews/${id}/review?chunk=${chunk.id}`)}
                    >
                      查看结果
                    </Button>
                  )}
                </Card>
              ))}
            </Space>

            <Divider />

            <Space style={{ width: '100%' }} direction="vertical" size="middle">
              <Button
                onClick={() => runAllChunksMutation.mutate()}
                loading={runAllChunksMutation.isPending}
                icon={<SyncOutlined />}
              >
                重新处理全部 Chunk
              </Button>
            </Space>
          </Card>

          <Card title="深度分析阶段">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Alert
                type={allReviewed ? 'success' : 'info'}
                showIcon
                icon={allReviewed ? <CheckCircleOutlined /> : <ClockCircleOutlined />}
                message={
                  allReviewed
                    ? '所有 Chunk 审核已完成，可以执行深度分析'
                    : `请先完成所有 Chunk 的人工审核（${reviewedCount}/${chunks.length}）`
                }
                style={{ marginBottom: 16 }}
              />

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
                {['prosody', 'emotion', 'fusion'].map((stageName) => {
                  const stageLabel = { prosody: '韵律分析', emotion: '情绪识别', fusion: '情绪融合' }[stageName] || stageName
                  const stageDesc = {
                    prosody: '分析语调、语速、停顿等韵律特征',
                    emotion: '基于音频和视频的情绪识别',
                    fusion: '融合音频与视频情绪，生成报告',
                  }[stageName] || ''
                  const canRun = allReviewed

                  return (
                    <Card
                      key={stageName}
                      size="small"
                      style={{
                        borderColor: canRun ? '#1890ff' : '#f0f0f0',
                        opacity: canRun ? 1 : 0.6,
                      }}
                    >
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <Space>
                          <BarChartOutlined style={{ fontSize: 20, color: '#1890ff' }} />
                          <Text strong>{stageLabel}</Text>
                        </Space>
                        <Text type="secondary" style={{ fontSize: 12 }}>{stageDesc}</Text>
                        <Button
                          type="primary"
                          disabled={!canRun}
                          loading={runGlobalStageMutation.isPending}
                          onClick={() => runGlobalStageMutation.mutate(stageName)}
                          icon={canRun ? <PlayCircleOutlined /> : undefined}
                        >
                          执行 {stageLabel}
                        </Button>
                      </Space>
                    </Card>
                  )
                })}
              </div>
            </Space>
          </Card>
        </>
      ) : (
        <Card>
          <Alert
            message="非分块模式"
            description="该视频未启用分块处理。切换到分块模式需要重新上传视频。"
            type="info"
            showIcon
          />
        </Card>
      )}
    </Space>
  )
}


