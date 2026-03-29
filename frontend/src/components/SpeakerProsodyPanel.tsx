import { useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, BarChart, Bar,
} from 'recharts'
import { Card, Row, Col, Statistic, Space, Typography, Select } from 'antd'
import { Segment, Speaker } from '../services/api'

const { Text } = Typography

interface Props {
  segments: Segment[]
  speakers: Speaker[]
}

const formatTime = (seconds: number) => {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

const CHART_COLORS = ['#409EFF', '#67C23A', '#FF9800', '#F56C6C', '#9C27B0', '#00BCD4', '#E6A23C', '#909399']

export function SpeakerProsodyPanel({ segments, speakers }: Props) {
  const [showAllSpeakers, setShowAllSpeakers] = useState(true)
  const [selectedSpeakerId, setSelectedSpeakerId] = useState<string | null>(null)

  const filteredSegments = showAllSpeakers
    ? segments
    : segments.filter(seg => seg.speaker_id === selectedSpeakerId)

  const speakerOptions = speakers.map((s, i) => ({
    value: s.id,
    label: (
      <Space>
        <div style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: s.color || CHART_COLORS[i % CHART_COLORS.length] }} />
        {s.label}
      </Space>
    )
  }))

  const allSegmentsWithSpeaker = filteredSegments
    .filter((seg) => seg.prosody)
    .map((seg) => {
      const speakerIdx = speakers.findIndex(s => s.id === seg.speaker_id)
      return {
        time: Math.round(seg.start_time),
        timeLabel: formatTime(seg.start_time),
        speaker_id: seg.speaker_id,
        speaker_label: seg.speaker_label || speakers[speakerIdx]?.label || '未知',
        speaker_color: speakers[speakerIdx]?.color || CHART_COLORS[speakerIdx % CHART_COLORS.length],
        pitch_mean: seg.prosody?.pitch_mean ? Math.round(seg.prosody.pitch_mean) : null,
        pitch_std: seg.prosody?.pitch_std ? Math.round(seg.prosody.pitch_std) : null,
        energy_mean: seg.prosody?.energy_mean ? Math.round(seg.prosody.energy_mean * 100) : null,
        speech_rate: seg.prosody?.speech_rate ? Math.round(seg.prosody.speech_rate * 10) / 10 : null,
        pause_ratio: seg.prosody?.pause_ratio ? Math.round(seg.prosody.pause_ratio * 100) : null,
        filler_count: seg.prosody?.filler_count || 0,
      }
    })

  const chartData = allSegmentsWithSpeaker

  const tickFormatter = (val: number) => formatTime(val)

  const speakerDataMap = speakers.map((speaker, idx) => {
    const speakerSegments = allSegmentsWithSpeaker.filter(s => s.speaker_id === speaker.id)
    return {
      speakerId: speaker.id,
      speakerLabel: speaker.label,
      color: speaker.color || CHART_COLORS[idx % CHART_COLORS.length],
      segments: speakerSegments,
    }
  })

  const avgPitch = chartData.reduce((sum, d) => sum + (d.pitch_mean || 0), 0) / (chartData.filter(d => d.pitch_mean).length || 1)
  const avgEnergy = chartData.reduce((sum, d) => sum + (d.energy_mean || 0), 0) / (chartData.filter(d => d.energy_mean).length || 1)
  const avgSpeechRate = chartData.reduce((sum, d) => sum + (d.speech_rate || 0), 0) / (chartData.filter(d => d.speech_rate).length || 1)
  const totalFillers = chartData.reduce((sum, d) => sum + d.filler_count, 0)
  const avgPause = chartData.reduce((sum, d) => sum + (d.pause_ratio || 0), 0) / (chartData.length || 1)

  const comparisonData = speakers.map((speaker, idx) => {
    const spkSegments = segments.filter(s => s.speaker_id === speaker.id && s.prosody)
    const spkAvgSpeechRate = spkSegments.reduce((sum, d) => sum + (d.prosody?.speech_rate || 0), 0) / (spkSegments.length || 1)
    const spkAvgPause = spkSegments.reduce((sum, d) => sum + (d.prosody?.pause_ratio || 0), 0) / (spkSegments.length || 1)
    const spkTotalDuration = spkSegments.reduce((sum, d) => sum + (d.end_time - d.start_time), 0)
    return {
      speaker: speaker.label,
      color: speaker.color || CHART_COLORS[idx % CHART_COLORS.length],
      speech_rate: Math.round(spkAvgSpeechRate * 10) / 10,
      pause_ratio: Math.round(spkAvgPause * 100),
      total_duration: Math.round(spkTotalDuration),
    }
  })

  const handleSpeakerChange = (value: string | null) => {
    setSelectedSpeakerId(value)
    setShowAllSpeakers(value === null)
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text strong style={{ fontSize: 16 }}>韵律分析</Text>
        <Select
          style={{ width: 200 }}
          value={showAllSpeakers ? null : selectedSpeakerId}
          onChange={handleSpeakerChange}
          placeholder="选择说话人"
          options={[{ value: null, label: '全部说话人' }, ...speakerOptions]}
        />
      </div>

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

      <Card title="说话人对比">
        <Row gutter={16}>
          <Col span={12}>
            <Text type="secondary">语速对比 (词/秒)</Text>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={comparisonData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis type="category" dataKey="speaker" width={80} />
                <Tooltip />
                <Bar dataKey="speech_rate" name="语速" />
              </BarChart>
            </ResponsiveContainer>
          </Col>
          <Col span={12}>
            <Text type="secondary">停顿比例对比 (%)</Text>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={comparisonData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis type="category" dataKey="speaker" width={80} />
                <Tooltip />
                <Bar dataKey="pause_ratio" name="停顿%" fill="#F56C6C" />
              </BarChart>
            </ResponsiveContainer>
          </Col>
        </Row>
      </Card>

      {chartData.length > 0 ? (
        <>
          <Card title="音高变化">
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tickFormatter={tickFormatter} />
                <YAxis />
                <Tooltip />
                <Legend />
                {speakerDataMap.map((spk) => (
                  <Line
                    key={spk.speakerId}
                    type="monotone"
                    dataKey="pitch_mean"
                    data={spk.segments}
                    stroke={spk.color}
                    name={`${spk.speakerLabel} 音高`}
                    dot={false}
                    connectNulls
                  />
                ))}
                {showAllSpeakers && speakerDataMap.map((spk) => (
                  <Line
                    key={`${spk.speakerId}-std`}
                    type="monotone"
                    dataKey="pitch_std"
                    data={spk.segments}
                    stroke={spk.color}
                    strokeDasharray="5 5"
                    name={`${spk.speakerLabel} 音高变化`}
                    dot={false}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </Card>

          <Row gutter={16}>
            <Col span={12}>
              <Card title="能量变化">
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" tickFormatter={tickFormatter} />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    {speakerDataMap.map((spk) => (
                      <Line
                        key={spk.speakerId}
                        type="monotone"
                        dataKey="energy_mean"
                        data={spk.segments}
                        stroke={spk.color}
                        name={`${spk.speakerLabel} 能量`}
                        dot={false}
                        connectNulls
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </Card>
            </Col>
            <Col span={12}>
              <Card title="语速与停顿">
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" tickFormatter={tickFormatter} />
                    <YAxis yAxisId="left" />
                    <YAxis yAxisId="right" orientation="right" />
                    <Tooltip />
                    <Legend />
                    {speakerDataMap.map((spk) => (
                      <Line
                        key={`${spk.speakerId}-sr`}
                        yAxisId="left"
                        type="monotone"
                        dataKey="speech_rate"
                        data={spk.segments}
                        stroke={spk.color}
                        name={`${spk.speakerLabel} 语速`}
                        dot={false}
                        connectNulls
                      />
                    ))}
                    {speakerDataMap.map((spk) => (
                      <Line
                        key={`${spk.speakerId}-pr`}
                        yAxisId="right"
                        type="monotone"
                        dataKey="pause_ratio"
                        data={spk.segments}
                        stroke={spk.color}
                        strokeDasharray="3 3"
                        name={`${spk.speakerLabel} 停顿%`}
                        dot={false}
                        connectNulls
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </Card>
            </Col>
          </Row>
        </>
      ) : (
        <Card>
          <Text type="secondary">暂无韵律分析数据</Text>
        </Card>
      )}
    </Space>
  )
}
