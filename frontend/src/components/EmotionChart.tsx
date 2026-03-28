import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { Card, Typography, Space, Row, Col, Statistic } from 'antd'
import { EmotionNode, EmotionSummary, SignalItem } from '../services/api'

const { Text } = Typography

const EMOTION_COLORS: Record<string, string> = {
  neutral: '#909399',
  happy: '#67C23A',
  sad: '#409EFF',
  angry: '#F56C6C',
  fearful: '#9C27B0',
  disgust: '#795548',
  surprised: '#FF9800',
  anxious: '#E91E63',
}

const EMOTION_LABELS: Record<string, string> = {
  neutral: '中性',
  happy: '开心',
  sad: '悲伤',
  angry: '愤怒',
  fearful: '恐惧',
  disgust: '厌恶',
  surprised: '惊讶',
  anxious: '焦虑',
}

interface Props {
  summary: EmotionSummary
  signals: SignalItem[]
  emotionNodes?: EmotionNode[]
}

export function EmotionChart({ summary, signals }: Props) {
  const pieData = Object.entries(summary.emotion_distribution).map(([name, value]) => ({
    name: EMOTION_LABELS[name] || name,
    value: Math.round(value * 1000) / 10,
    raw: name,
  }))

  const signalRows = signals.slice(0, 20)

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Row gutter={16}>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="主导情绪"
              value={EMOTION_LABELS[summary.dominant_emotion] || summary.dominant_emotion}
              valueStyle={{ color: EMOTION_COLORS[summary.dominant_emotion] || '#999' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="压力信号"
              value={summary.stress_signals}
              valueStyle={{ color: summary.stress_signals > 5 ? '#F56C6C' : '#67C23A' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="回避信号"
              value={summary.avoidance_signals}
              valueStyle={{ color: summary.avoidance_signals > 3 ? '#F56C6C' : '#67C23A' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="信心指数"
              value={Math.round(summary.confidence_score * 100)}
              suffix="%"
              valueStyle={{ color: summary.confidence_score > 0.6 ? '#67C23A' : '#E6A23C' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="情绪分布">
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={90}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}%`}
                >
                  {pieData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={EMOTION_COLORS[entry.raw] || '#999'}
                    />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: number) => `${value}%`}
                />
                <Legend
                  formatter={(value) => EMOTION_LABELS[value] || value}
                />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="关键信号">
            {signalRows.length > 0 ? (
              <div style={{ maxHeight: 250, overflowY: 'auto' }}>
                {signalRows.map((signal, i) => (
                  <div
                    key={i}
                    style={{
                      padding: '6px 0',
                      borderBottom: '1px solid #f0f0f0',
                      display: 'flex',
                      justifyContent: 'space-between',
                    }}
                  >
                    <Space>
                      <Text type={signal.type === 'stress' ? 'danger' : 'warning'}>
                        [{signal.type === 'stress' ? '压力' : '回避'}]
                      </Text>
                      <Text>{signal.indicator}</Text>
                    </Space>
                    <Text type="secondary">
                      {Math.floor(signal.timestamp / 60)}:{String(Math.floor(signal.timestamp % 60)).padStart(2, '0')}
                    </Text>
                  </div>
                ))}
              </div>
            ) : (
              <Text type="secondary">暂无显著信号</Text>
            )}
          </Card>
        </Col>
      </Row>
    </Space>
  )
}
