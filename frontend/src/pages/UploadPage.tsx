import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Card, Typography, Upload, Space, message, Progress, Alert,
  Switch, Tooltip, Divider, Button, Tag, Radio, Collapse, Slider, Select, InputNumber,
} from 'antd'
import {
  InboxOutlined, CheckCircleOutlined, VideoCameraOutlined,
  ScissorOutlined, InfoCircleOutlined, SettingOutlined,
} from '@ant-design/icons'
import type { UploadProps } from 'antd'
import { interviewApi } from '../services/api'

const { Title, Text, Paragraph } = Typography
const { Dragger } = Upload
const { Panel } = Collapse

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

interface DiarizationConfig {
  segmentation_onset: number
  segmentation_duration: number
  min_duration_off: number
  min_duration_on: number
  clustering_threshold: number
  min_cluster_size: number
  gap_threshold: number
  min_segment_duration: number
}

interface STTConfig {
  language: string
  use_itn: boolean
  vad_enabled: boolean
  spk_enabled: boolean
  batch_size_s: number
  merge_vad: boolean
  merge_length_s: number
}

const defaultDiarizationConfig: DiarizationConfig = {
  segmentation_onset: 0.3,
  segmentation_duration: 5.0,
  min_duration_off: 0.3,
  min_duration_on: 0.3,
  clustering_threshold: 0.715,
  min_cluster_size: 15,
  gap_threshold: 0.5,
  min_segment_duration: 0.5,
}

const defaultSTTConfig: STTConfig = {
  language: 'auto',
  use_itn: true,
  vad_enabled: true,
  spk_enabled: false,
  batch_size_s: 300,
  merge_vad: true,
  merge_length_s: 15,
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
  const [sttEngine, setSttEngine] = useState<'faster-whisper' | 'sensevoice'>('faster-whisper')
  const [processingStarted, setProcessingStarted] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [diarizationConfig, setDiarizationConfig] = useState<DiarizationConfig>(defaultDiarizationConfig)
  const [sttConfig, setSTTConfig] = useState<STTConfig>(defaultSTTConfig)

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

  const handleStartProcess = () => {
    const config: any = {
      chunk_enabled: splitEnabled,
      chunk_duration: 600,
      speaker_diarization: globalDiarization,
      diarization_engine: diarizationEngine,
      stt_engine: sttEngine,
    }
    
    if (showAdvanced) {
      config.diarization_config = diarizationConfig
      config.stt_config = sttConfig
    }
    
    processMutation.mutate(config)
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
              <div style={{ marginBottom: 8 }}>
                <Text strong>
                  <InfoCircleOutlined style={{ marginRight: 6 }} />
                  语音转文字引擎
                </Text>
              </div>
              <Radio.Group 
                value={sttEngine} 
                onChange={e => setSttEngine(e.target.value)}
                optionType="button"
                buttonStyle="solid"
              >
                <Radio.Button value="faster-whisper">Whisper (OpenAI)（推荐）</Radio.Button>
                <Radio.Button value="sensevoice">FunASR (SenseVoice)</Radio.Button>
              </Radio.Group>
              <div style={{ marginTop: 6 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {sttEngine === 'faster-whisper' 
                    ? '使用 OpenAI Whisper 模型进行语音识别，支持多语言，准确度高。'
                    : '使用阿里 FunASR SenseVoice 模型，支持情绪识别等高级功能。'
                  }
                </Text>
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <Space align="center">
                <Switch checked={globalDiarization} onChange={setGlobalDiarization} />
                <Tooltip title="在处理前先对整个视频进行说话人分离，确保说话人身份在所有 Chunk 间保持一致。适用于长视频分割处理场景。">
                  <Text strong>
                    全局说话人分离
                  </Text>
                </Tooltip>
              </Space>
              <div style={{ marginTop: 6 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {globalDiarization
                    ? '启用后将先对整个视频进行说话人识别，再处理各 Chunk。说话人身份跨 Chunk 一致，但处理时间较长。'
                    : '每个 Chunk 独立进行说话人识别（使用上方选择的引擎），处理更快，但不同 Chunk 间的说话人身份可能不同。'
                  }
                </Text>
              </div>
            </div>

            <Divider />

            <Collapse 
              activeKey={showAdvanced ? ['1'] : []}
              onChange={(keys) => setShowAdvanced(keys.includes('1'))}
              style={{ marginBottom: 16 }}
            >
              <Panel 
                header={
                  <Space>
                    <SettingOutlined />
                    <Text strong>高级选项</Text>
                    <Tag color={showAdvanced ? 'blue' : 'default'}>
                      {showAdvanced ? '已启用自定义参数' : '使用默认参数'}
                    </Tag>
                  </Space>
                }
                key="1"
              >
                <Alert 
                  message="高级参数调整" 
                  description="以下参数影响说话人分离和语音识别的质量。如不确定，建议保持默认值。"
                  type="info" 
                  showIcon 
                  style={{ marginBottom: 16 }}
                />

                <Card size="small" title="说话人分离参数" style={{ marginBottom: 16 }}>
                  <Space direction="vertical" style={{ width: '100%' }} size="middle">
                    <div>
                      <div style={{ marginBottom: 4 }}>
                        <Tooltip title="值越低越容易检测到语音开始，但可能误检噪音。噪音环境建议提高到 0.4-0.5。">
                          <Text>语音起始检测阈值 <InfoCircleOutlined style={{ color: '#999', marginLeft: 4 }} /></Text>
                        </Tooltip>
                      </div>
                      <Slider
                        min={0.1}
                        max={0.9}
                        step={0.05}
                        value={diarizationConfig.segmentation_onset}
                        onChange={(v) => setDiarizationConfig(prev => ({ ...prev, segmentation_onset: v }))}
                        marks={{ 0.1: '0.1', 0.3: '默认', 0.5: '0.5', 0.9: '0.9' }}
                      />
                    </div>

                    <div>
                      <div style={{ marginBottom: 4 }}>
                        <Tooltip title="值越高，越不容易将同一人分成多个说话人。同一人被拆分时建议提高到 0.75-0.85。">
                          <Text>说话人聚类阈值 <InfoCircleOutlined style={{ color: '#999', marginLeft: 4 }} /></Text>
                        </Tooltip>
                      </div>
                      <Slider
                        min={0.5}
                        max={0.9}
                        step={0.05}
                        value={diarizationConfig.clustering_threshold}
                        onChange={(v) => setDiarizationConfig(prev => ({ ...prev, clustering_threshold: v }))}
                        marks={{ 0.5: '0.5', 0.715: '默认', 0.85: '0.85', 0.9: '0.9' }}
                      />
                    </div>

                    <div>
                      <div style={{ marginBottom: 4 }}>
                        <Tooltip title="值越大，越不容易产生虚假说话人。说话人数量过多时建议提高到 20-30。">
                          <Text>最小聚类样本数 <InfoCircleOutlined style={{ color: '#999', marginLeft: 4 }} /></Text>
                        </Tooltip>
                      </div>
                      <InputNumber
                        min={5}
                        max={50}
                        value={diarizationConfig.min_cluster_size}
                        onChange={(v) => setDiarizationConfig(prev => ({ ...prev, min_cluster_size: v || 15 }))}
                        style={{ width: '100%' }}
                      />
                    </div>

                    <div>
                      <div style={{ marginBottom: 4 }}>
                        <Tooltip title="小于此值的片段会被过滤掉。短句丢失时建议降低到 0.15-0.2。">
                          <Text>说话片段最小长度(秒) <InfoCircleOutlined style={{ color: '#999', marginLeft: 4 }} /></Text>
                        </Tooltip>
                      </div>
                      <Slider
                        min={0.1}
                        max={1.0}
                        step={0.05}
                        value={diarizationConfig.min_duration_on}
                        onChange={(v) => setDiarizationConfig(prev => ({ ...prev, min_duration_on: v }))}
                        marks={{ 0.1: '0.1', 0.3: '默认', 0.5: '0.5', 1.0: '1.0' }}
                      />
                    </div>

                    <div>
                      <div style={{ marginBottom: 4 }}>
                        <Tooltip title="同一说话人间隙小于此值会被合并。碎片化严重时建议提高到 0.8-1.0。">
                          <Text>后处理合并间隙阈值(秒) <InfoCircleOutlined style={{ color: '#999', marginLeft: 4 }} /></Text>
                        </Tooltip>
                      </div>
                      <Slider
                        min={0.1}
                        max={2.0}
                        step={0.1}
                        value={diarizationConfig.gap_threshold}
                        onChange={(v) => setDiarizationConfig(prev => ({ ...prev, gap_threshold: v }))}
                        marks={{ 0.1: '0.1', 0.5: '默认', 1.0: '1.0', 2.0: '2.0' }}
                      />
                    </div>
                  </Space>
                </Card>

                <Card size="small" title="语音转文字参数">
                  <Space direction="vertical" style={{ width: '100%' }} size="middle">
                    <div>
                      <div style={{ marginBottom: 4 }}>
                        <Tooltip title="指定语言可提高识别准确率。中文访谈建议选择 'zh'。">
                          <Text>识别语言 <InfoCircleOutlined style={{ color: '#999', marginLeft: 4 }} /></Text>
                        </Tooltip>
                      </div>
                      <Select
                        value={sttConfig.language}
                        onChange={(v) => setSTTConfig(prev => ({ ...prev, language: v }))}
                        style={{ width: '100%' }}
                        options={[
                          { value: 'auto', label: '自动检测' },
                          { value: 'zh', label: '中文' },
                          { value: 'en', label: '英文' },
                          { value: 'ja', label: '日文' },
                          { value: 'ko', label: '韩文' },
                        ]}
                      />
                    </div>

                    <div>
                      <div style={{ marginBottom: 4 }}>
                        <Tooltip title="将'一百二十三'转为'123'等。正式报告建议开启。">
                          <Text>逆文本标准化 <InfoCircleOutlined style={{ color: '#999', marginLeft: 4 }} /></Text>
                        </Tooltip>
                      </div>
                      <Switch
                        checked={sttConfig.use_itn}
                        onChange={(v) => setSTTConfig(prev => ({ ...prev, use_itn: v }))}
                      />
                    </div>

                    <div>
                      <div style={{ marginBottom: 4 }}>
                        <Tooltip title="自动过滤静音段，提高效率。长静音段落建议开启。">
                          <Text>语音活动检测(VAD) <InfoCircleOutlined style={{ color: '#999', marginLeft: 4 }} /></Text>
                        </Tooltip>
                      </div>
                      <Switch
                        checked={sttConfig.vad_enabled}
                        onChange={(v) => setSTTConfig(prev => ({ ...prev, vad_enabled: v }))}
                      />
                    </div>

                    <div>
                      <div style={{ marginBottom: 4 }}>
                        <Tooltip title="降低内存占用，适合低配机器。高配机器可提高到 400-500。">
                          <Text>批处理时长(秒) <InfoCircleOutlined style={{ color: '#999', marginLeft: 4 }} /></Text>
                        </Tooltip>
                      </div>
                      <InputNumber
                        min={60}
                        max={600}
                        value={sttConfig.batch_size_s}
                        onChange={(v) => setSTTConfig(prev => ({ ...prev, batch_size_s: v || 300 }))}
                        style={{ width: '100%' }}
                      />
                    </div>
                  </Space>
                </Card>

                <div style={{ marginTop: 12 }}>
                  <Button 
                    size="small" 
                    onClick={() => {
                      setDiarizationConfig(defaultDiarizationConfig)
                      setSTTConfig(defaultSTTConfig)
                    }}
                  >
                    重置为默认值
                  </Button>
                </div>
              </Panel>
            </Collapse>

            {!processingStarted ? (
              <Button
                type="primary"
                size="large"
                icon={<VideoCameraOutlined />}
                onClick={handleStartProcess}
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
