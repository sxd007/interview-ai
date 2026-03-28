import { Link } from 'react-router-dom'
import { Card, Typography, Space, Row, Col, Statistic, Button, List } from 'antd'
import {
  UploadOutlined,
  AudioOutlined,
  VideoCameraOutlined,
  TeamOutlined,
  FileTextOutlined,
  SafetyOutlined,
} from '@ant-design/icons'

const { Title, Text, Paragraph } = Typography

export function HomePage() {
  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card>
        <Title level={2}>访谈视频智能分析系统</Title>
        <Paragraph>
          欢迎使用 Interview AI - 专业的多模态访谈分析工具，支持心理研究、合规调查等场景
        </Paragraph>
      </Card>

      <Row gutter={16}>
        <Col span={6}>
          <Card hoverable>
            <Statistic
              title="音频处理"
              value={4}
              prefix={<AudioOutlined />}
              suffix="项"
            />
            <Paragraph type="secondary" style={{ marginTop: 8, fontSize: 12 }}>
              STT转录、说话人分离、韵律分析、情绪识别
            </Paragraph>
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable>
            <Statistic
              title="视频分析"
              value={3}
              prefix={<VideoCameraOutlined />}
              suffix="项"
            />
            <Paragraph type="secondary" style={{ marginTop: 8, fontSize: 12 }}>
              面部分析、动作单元、微表情检测
            </Paragraph>
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable>
            <Statistic
              title="说话人识别"
              value={1}
              prefix={<TeamOutlined />}
              suffix="项"
            />
            <Paragraph type="secondary" style={{ marginTop: 8, fontSize: 12 }}>
              自动区分不同说话人
            </Paragraph>
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable>
            <Statistic
              title="分析报告"
              value={2}
              prefix={<FileTextOutlined />}
              suffix="份"
            />
            <Paragraph type="secondary" style={{ marginTop: 8, fontSize: 12 }}>
              结构化JSON、Markdown摘要
            </Paragraph>
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="功能概览" style={{ height: '100%' }}>
            <List
              size="small"
              bordered
              dataSource={[
                {
                  title: '音频分析',
                  items: [
                    '语音转文字 (STT) - Whisper 大模型',
                    '说话人分离 - pyannote.audio',
                    '音频降噪 - Demucs',
                    '韵律分析 - 基频、能量、语速',
                    '声音情绪识别 - 多分类情绪分析',
                  ],
                },
                {
                  title: '视频分析',
                  items: [
                    '关键帧提取 - PySceneDetect',
                    '面部关键点 - MediaPipe (468点)',
                    '动作单元 (AU) - FACS标准',
                    '面部情绪识别',
                  ],
                },
              ]}
              renderItem={(item) => (
                <List.Item>
                  <Text strong>{item.title}</Text>
                  <ul style={{ margin: '8px 0 0 0', paddingLeft: 20 }}>
                    {item.items.map((i, idx) => (
                      <li key={idx} style={{ color: '#666' }}>
                        {i}
                      </li>
                    ))}
                  </ul>
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="快速开始" style={{ height: '100%' }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Link to="/upload">
                <Button type="primary" size="large" block icon={<UploadOutlined />}>
                  上传访谈视频
                </Button>
              </Link>
              <Link to="/interviews">
                <Button size="large" block icon={<VideoCameraOutlined />}>
                  查看访谈列表
                </Button>
              </Link>
            </Space>
            <div style={{ marginTop: 24 }}>
              <Space>
                <SafetyOutlined style={{ fontSize: 20, color: '#52c41a' }} />
                <Text strong>隐私保护</Text>
              </Space>
              <Paragraph type="secondary">
                所有数据均在本地处理，不会上传到云端，保护访谈隐私安全。
              </Paragraph>
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="技术架构">
        <Row gutter={16}>
          <Col span={8}>
            <Text strong>推理引擎</Text>
            <Paragraph type="secondary">
              PyTorch (MPS/CUDA) + faster-whisper + pyannote.audio
            </Paragraph>
          </Col>
          <Col span={8}>
            <Text strong>后端框架</Text>
            <Paragraph type="secondary">FastAPI + SQLAlchemy</Paragraph>
          </Col>
          <Col span={8}>
            <Text strong>前端框架</Text>
            <Paragraph type="secondary">React + Ant Design + Recharts</Paragraph>
          </Col>
        </Row>
      </Card>
    </Space>
  )
}
