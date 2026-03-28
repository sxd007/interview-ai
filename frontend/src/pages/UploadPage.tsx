import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Card, Typography, Upload, Space, message, Progress, Alert,
  Switch, Tooltip, Divider, Button, Tag, Radio,
} from 'antd'
import {
  InboxOutlined, CheckCircleOutlined, VideoCameraOutlined,
  ScissorOutlined, InfoCircleOutlined,
} from '@ant-design/icons'
import type { UploadProps } from 'antd'
import { interviewApi } from '../services/api'

const { Title, Text, Paragraph } = Typography
const { Dragger } = Upload

const formatDuration = (seconds: number) => {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}小时${m}分钟`
  if (m > 0) return `${m}分${s}秒`
  return `${s}秒`
}

const formatSize = (bytes: number) => {
  if (bytes > 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

interface VideoInfo {
  id: string
  filename: string
  duration: number
  size: number
}

export function UploadPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadComplete, setUploadComplete] = useState(false)
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null)
  const [splitEnabled, setSplitEnabled] = useState(false)
  const [globalDiarization, setGlobalDiarization] = useState(false)
  const [diarizationEngine, setDiarizationEngine] = useState<'pyannote' | 'funasr'>('pyannote')
  const [processingStarted, setProcessingStarted] = useState(false)

  useEffect(() => {
    if (videoInfo) {
      setSplitEnabled(videoInfo.duration > 1800)
    }
  }, [videoInfo])

  const uploadMutation = useMutation({
    mutationFn: (file: File) => interviewApi.upload(file, setUploadProgress),
    onSuccess: (response) => {
      setUploadComplete(true)
      message.success('视频上传成功！')
      const { id, filename, duration } = response.data
      setVideoInfo({
        id,
        filename,
        duration: duration || 0,
        size: 0,
      })
    },
    onError: () => {
      message.error('上传失败，请重试')
      setUploadProgress(0)
    },
  })

  const processMutation = useMutation({
    mutationFn: (config: any) => interviewApi.process(videoInfo!.id, config),
    onSuccess: () => {
      setProcessingStarted(true)
      message.success('基础解析已启动，Chunk 完成后可进入人工审核')
      queryClient.invalidateQueries({ queryKey: ['interviews'] })
      setTimeout(() => navigate(`/interviews/${videoInfo!.id}`), 1500)
    },
    onError: (e: any) => {
      message.error(e?.response?.data?.detail || '启动失败')
    },
  })

  const props: UploadProps = {
    name: 'file',
    multiple: false,
    accept: 'video/*',
    showUploadList: false,
    disabled: uploadMutation.isPending,
    beforeUpload: (file) => {
      const isVideo = file.type.startsWith('video/')
      if (!isVideo) { message.error('只能上传视频文件'); return false }
      const isLt2G = file.size / 1024 / 1024 / 1024 < 2
      if (!isLt2G) { message.error('文件大小不能超过 2GB'); return false }
      if (videoInfo) setVideoInfo(prev => prev ? { ...prev, size: file.size } : null)
      uploadMutation.mutate(file)
      return false
    },
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%', maxWidth: 900 }}>

      <Card>
        <Title level={3}>上传访谈视频</Title>
        <Paragraph type="secondary">
          支持 MP4, MOV, AVI, MKV 格式，最大 2GB
        </Paragraph>
      </Card>

      <Card>
        {!uploadComplete ? (
          <>
            <Dragger {...props} style={{ padding: 40 }}>
              <p className="ant-upload-drag-icon">
                {uploadMutation.isPending ? <Progress type="circle" percent={uploadProgress} size={40} /> : <InboxOutlined />}
              </p>
              <p className="ant-upload-text">
                {uploadMutation.isPending ? '正在上传...' : '点击或拖拽视频文件到此区域上传'}
              </p>
              <p className="ant-upload-hint">
                {uploadMutation.isPending ? `${uploadProgress}%` : '支持大文件上传'}
              </p>
            </Dragger>
            {uploadProgress > 0 && uploadProgress < 100 && (
              <Progress percent={uploadProgress} status="active" style={{ marginTop: 16 }} />
            )}
          </>
        ) : !videoInfo ? null : (
          <>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 24 }}>
              <VideoCameraOutlined style={{ fontSize: 48, color: '#1890ff', marginTop: 4 }} />
              <div style={{ flex: 1 }}>
                <Text strong style={{ fontSize: 16 }}>{videoInfo.filename}</Text>
                <div style={{ marginTop: 8, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                  {videoInfo.duration > 0 && (
                    <Tag icon={<InfoCircleOutlined />} color="blue">
                      时长: {formatDuration(videoInfo.duration)}
                    </Tag>
                  )}
                  {videoInfo.size > 0 && (
                    <Tag>大小: {formatSize(videoInfo.size)}</Tag>
                  )}
                  <Tag color={videoInfo.duration > 1800 ? 'orange' : 'default'}>
                    {videoInfo.duration > 1800 ? '建议分割处理' : '可一次性处理'}
                  </Tag>
                </div>
              </div>
            </div>

            <Divider />

            <div style={{ marginBottom: 16 }}>
              <Space align="center">
                <Switch checked={splitEnabled} onChange={setSplitEnabled} />
                <Tooltip title="将视频分割为 10 分钟片段并行处理，加快处理速度。适用于 30 分钟以上的长视频。">
                  <Text strong>
                    <ScissorOutlined style={{ marginRight: 6 }} />
                    分割视频并行处理
                  </Text>
                </Tooltip>
              </Space>
              <div style={{ marginTop: 6 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {splitEnabled
                    ? `视频将分割为 ${Math.ceil(videoInfo.duration / 600)} 个片段。第一个片段完成后即可开始人工审核，无需等待全部完成。`
                    : videoInfo.duration > 1800
                      ? '提示：您的视频较长，建议开启分割处理以加快速度。'
                      : '视频较短，无需分割。'
                  }
                </Text>
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <div style={{ marginBottom: 8 }}>
                <Text strong>
                  <InfoCircleOutlined style={{ marginRight: 6 }} />
                  说话人分离引擎
                </Text>
              </div>
              <Radio.Group 
                value={diarizationEngine} 
                onChange={e => setDiarizationEngine(e.target.value)}
                optionType="button"
                buttonStyle="solid"
              >
                <Radio.Button value="pyannote">pyannote（推荐，准确度高）</Radio.Button>
                <Radio.Button value="funasr">FunASR 内置（处理快）</Radio.Button>
              </Radio.Group>
              <div style={{ marginTop: 6 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {diarizationEngine === 'pyannote' 
                    ? '使用 pyannote 模型进行说话人分离，推荐使用，准确度更高。'
                    : '使用 FunASR 内置说话人分离，处理速度更快，但准确度可能不如 pyannote。'
                  }
                </Text>
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <Space align="center">
                <Switch checked={globalDiarization} onChange={setGlobalDiarization} />
                <Tooltip title="在处理前先对整个视频进行说话人分离，确保说话人身份在所有 Chunk 间保持一致。需 GPU 加速，处理时间较长。">
                  <Text strong>
                    全局说话人分离
                  </Text>
                </Tooltip>
              </Space>
              <div style={{ marginTop: 6 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {globalDiarization
                    ? '启用后将先对整个视频进行说话人识别，再处理各 Chunk。说话人身份跨 Chunk 一致，但处理时间较长。'
                    : '默认每个 Chunk 独立进行说话人识别，处理更快，但不同 Chunk 间的说话人身份可能不同。'
                  }
                </Text>
              </div>
            </div>

            {!processingStarted ? (
              <Button
                type="primary"
                size="large"
                icon={<VideoCameraOutlined />}
                onClick={() => processMutation.mutate({
                  chunk_enabled: splitEnabled,
                  chunk_duration: 600,
                  speaker_diarization: globalDiarization,
                  diarization_engine: diarizationEngine,
                })}
                loading={processMutation.isPending}
                block
              >
                开始基础解析
              </Button>
            ) : (
              <div style={{ textAlign: 'center', padding: 16 }}>
                <CheckCircleOutlined style={{ fontSize: 40, color: '#52c41a' }} />
                <div style={{ marginTop: 8 }}>基础解析已启动</div>
              </div>
            )}
          </>
        )}
      </Card>

      <Card title="处理流程说明">
        <Space direction="vertical" style={{ width: '100%' }}>
          <Alert message="基础解析（自动）" type="info" showIcon />
          <div style={{ paddingLeft: 24 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text>① 音频提取 → ② 降噪 → ③ 说话人识别 → ④ 语音转文字 → ⑤ 人脸分析</Text>
              <Text type="secondary">每个 Chunk 完成后可立即进入人工审核，无需等待全部完成</Text>
            </Space>
          </div>
          <Alert message="人工审核纠错（人工）" type="warning" showIcon />
          <div style={{ paddingLeft: 24 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text>说话人合并 / 段落分割合并 / 时间戳修正 / 文本修正</Text>
              <Text type="secondary">所有 Chunk 审核完成后，确认进入深度分析</Text>
            </Space>
          </div>
          <Alert message="深度分析（自动）" type="info" showIcon />
          <div style={{ paddingLeft: 24 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text>韵律分析 → 情绪识别 → 情绪融合 + 报告生成</Text>
              <Text type="secondary">纠错完成确认后自动执行</Text>
            </Space>
          </div>
        </Space>
      </Card>

      <Card title="注意事项">
        <Space direction="vertical">
          <Text>• 视频分析可能需要较长时间，请耐心等待</Text>
          <Text>• 开启分割处理可加快长视频的分析速度</Text>
          <Text>• 所有数据均在本地处理，保护隐私</Text>
        </Space>
      </Card>
    </Space>
  )
}
