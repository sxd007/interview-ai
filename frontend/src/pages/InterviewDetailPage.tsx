import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Card,
  Typography,
  Space,
  Spin,
  Tag,
  Button,
  Descriptions,
  Timeline,
  Tabs,
  Progress,
  Empty,
  Tooltip,
  Badge,
  Divider,
  Alert,
} from 'antd'
import {
  PlayCircleOutlined,
  ReloadOutlined,
  AudioOutlined,
  MessageOutlined,
  TeamOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  BarChartOutlined,
  HeartOutlined,
  DownloadOutlined,
  EditOutlined,
} from '@ant-design/icons'
import { interviewApi, transcriptApi, reportApi } from '../services/api'
import { ProsodyChart } from '../components/ProsodyChart'

const { Title, Text, Paragraph } = Typography

const getStatusConfig = (status: string) => {
  const configs: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
    pending: { color: 'default', icon: <ClockCircleOutlined />, text: '等待中' },
    processing: { color: 'processing', icon: <ReloadOutlined spin />, text: '处理中' },
    completed: { color: 'success', icon: <CheckCircleOutlined />, text: '已完成' },
    failed: { color: 'error', icon: <CloseCircleOutlined />, text: '失败' },
  }
  return configs[status] || configs.pending
}

const formatTime = (seconds: number) => {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

const emotionColor = (emotion: string) => {
  const map: Record<string, string> = {
    happy: 'green', neutral: 'default', sad: 'blue', angry: 'red',
    fearful: 'purple', disgusted: 'volcano', surprised: 'cyan', unknown: 'default',
  }
  return map[emotion] || 'default'
}

export function InterviewDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: interviewData, isLoading: interviewLoading, isError } = useQuery({
    queryKey: ['interview', id],
    queryFn: () => interviewApi.get(id!),
    refetchInterval: (query) => {
      const status = query.state.data?.data?.status
      if (status === 'processing' || status === 'pending' || status === 'queued') return 5000
      return false
    },
    enabled: !!id,
  })

  const interview = interviewData?.data

  const { data: transcriptData, isLoading: transcriptLoading } = useQuery({
    queryKey: ['transcript', id],
    queryFn: () => transcriptApi.get(id!),
    enabled: !!id && !!interview,
    retry: 3,
  })

  const processMutation = useMutation({
    mutationFn: () => interviewApi.process(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['interview', id] })
    },
  })

  const downloadMutation = useMutation({
    mutationFn: () => reportApi.download(id!),
    onSuccess: (data: any) => {
      const url = URL.createObjectURL(new Blob([data.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `interview_${id?.slice(0, 8)}.pdf`
      a.click()
    },
  })

  const statusConfig = interview ? getStatusConfig(interview.status) : getStatusConfig('pending')

  if (interviewLoading) {
    return (
      <div style={{ textAlign: 'center', marginTop: 100 }}>
        <Spin size="large" />
        <Text type="secondary" style={{ display: 'block', marginTop: 16 }}>
          加载中...
        </Text>
      </div>
    )
  }

  if (isError || !interview) {
    return (
      <Empty description="访谈不存在">
        <Button type="primary" onClick={() => navigate('/interviews')}>
          返回列表
        </Button>
      </Empty>
    )
  }

  const speakers = transcriptData?.data?.speakers || []
  const segments = transcriptData?.data?.segments || []

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card
        title="访谈信息"
        extra={
          <Space>
            <Tag color={statusConfig.color} icon={statusConfig.icon}>
              {statusConfig.text}
            </Tag>
            {interview.status === 'pending' || interview.status === 'failed' ? (
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={() => processMutation.mutate()}
                loading={processMutation.isPending}
              >
                开始处理
              </Button>
            ) : null}
              {(interview.status === 'queued' || interview.status === 'processing' || interview.status === 'completed') && (
                <>
                  <Button
                    icon={<EditOutlined />}
                    onClick={() => navigate(`/interviews/${id}/pipeline`)}
                  >
                    {interview.is_chunked ? '查看进度' : '流水线'}
                  </Button>
                  <Button
                    icon={<DownloadOutlined />}
                    onClick={() => downloadMutation.mutate()}
                    loading={downloadMutation.isPending}
                  >
                    下载PDF
                  </Button>
                </>
              )}
          </Space>
        }
      >
        <Descriptions column={2}>
          <Descriptions.Item label="文件名">{interview.filename}</Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {new Date(interview.created_at).toLocaleString('zh-CN')}
          </Descriptions.Item>
          <Descriptions.Item label="时长">
            {interview.duration ? formatTime(interview.duration) : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="分辨率">{interview.resolution || '-'}</Descriptions.Item>
        </Descriptions>

        {(interview.status === 'processing' || interview.status === 'pending') && (
          <div style={{ marginTop: 16 }}>
            <Progress percent={interview.status === 'processing' ? 50 : 10} status="active" />
            <Text type="secondary">正在处理中，请稍候...</Text>
          </div>
        )}

        {interview.status === 'failed' && interview.error_message && (
          <Alert
            type="error"
            message="处理失败"
            description={interview.error_message}
            style={{ marginTop: 16 }}
            showIcon
          />
        )}
      </Card>

      {interview.status === 'completed' && (
        <Tabs
          defaultActiveKey="transcript"
          items={[
            {
              key: 'transcript',
              label: (
                <span>
                  <MessageOutlined /> 转录文本
                </span>
              ),
              children: (
                <Card>
                  {transcriptLoading ? (
                    <Spin tip="正在加载转录..." />
                  ) : segments.length > 0 ? (
                    <div>
                      <Space style={{ marginBottom: 16 }}>
                        <Badge count={speakers.length} showZero color="#1890ff">
                          <TeamOutlined /> 说话人
                        </Badge>
                        <Badge count={segments.length} showZero color="#52c41a">
                          <AudioOutlined /> 段落
                        </Badge>
                      </Space>

                      <div style={{ marginBottom: 16 }}>
                        {speakers.map((speaker) => (
                          <Tag key={speaker.id} color={speaker.color} style={{ marginRight: 8 }}>
                            {speaker.label}
                          </Tag>
                        ))}
                      </div>

                      <div
                        style={{
                          maxHeight: 500,
                          overflowY: 'auto',
                          padding: 16,
                          background: '#f5f5f5',
                          borderRadius: 8,
                        }}
                      >
                          {segments.map((seg) => {
                            const speaker = speakers.find((s) => s.id === seg.speaker_id)
                            const emotionLabel = String(seg.emotion_scores?.emotion ?? '')
                          const langLabel = seg.lang && seg.lang !== 'zh' && seg.lang !== 'unknown' ? seg.lang : null
                          const eventLabel = seg.event && seg.event !== 'speech' ? seg.event : null
                          return (
                            <div key={seg.id} style={{ marginBottom: 12 }}>
                              <Tooltip title={`${formatTime(seg.start_time)} - ${formatTime(seg.end_time)}`}>
                                <Tag color={speaker?.color || 'default'}>
                                  [{formatTime(seg.start_time)}] {seg.speaker_label || speaker?.label || '未知'}
                                </Tag>
                              </Tooltip>
                              {langLabel && <Tag color="blue">{langLabel}</Tag>}
                              {emotionLabel && <Tag color={emotionColor(emotionLabel)}>{emotionLabel}</Tag>}
                              {eventLabel && <Tag color="orange">{eventLabel}</Tag>}
                              <Text>{seg.transcript || '(无转录)'}</Text>
                            </div>
                          )
                        })}
                      </div>

                      <Divider />

                      <Title level={5}>完整文本</Title>
                      <Paragraph
                        style={{
                          background: '#fafafa',
                          padding: 16,
                          borderRadius: 8,
                          whiteSpace: 'pre-wrap',
                        }}
                      >
                        {transcriptData?.data?.full_text || '无转录文本'}
                      </Paragraph>
                    </div>
                  ) : (
                    <Empty description="暂无转录数据" />
                  )}
                </Card>
              ),
            },
            {
              key: 'timeline',
              label: (
                <span>
                  <ClockCircleOutlined /> 时间线
                </span>
              ),
              children: (
                <Card>
                  {segments.length > 0 ? (
                    <Timeline
                      mode="left"
                      items={segments.map((seg) => {
                        const speaker = speakers.find((s) => s.id === seg.speaker_id)
                        const emotionLabel = String(seg.emotion_scores?.emotion ?? '')
                        const langLabel = seg.lang && seg.lang !== 'zh' && seg.lang !== 'unknown' ? seg.lang : null
                        const eventLabel = seg.event && seg.event !== 'speech' ? seg.event : null
                        return {
                          color: speaker?.color || '#1890ff',
                          children: (
                            <div>
                              <Text strong>{formatTime(seg.start_time)}</Text>
                              <Tag color={speaker?.color}>{seg.speaker_label || speaker?.label}</Tag>
                              {langLabel && <Tag color="blue">{langLabel}</Tag>}
                              {emotionLabel && <Tag color={emotionColor(emotionLabel)}>{emotionLabel}</Tag>}
                              {eventLabel && <Tag color="orange">{eventLabel}</Tag>}
                              <br />
                              <Text type="secondary">{seg.transcript?.slice(0, 60)}...</Text>
                            </div>
                          ),
                        }
                      })}
                    />
                  ) : (
                    <Empty description="暂无时间线数据" />
                  )}
                </Card>
              ),
            },
            {
              key: 'speakers',
              label: (
                <span>
                  <TeamOutlined /> 说话人
                </span>
              ),
              children: (
                <Card>
                  {speakers.length > 0 ? (
                    <Space direction="vertical" style={{ width: '100%' }}>
                      {speakers.map((speaker) => {
                        const speakerSegments = segments.filter(
                          (s) => s.speaker_id === speaker.id
                        )
                        const totalTime = speakerSegments.reduce(
                          (acc, seg) => acc + (seg.end_time - seg.start_time),
                          0
                        )
                        return (
                          <Card key={speaker.id} size="small">
                            <Space>
                              <div
                                style={{
                                  width: 16,
                                  height: 16,
                                  borderRadius: '50%',
                                  backgroundColor: speaker.color,
                                }}
                              />
                              <Text strong>{speaker.label}</Text>
                            </Space>
                            <Descriptions column={2} style={{ marginTop: 8 }}>
                              <Descriptions.Item label="发言次数">
                                {speakerSegments.length} 次
                              </Descriptions.Item>
                              <Descriptions.Item label="发言时长">
                                {formatTime(totalTime)}
                              </Descriptions.Item>
                            </Descriptions>
                          </Card>
                        )
                      })}
                    </Space>
                  ) : (
                    <Empty description="暂无说话人数据" />
                  )}
                </Card>
              ),
            },
            {
              key: 'prosody',
              label: (
                <span>
                  <BarChartOutlined /> 韵律分析
                </span>
              ),
              children: (
                <Card>
                  {transcriptLoading ? (
                    <Spin tip="加载韵律数据..." />
                  ) : (
                    <ProsodyChart
                      segments={segments}
                    />
                  )}
                </Card>
              ),
            },
            {
              key: 'emotion',
              label: (
                <span>
                  <HeartOutlined /> 情绪分析
                </span>
              ),
              children: (
                <Card>
                  <Empty description="暂无情绪分析数据" />
                </Card>
              ),
            },
          ]}
        />
      )}
    </Space>
  )
}
