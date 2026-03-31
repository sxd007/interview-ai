import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Card,
  Button,
  Modal,
  Form,
  Input,
  Tag,
  Table,
  message,
  Descriptions,
  Space,
  Upload,
  Popconfirm,
} from 'antd'
import { PlusOutlined, ArrowLeftOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { voicePrintApi, VoicePrintSample, VoicePrintMatch } from '../services/api'

export function VoicePrintDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showEditModal, setShowEditModal] = useState(false)
  const [form] = Form.useForm()

  const { data: profile, isLoading: loadingProfile, refetch: refetchProfile } = useQuery({
    queryKey: ['voicePrintProfile', id],
    queryFn: () => voicePrintApi.getProfile(id!),
    enabled: !!id,
  })

  const { data: samples, refetch: refetchSamples } = useQuery({
    queryKey: ['voicePrintSamples', id],
    queryFn: () => voicePrintApi.listSamples(id!),
    enabled: !!id,
  })

  const { data: matches } = useQuery({
    queryKey: ['voicePrintMatches', id],
    queryFn: () => voicePrintApi.getMatches(id!),
    enabled: !!id,
  })

  const updateMutation = useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      voicePrintApi.updateProfile(id!, data),
    onSuccess: () => {
      message.success('更新成功')
      setShowEditModal(false)
      queryClient.invalidateQueries({ queryKey: ['voicePrintProfile', id] })
    },
    onError: () => {
      message.error('更新失败')
    },
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => voicePrintApi.addSample(id!, file),
    onSuccess: () => {
      message.success('上传成功')
      refetchSamples()
      refetchProfile()
    },
    onError: () => {
      message.error('上传失败')
    },
  })

  const deleteSampleMutation = useMutation({
    mutationFn: (sampleId: string) => voicePrintApi.deleteSample(sampleId),
    onSuccess: () => {
      message.success('删除成功')
      refetchSamples()
      refetchProfile()
    },
    onError: () => {
      message.error('删除失败')
    },
  })

  const getStatusTag = (status: string) => {
    const config: Record<string, { color: string; text: string }> = {
      pending: { color: 'warning', text: '处理中' },
      completed: { color: 'success', text: '完成' },
      failed: { color: 'error', text: '失败' },
      skipped: { color: 'default', text: '跳过' },
    }
    const c = config[status] || { color: 'default', text: status }
    return <Tag color={c.color}>{c.text}</Tag>
  }

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const sampleColumns: ColumnsType<VoicePrintSample> = [
    {
      title: '文件名',
      dataIndex: 'audio_path',
      render: (path: string) => path.split('/').pop() || path,
    },
    {
      title: '时长',
      dataIndex: 'duration',
      render: (dur?: number) => formatDuration(dur),
    },
    {
      title: '状态',
      dataIndex: 'status',
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '操作',
      render: (_, record) => (
        <Popconfirm
          title="确定删除此样本？"
          onConfirm={() => deleteSampleMutation.mutate(record.id)}
        >
          <a style={{ color: '#ff4d4f' }}>删除</a>
        </Popconfirm>
      ),
    },
  ]

  const matchColumns: ColumnsType<VoicePrintMatch> = [
    {
      title: '面试ID',
      dataIndex: 'interview_id',
      render: (id?: string) => id ? `${id.slice(0, 8)}...` : '-',
    },
    {
      title: '说话人',
      dataIndex: 'speaker_label',
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      render: (v: number) => `${(v * 100).toFixed(1)}%`,
    },
    {
      title: '匹配时间',
      dataIndex: 'matched_at',
      render: (t: string) => new Date(t).toLocaleString(),
    },
  ]

  const handleUpload = (file: File) => {
    uploadMutation.mutate(file)
    return false
  }

  const handleEdit = async () => {
    try {
      const values = await form.validateFields()
      updateMutation.mutate(values)
    } catch {}
  }

  if (loadingProfile) {
    return <div style={{ textAlign: 'center', padding: 48 }}>加载中...</div>
  }

  if (!profile?.data) {
    return (
      <div>
        <div style={{ textAlign: 'center', padding: 48 }}>档案不存在</div>
        <Link to="/voice-prints" style={{ display: 'block', textAlign: 'center' }}>
          返回列表
        </Link>
      </div>
    )
  }

  const p = profile.data

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/voice-prints')} style={{ marginBottom: 16 }}>
        返回列表
      </Button>

      <Card title={p.name} extra={<Button onClick={() => { form.setFieldsValue({ name: p.name, description: p.description }); setShowEditModal(true) }}>编辑</Button>}>
        <Descriptions bordered column={2}>
          <Descriptions.Item label="样本数量">{p.sample_count}</Descriptions.Item>
          <Descriptions.Item label="状态">
            {p.status === 'pending' && <Tag color="warning">待训练</Tag>}
            {p.status === 'ready' && <Tag color="success">已就绪</Tag>}
            {p.status === 'trained' && <Tag color="processing">已优化</Tag>}
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">{new Date(p.created_at).toLocaleString()}</Descriptions.Item>
          <Descriptions.Item label="更新时间">{new Date(p.updated_at).toLocaleString()}</Descriptions.Item>
          <Descriptions.Item label="描述" span={2}>{p.description || '-'}</Descriptions.Item>
        </Descriptions>
        {p.embedding && (
          <div style={{ marginTop: 16, padding: 8, background: '#f6ffed', borderRadius: 4 }}>
            <span style={{ color: '#52c41a' }}>✓ 声纹特征已提取</span>
            <span style={{ color: '#888', marginLeft: 8 }}>维度: {p.embedding.length}</span>
          </div>
        )}
      </Card>

      <Card title="音频样本" style={{ marginTop: 16 }}>
        <Space style={{ marginBottom: 16 }}>
          <Upload beforeUpload={handleUpload} showUploadList={false} accept="audio/*">
            <Button type="primary" icon={<PlusOutlined />} loading={uploadMutation.isPending}>
              上传音频
            </Button>
          </Upload>
        </Space>
        <Table
          columns={sampleColumns}
          dataSource={samples?.data || []}
          rowKey="id"
          pagination={false}
          locale={{ emptyText: '暂无音频样本' }}
        />
      </Card>

      <Card title="匹配记录" style={{ marginTop: 16 }}>
        <Table
          columns={matchColumns}
          dataSource={matches?.data || []}
          rowKey="id"
          pagination={false}
          locale={{ emptyText: '暂无匹配记录' }}
        />
      </Card>

      <Modal
        title="编辑声纹档案"
        open={showEditModal}
        onCancel={() => setShowEditModal(false)}
        onOk={handleEdit}
        confirmLoading={updateMutation.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}