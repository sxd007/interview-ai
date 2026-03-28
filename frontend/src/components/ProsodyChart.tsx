import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, BarChart, Bar,
} from 'recharts'
import { Card, Row, Col, Statistic, Space, Tag, Typography } from 'antd'
import { Segment } from '../services/api'

const { Text } = Typography

interface Props {
  segments: Segment[]
}

const formatTime = (seconds: number) => {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

export function ProsodyChart({ segments }: Props) {
  const chartData = segments
    .filter((seg) => seg.prosody)
    .map((seg) => ({
      time: formatTime(seg.start_time),
      start: Math.round(seg.start_time),
      pitch_mean: seg.prosody?.pitch_mean
        ? Math.round(seg.prosody.pitch_mean)
        : null,
      pitch_std: seg.prosody?.pitch_std
        ? Math.round(seg.prosody.pitch_std)
        : null,
      energy_mean: seg.prosody?.energy_mean
        ? Math.round(seg.prosody.energy_mean * 100)
        : null,
      speech_rate: seg.prosody?.speech_rate
        ? Math.round(seg.prosody.speech_rate * 10) / 10
        : null,
      pause_ratio: seg.prosody?.pause_ratio
        ? Math.round(seg.prosody.pause_ratio * 100)
        : null,
      filler_count: seg.prosody?.filler_count || 0,
    }))

  const avgPitch = chartData.reduce((sum, d) => sum + (d.pitch_mean || 0), 0) / (chartData.filter(d => d.pitch_mean).length || 1)
  const avgEnergy = chartData.reduce((sum, d) => sum + (d.energy_mean || 0), 0) / (chartData.filter(d => d.energy_mean).length || 1)
  const avgSpeechRate = chartData.reduce((sum, d) => sum + (d.speech_rate || 0), 0) / (chartData.filter(d => d.speech_rate).length || 1)
  const totalFillers = chartData.reduce((sum, d) => sum + d.filler_count, 0)
  const avgPause = chartData.reduce((sum, d) => sum + (d.pause_ratio || 0), 0) / (chartData.length || 1)

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Row gutter={16}>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="平均音高 (Hz)"
              value={Math.round(avgPitch)}
              precision={0}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="平均能量"
              value={Math.round(avgEnergy)}
              precision={0}
              suffix=""
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="语速 (词/秒)"
              value={avgSpeechRate}
              precision={1}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="填充词"
              value={totalFillers}
              valueStyle={{ color: totalFillers > 20 ? '#F56C6C' : '#67C23A' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="停顿比例"
              value={Math.round(avgPause)}
              suffix="%"
              valueStyle={{ color: avgPause > 30 ? '#E6A23C' : '#67C23A' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="分析段落"
              value={chartData.length}
            />
          </Card>
        </Col>
      </Row>

      {chartData.length > 0 ? (
        <>
          <Card title="音高变化">
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="pitch_mean"
                  stroke="#409EFF"
                  name="平均音高 (Hz)"
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="pitch_std"
                  stroke="#9C27B0"
                  name="音高标准差"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          <Row gutter={16}>
            <Col span={12}>
              <Card title="能量变化">
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="energy_mean" fill="#67C23A" name="平均能量" />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </Col>
            <Col span={12}>
              <Card title="语速与停顿">
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" />
                    <YAxis yAxisId="left" />
                    <YAxis yAxisId="right" orientation="right" />
                    <Tooltip />
                    <Legend />
                    <Line
                      yAxisId="left"
                      type="monotone"
                      dataKey="speech_rate"
                      stroke="#FF9800"
                      name="语速"
                      dot={false}
                    />
                    <Line
                      yAxisId="right"
                      type="monotone"
                      dataKey="pause_ratio"
                      stroke="#F56C6C"
                      name="停顿% "
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </Card>
            </Col>
          </Row>

          <Card title="段落详细">
            <div style={{ maxHeight: 300, overflowY: 'auto' }}>
              {chartData.map((d, i) => (
                <div
                  key={i}
                  style={{
                    padding: '8px 0',
                    borderBottom: '1px solid #f0f0f0',
                    display: 'flex',
                    gap: 16,
                    alignItems: 'center',
                    flexWrap: 'wrap',
                  }}
                >
                  <Text strong style={{ minWidth: 50 }}>{d.time}</Text>
                  {d.pitch_mean && <Tag color="blue">音高 {d.pitch_mean}Hz</Tag>}
                  {d.energy_mean && <Tag color="green">能量 {d.energy_mean}</Tag>}
                  {d.speech_rate !== null && <Tag color="orange">语速 {d.speech_rate}/s</Tag>}
                  {d.pause_ratio !== null && (
                    <Tag color={d.pause_ratio > 30 ? 'red' : 'default'}>
                      停顿 {d.pause_ratio}%
                    </Tag>
                  )}
                  {d.filler_count > 0 && (
                    <Tag color="purple">填充词 {d.filler_count}</Tag>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </>
      ) : (
        <Card>
          <Text type="secondary">暂无韵律分析数据</Text>
        </Card>
      )}
    </Space>
  )
}
