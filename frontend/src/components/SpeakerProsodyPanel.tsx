import { useState, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceArea, ReferenceLine, ComposedChart,
  BarChart, Bar,
} from 'recharts'
import { Card, Row, Col, Statistic, Space, Typography, Select, Radio, InputNumber } from 'antd'
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

type BaselineMode = 'percentile' | 'range' | 'prefix'

const getPercentile = (arr: number[], p: number): number => {
  if (arr.length === 0) return 0
  const sorted = [...arr].sort((a, b) => a - b)
  const idx = Math.ceil((p / 100) * sorted.length) - 1
  return sorted[Math.max(0, idx)]
}

const calcBaselineByPercentile = (segments: Segment[], lowerPct: number, upperPct: number) => {
  const values = segments
    .filter(s => s.prosody?.pitch_mean && s.prosody.pitch_mean > 0)
    .map(s => s.prosody!.pitch_mean!)
    .filter((v): v is number => v !== undefined && v > 0)
    .sort((a, b) => a - b)
  
  if (values.length === 0) return { lower: 0, upper: 0 }
  return {
    lower: getPercentile(values, lowerPct),
    upper: getPercentile(values, upperPct),
  }
}

const calcBaselineByRange = (segments: Segment[], startSec: number, endSec: number) => {
  const values = segments
    .filter(s => s.prosody?.pitch_mean && s.prosody.pitch_mean > 0)
    .filter(s => s.start_time >= startSec && s.end_time <= endSec)
    .map(s => s.prosody!.pitch_mean!)
    .filter((v): v is number => v !== undefined && v > 0)
  
  if (values.length === 0) return null
  return {
    lower: Math.min(...values),
    upper: Math.max(...values),
  }
}

const calcBaselineByPrefix = (segments: Segment[], speakersList: Speaker[], seconds: number) => {
  const baselines: Record<string, { lower: number; upper: number }> = {}
  
  for (const speaker of speakersList) {
    const spkSegments = segments.filter(s => s.speaker_id === speaker.id)
    const values = spkSegments
      .filter(s => s.prosody?.pitch_mean && s.prosody.pitch_mean > 0)
      .filter(s => s.end_time <= seconds)
      .map(s => s.prosody!.pitch_mean!)
      .filter((v): v is number => v !== undefined && v > 0)
    
    if (values.length > 0) {
      baselines[speaker.id] = {
        lower: Math.min(...values),
        upper: Math.max(...values),
      }
    }
  }
  
  return baselines
}

export function SpeakerProsodyPanel({ segments, speakers }: Props) {
  const [showAllSpeakers, setShowAllSpeakers] = useState(true)
  const [selectedSpeakerId, setSelectedSpeakerId] = useState<string | null>(null)
  const [legendHidden, setLegendHidden] = useState<Record<string, boolean>>({})
  
  const [baselineMode, setBaselineMode] = useState<BaselineMode>('percentile')
  const [percentileLower, setPercentileLower] = useState(25)
  const [percentileUpper, setPercentileUpper] = useState(40)
  const [customRangeStart, setCustomRangeStart] = useState(0)
  const [customRangeEnd, setCustomRangeEnd] = useState(60)
  const [prefixSeconds, setPrefixSeconds] = useState(180)

  const filteredSegments = showAllSpeakers
    ? segments
    : segments.filter(seg => seg.speaker_id === selectedSpeakerId)

  const speakerOptions = speakers.map((s, _i) => ({
    value: s.id,
    label: s.label,
  }))

  const allTimePoints = useMemo(() => {
    if (filteredSegments.length === 0) return []
    const maxTime = Math.max(...filteredSegments.map(s => s.end_time || s.start_time))
    const minTime = Math.min(...filteredSegments.map(s => s.start_time))
    const result: number[] = []
    for (let t = Math.floor(minTime); t <= Math.ceil(maxTime); t += 1) {
      result.push(t)
    }
    return result
  }, [filteredSegments])

  const allSpeakersData = useMemo(() => {
    const speakerMap: Record<string, Record<number, any>> = {}
    
    speakers.forEach(speaker => {
      speakerMap[speaker.id] = {}
      const spkSegments = filteredSegments.filter(s => s.speaker_id === speaker.id)
      const speakerIdx = speakers.findIndex(s => s.id === speaker.id)
      
      allTimePoints.forEach(time => {
        const seg = spkSegments.find(s => time >= Math.floor(s.start_time) && time < Math.ceil(s.end_time || s.start_time + 1))
        
        if (seg && seg.prosody) {
          const prosody = seg.prosody
          const hasPitch = prosody.pitch_mean && prosody.pitch_mean > 0
          speakerMap[speaker.id][time] = {
            time,
            timeLabel: formatTime(time),
            speaker_id: speaker.id,
            speaker_label: speaker.label,
            speaker_color: speaker.color || CHART_COLORS[speakerIdx % CHART_COLORS.length],
            pitch_mean: hasPitch && prosody.pitch_mean ? Math.round(prosody.pitch_mean) : null,
            pitch_std: prosody.pitch_std ? Math.round(prosody.pitch_std) : null,
            energy_mean: prosody.energy_mean ? Math.round(prosody.energy_mean * 100) : null,
            speech_rate: prosody.speech_rate ? Math.round(prosody.speech_rate * 10) / 10 : null,
            pause_ratio: prosody.pause_ratio ? Math.round(prosody.pause_ratio * 100) : null,
            filler_count: prosody.filler_count || 0,
            hasData: true,
          }
        } else {
          speakerMap[speaker.id][time] = {
            time,
            timeLabel: formatTime(time),
            speaker_id: speaker.id,
            speaker_label: speaker.label,
            speaker_color: speaker.color || CHART_COLORS[speakerIdx % CHART_COLORS.length],
            pitch_mean: null,
            pitch_std: null,
            energy_mean: null,
            speech_rate: null,
            pause_ratio: null,
            filler_count: 0,
            hasData: false,
          }
        }
      })
    })
    
    return speakerMap
  }, [speakers, filteredSegments, allTimePoints])

  const chartData = allTimePoints.map(time => {
    const result: any = { time, timeLabel: formatTime(time) }
    speakers.forEach(speaker => {
      const point = allSpeakersData[speaker.id]?.[time]
      if (point) {
        result[`${speaker.id}_pitch`] = point.pitch_mean
        result[`${speaker.id}_energy`] = point.energy_mean
        result[`${speaker.id}_speech_rate`] = point.speech_rate
        result[`${speaker.id}_pause_ratio`] = point.pause_ratio
      }
    })
    return result
  })
  
  const tickFormatter = (val: number) => formatTime(val)

  const speakerDataMap = useMemo(() => {
    return speakers.map((speaker, idx) => {
      // 只为未被隐藏的说话人计算 baseline
      const isHidden = legendHidden[speaker.id]
      const originalSpeakerSegments = segments.filter(s => s.speaker_id === speaker.id && !isHidden)
      const speakerTimeData = allTimePoints.map(time => allSpeakersData[speaker.id]?.[time]).filter(Boolean)

      let baseline = { lower: 0, upper: 0 }

      // 如果说话人被隐藏，或者根本不在当前过滤结果中，则不计算 baseline
      const isVisibleInFilter = !showAllSpeakers ? speaker.id === selectedSpeakerId : true
      if (isVisibleInFilter && !isHidden) {
        if (baselineMode === 'percentile') {
          baseline = calcBaselineByPercentile(originalSpeakerSegments, percentileLower, percentileUpper)
        } else if (baselineMode === 'range') {
          const rangeBaseline = calcBaselineByRange(originalSpeakerSegments, customRangeStart, customRangeEnd)
          if (rangeBaseline) baseline = rangeBaseline
        } else if (baselineMode === 'prefix') {
          const prefixBaseline = calcBaselineByPrefix(segments, speakers, prefixSeconds)
          if (prefixBaseline[speaker.id]) baseline = prefixBaseline[speaker.id]
        }
      }

      return {
        speakerId: speaker.id,
        speakerLabel: speaker.label,
        color: speaker.color || CHART_COLORS[idx % CHART_COLORS.length],
        baseline,
        segments: speakerTimeData,
      }
    })
  }, [speakers, segments, allTimePoints, allSpeakersData, baselineMode, percentileLower, percentileUpper, customRangeStart, customRangeEnd, prefixSeconds, showAllSpeakers, selectedSpeakerId, legendHidden])

  const avgPitchData = useMemo(() => {
    let sum = 0, count = 0
    speakers.forEach(speaker => {
      chartData.forEach(d => {
        const val = d[`${speaker.id}_pitch`]
        if (val !== null && val !== undefined) {
          sum += val
          count++
        }
      })
    })
    return count > 0 ? sum / count : 0
  }, [chartData, speakers])

  const avgEnergyData = useMemo(() => {
    let sum = 0, count = 0
    speakers.forEach(speaker => {
      chartData.forEach(d => {
        const val = d[`${speaker.id}_energy`]
        if (val !== null && val !== undefined) {
          sum += val
          count++
        }
      })
    })
    return count > 0 ? sum / count : 0
  }, [chartData, speakers])

  const avgSpeechRateData = useMemo(() => {
    let sum = 0, count = 0
    speakers.forEach(speaker => {
      chartData.forEach(d => {
        const val = d[`${speaker.id}_speech_rate`]
        if (val !== null && val !== undefined) {
          sum += val
          count++
        }
      })
    })
    return count > 0 ? sum / count : 0
  }, [chartData, speakers])

  const avgPauseData = useMemo(() => {
    let sum = 0, count = 0
    speakers.forEach(speaker => {
      chartData.forEach(d => {
        const val = d[`${speaker.id}_pause_ratio`]
        if (val !== null && val !== undefined) {
          sum += val
          count++
        }
      })
    })
    return count > 0 ? sum / count : 0
  }, [chartData, speakers])

  const totalFillers = filteredSegments.reduce((sum, seg) => sum + (seg.prosody?.filler_count || 0), 0)

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

  const onLegendClick = (e: any) => {
    if (e.dataKey) {
      const key = e.dataKey.replace('_pitch', '').replace('_energy', '').replace('_speech_rate', '').replace('_pause_ratio', '')
      console.log('Legend clicked:', { dataKey: e.dataKey, extractedKey: key, currentValue: legendHidden[key], newValue: !legendHidden[key] })
      setLegendHidden(prev => ({ ...prev, [key]: !prev[key] }))
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <Text strong style={{ fontSize: 16 }}>韵律分析</Text>
        <Space wrap>
          <Select
            style={{ width: 200 }}
            value={showAllSpeakers ? null : selectedSpeakerId}
            onChange={handleSpeakerChange}
            placeholder="选择说话人"
            options={[{ value: null, label: '全部说话人' }, ...speakerOptions]}
          />
        </Space>
      </div>

      <Card size="small" title="音高Baseline设置" style={{ background: '#fafafa' }}>
        <Space wrap align="center">
          <Text>模式：</Text>
          <Radio.Group
            value={baselineMode}
            onChange={(e) => setBaselineMode(e.target.value)}
            optionType="button"
            buttonStyle="solid"
            size="small"
          >
            <Radio.Button value="percentile">分位数区间</Radio.Button>
            <Radio.Button value="range">自定义区间</Radio.Button>
            <Radio.Button value="prefix">开头N秒</Radio.Button>
          </Radio.Group>

          {baselineMode === 'percentile' && (
            <Space>
              <InputNumber
                min={5}
                max={45}
                value={percentileLower}
                onChange={(v) => setPercentileLower(v || 25)}
                size="small"
                style={{ width: 80 }}
                addonAfter="%"
              />
              <Text>~</Text>
              <InputNumber
                min={55}
                max={95}
                value={percentileUpper}
                onChange={(v) => setPercentileUpper(v || 40)}
                size="small"
                style={{ width: 80 }}
                addonAfter="%"
              />
              <Text type="secondary">(25-40%分位数区间作为baseline)</Text>
            </Space>
          )}

          {baselineMode === 'range' && (
            <Space>
              <InputNumber
                min={0}
                value={customRangeStart}
                onChange={(v) => setCustomRangeStart(v || 0)}
                size="small"
                style={{ width: 100 }}
                addonAfter="秒"
                placeholder="开始"
              />
              <Text>~</Text>
              <InputNumber
                min={0}
                value={customRangeEnd}
                onChange={(v) => setCustomRangeEnd(v || 60)}
                size="small"
                style={{ width: 100 }}
                addonAfter="秒"
                placeholder="结束"
              />
            </Space>
          )}

          {baselineMode === 'prefix' && (
            <Space>
              <InputNumber
                min={10}
                max={600}
                value={prefixSeconds}
                onChange={(v) => setPrefixSeconds(v || 180)}
                size="small"
                style={{ width: 100 }}
                addonAfter="秒"
              />
              <Text type="secondary">(开头N秒作为各人baseline，按人分别计算)</Text>
            </Space>
          )}

          <Text type="secondary" style={{ marginLeft: 16 }}>
            (按说话人分别计算baseline)
          </Text>
        </Space>
      </Card>

      <Row gutter={16}>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="平均音高 (Hz)"
              value={Math.round(avgPitchData)}
              precision={0}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="平均能量"
              value={Math.round(avgEnergyData)}
              precision={0}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="语速 (词/秒)"
              value={avgSpeechRateData}
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
              value={Math.round(avgPauseData)}
              suffix="%"
              valueStyle={{ color: avgPauseData > 30 ? '#E6A23C' : '#67C23A' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="分析段落"
              value={filteredSegments.length}
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
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" type="number" tickFormatter={tickFormatter} domain={['dataMin', 'dataMax']} />
                <YAxis />
                <Tooltip 
                  formatter={(value: number, name: string) => {
                    if (name?.includes('音高') && value) return [`${Math.round(value)} Hz`, name]
                    return [value, name]
                  }}
                  labelFormatter={(label) => `时间: ${formatTime(label)}`}
                />
                <Legend onClick={onLegendClick} />
                {speakerDataMap.map((spk) => (
                  <Line
                    key={spk.speakerId}
                    type="monotone"
                    dataKey={`${spk.speakerId}_pitch`}
                    data={chartData}
                    stroke={spk.color}
                    strokeWidth={2}
                    name={`${spk.speakerLabel} 音高`}
                    dot={false}
                    connectNulls={false}
                    hide={legendHidden[spk.speakerId]}
                  />
                ))}
                {speakerDataMap.map((spk) => {
                  const bl = spk.baseline
                  console.log(`Speaker ${spk.speakerLabel}: baseline =`, bl)
                  if (!bl || (bl.lower === 0 && bl.upper === 0)) return null
                  const xMin = Math.min(...chartData.map(d => d.time))
                  const xMax = Math.max(...chartData.map(d => d.time))
                  const isHidden = legendHidden[spk.speakerId]
                  if (isHidden) return null
                  return (
                    <>
                      <ReferenceLine y={bl.lower} stroke={spk.color} strokeDasharray="3 3" />
                      <ReferenceLine y={bl.upper} stroke={spk.color} strokeDasharray="3 3" />
                      <ReferenceArea
                        key={`${spk.speakerId}-baseline`}
                        x1={xMin}
                        x2={xMax}
                        y1={bl.lower}
                        y2={bl.upper}
                        stroke={spk.color}
                        strokeOpacity={0.3}
                        fill={spk.color}
                        fillOpacity={0.15}
                      />
                    </>
                  )
                })}
                <ReferenceLine y={0} stroke="#999" />
              </ComposedChart>
            </ResponsiveContainer>
            <div style={{ marginTop: 8, textAlign: 'center' }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                浅色区域 = Baseline区间 (正常音高范围)
              </Text>
            </div>
          </Card>

          <Row gutter={16}>
            <Col span={12}>
              <Card title="能量变化">
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" type="number" tickFormatter={tickFormatter} domain={['dataMin', 'dataMax']} />
                    <YAxis />
                    <Tooltip />
                    <Legend onClick={onLegendClick} />
                    {speakerDataMap.map((spk) => (
                      <Line
                        key={spk.speakerId}
                        type="monotone"
                        dataKey={`${spk.speakerId}_energy`}
                        data={chartData}
                        stroke={spk.color}
                        name={`${spk.speakerLabel} 能量`}
                        dot={false}
                        connectNulls={false}
                        hide={legendHidden[spk.speakerId]}
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
                    <XAxis dataKey="time" type="number" tickFormatter={tickFormatter} domain={['dataMin', 'dataMax']} />
                    <YAxis yAxisId="left" />
                    <YAxis yAxisId="right" orientation="right" />
                    <Tooltip />
                    <Legend onClick={onLegendClick} />
                    {speakerDataMap.map((spk) => (
                      <Line
                        key={`${spk.speakerId}-sr`}
                        yAxisId="left"
                        type="monotone"
                        dataKey={`${spk.speakerId}_speech_rate`}
                        data={chartData}
                        stroke={spk.color}
                        name={`${spk.speakerLabel} 语速`}
                        dot={false}
                        connectNulls={false}
                        hide={legendHidden[spk.speakerId]}
                      />
                    ))}
                    {speakerDataMap.map((spk) => (
                      <Line
                        key={`${spk.speakerId}-pr`}
                        yAxisId="right"
                        type="monotone"
                        dataKey={`${spk.speakerId}_pause_ratio`}
                        data={chartData}
                        stroke={spk.color}
                        strokeDasharray="3 3"
                        name={`${spk.speakerLabel} 停顿%`}
                        dot={false}
                        connectNulls={false}
                        hide={legendHidden[spk.speakerId]}
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
