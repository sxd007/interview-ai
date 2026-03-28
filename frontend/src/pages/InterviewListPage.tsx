import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Table,
  Card,
  Typography,
  Space,
  Tag,
  Button,
  Input,
  Dropdown,
  Modal,
  message,
  Tooltip,
  Badge,
  Empty,
} from 'antd'
import {
  SearchOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  MoreOutlined,
  VideoCameraOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { interviewApi, type Interview } from '../services/api'

const { Title } = Typography

const getStatusConfig = (status: string) => {
  const configs: Record<string, { color: string; text: string }> = {
    pending: { color: 'default', text: '等待中' },
    processing: { color: 'processing', text: '处理中' },
    completed: { color: 'success', text: '已完成' },
    failed: { color: 'error', text: '失败' },
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

export function InterviewListPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchText, setSearchText] = useState('')

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['interviews'],
    queryFn: () => interviewApi.list({ limit: 100 }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => interviewApi.delete(id),
    onSuccess: () => {
      message.success('删除成功')
      queryClient.invalidateQueries({ queryKey: ['interviews'] })
    },
    onError: () => {
      message.error('删除失败')
    },
  })

  const processMutation = useMutation({
    mutationFn: (id: string) => interviewApi.process(id),
    onSuccess: () => {
      message.success('处理已启动')
      queryClient.invalidateQueries({ queryKey: ['interviews'] })
    },
    onError: () => {
      message.error('启动处理失败')
    },
  })

  const interviews = data?.data?.interviews || []

  const filteredInterviews = interviews.filter(
    (interview) =>
      interview.filename.toLowerCase().includes(searchText.toLowerCase())
  )

  const handleDelete = (record: Interview) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除访谈 "${record.filename}" 吗？此操作不可恢复。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => deleteMutation.mutate(record.id),
    })
  }

  const getActionItems = (record: Interview): MenuProps['items'] => [
    {
      key: 'view',
      label: '查看详情',
      icon: <VideoCameraOutlined />,
      onClick: () => navigate(`/interviews/${record.id}`),
    },
    ...(record.status !== 'completed'
      ? [
          {
            key: 'process',
            label: '开始处理',
            icon: <PlayCircleOutlined />,
            onClick: () => processMutation.mutate(record.id),
          },
        ]
      : []),
    { type: 'divider' as const },
    {
      key: 'delete',
      label: '删除',
      icon: <DeleteOutlined />,
      danger: true,
      onClick: () => handleDelete(record),
    },
  ]

  const columns: ColumnsType<Interview> = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
      render: (filename, record) => (
        <Button type="link" onClick={() => navigate(`/interviews/${record.id}`)}>
          {filename}
        </Button>
      ),
    },
    {
      title: '时长',
      dataIndex: 'duration',
      key: 'duration',
      width: 100,
      render: (duration) => (duration ? formatTime(duration) : '-'),
    },
    {
      title: '分辨率',
      dataIndex: 'resolution',
      key: 'resolution',
      width: 120,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status) => {
        const config = getStatusConfig(status)
        return <Tag color={config.color}>{config.text}</Tag>
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (date) => new Date(date).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_, record) => (
        <Space size="small">
          {record.status === 'pending' || record.status === 'failed' ? (
            <Tooltip title="开始处理">
              <Button
                type="text"
                size="small"
                icon={processMutation.isPending ? <ReloadOutlined spin /> : <PlayCircleOutlined />}
                onClick={() => processMutation.mutate(record.id)}
                disabled={processMutation.isPending}
              />
            </Tooltip>
          ) : null}
          <Dropdown menu={{ items: getActionItems(record) }} trigger={['click']}>
            <Button type="text" size="small" icon={<MoreOutlined />} />
          </Dropdown>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card
        title={
          <Space>
            <Title level={3} style={{ margin: 0 }}>访谈列表</Title>
            <Badge count={filteredInterviews.length} showZero color="#1890ff" />
          </Space>
        }
        extra={
          <Space>
            <Input
              placeholder="搜索文件名..."
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              style={{ width: 200 }}
              allowClear
            />
            <Button onClick={() => refetch()}>刷新</Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={filteredInterviews}
          rowKey="id"
          loading={isLoading}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
          }}
          locale={{
            emptyText: (
              <Empty
                description="暂无访谈记录"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              >
                <Button type="primary" onClick={() => navigate('/upload')}>
                  上传视频
                </Button>
              </Empty>
            ),
          }}
        />
      </Card>
    </Space>
  )
}
