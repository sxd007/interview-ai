import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Card,
  Button,
  Modal,
  Form,
  Input,
  message,
  Empty,
  Tag,
  Popconfirm,
  Row,
  Col,
} from 'antd'
import { PlusOutlined, UserOutlined } from '@ant-design/icons'
import { voicePrintApi } from '../services/api'

export function VoicePrintListPage() {
  const queryClient = useQueryClient()
  const [showModal, setShowModal] = useState(false)
  const [form] = Form.useForm()

  const { data: profiles, isLoading } = useQuery({
    queryKey: ['voicePrintProfiles'],
    queryFn: () => voicePrintApi.listProfiles({ limit: 100 }),
  })

  const createMutation = useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      voicePrintApi.createProfile(data),
    onSuccess: () => {
      message.success('创建成功')
      setShowModal(false)
      form.resetFields()
      queryClient.invalidateQueries({ queryKey: ['voicePrintProfiles'] })
    },
    onError: () => {
      message.error('创建失败')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => voicePrintApi.deleteProfile(id),
    onSuccess: () => {
      message.success('删除成功')
      queryClient.invalidateQueries({ queryKey: ['voicePrintProfiles'] })
    },
    onError: () => {
      message.error('删除失败')
    },
  })

  const getStatusTag = (status: string) => {
    const config: Record<string, { color: string; text: string }> = {
      pending: { color: 'warning', text: '待训练' },
      ready: { color: 'success', text: '已就绪' },
      trained: { color: 'processing', text: '已优化' },
    }
    const c = config[status] || { color: 'default', text: status }
    return <Tag color={c.color}>{c.text}</Tag>
  }

  const handleCreate = async () => {
    try {
      const values = await form.validateFields()
      createMutation.mutate(values)
    } catch {}
  }

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <h2>声纹库管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowModal(true)}>
          新建人员
        </Button>
      </div>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}>加载中...</div>
      ) : !profiles?.data?.length ? (
        <Empty description="暂无声纹档案，请创建第一个人员" />
      ) : (
        <Row gutter={16}>
          {profiles.data.map((profile) => (
            <Col key={profile.id} xs={24} sm={12} md={8} lg={6}>
              <Card
                hoverable
                actions={[
                  <Link key="detail" to={`/voice-prints/${profile.id}`}>
                    查看详情
                  </Link>,
                  <Popconfirm
                    key="delete"
                    title="确定删除此声纹档案？"
                    onConfirm={() => deleteMutation.mutate(profile.id)}
                  >
                    <a style={{ color: '#ff4d4f' }}>删除</a>
                  </Popconfirm>,
                ]}
              >
                <Card.Meta
                  avatar={<UserOutlined style={{ fontSize: 32, color: '#1890ff' }} />}
                  title={
                    <Link to={`/voice-prints/${profile.id}`}>{profile.name}</Link>
                  }
                  description={
                    <div>
                      {profile.description && (
                        <div style={{ marginBottom: 8 }}>{profile.description}</div>
                      )}
                      <div>样本数: {profile.sample_count}</div>
                      {getStatusTag(profile.status)}
                    </div>
                  }
                />
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title="新建声纹档案"
        open={showModal}
        onCancel={() => {
          setShowModal(false)
          form.resetFields()
        }}
        onOk={handleCreate}
        confirmLoading={createMutation.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
            <Input placeholder="请输入姓名" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="可选描述" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}