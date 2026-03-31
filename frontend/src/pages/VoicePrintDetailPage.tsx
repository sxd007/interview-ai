import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { voicePrintApi, VoicePrintProfile, VoicePrintSample, VoicePrintMatch } from '../services/api'

export function VoicePrintDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [profile, setProfile] = useState<VoicePrintProfile | null>(null)
  const [samples, setSamples] = useState<VoicePrintSample[]>([])
  const [matches, setMatches] = useState<VoicePrintMatch[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [editName, setEditName] = useState('')
  const [editDesc, setEditDesc] = useState('')

  useEffect(() => {
    if (id) loadData()
  }, [id])

  const loadData = async () => {
    try {
      const [profileRes, samplesRes, matchesRes] = await Promise.all([
        voicePrintApi.getProfile(id!),
        voicePrintApi.listSamples(id!),
        voicePrintApi.getMatches(id!),
      ])
      setProfile(profileRes.data)
      setSamples(samplesRes.data)
      setMatches(matchesRes.data)
    } catch (err) {
      console.error('Failed to load data:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !id) return

    setUploading(true)
    try {
      await voicePrintApi.addSample(id, file)
      loadData()
    } catch (err) {
      console.error('Failed to upload sample:', err)
      alert('上传失败')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const handleDeleteSample = async (sampleId: string) => {
    if (!confirm('确定删除此样本？')) return
    try {
      await voicePrintApi.deleteSample(sampleId)
      loadData()
    } catch (err) {
      console.error('Failed to delete sample:', err)
    }
  }

  const handleUpdate = async () => {
    if (!id || !editName.trim()) return
    try {
      await voicePrintApi.updateProfile(id, { name: editName, description: editDesc })
      setShowEditModal(false)
      loadData()
    } catch (err) {
      console.error('Failed to update profile:', err)
    }
  }

  const openEditModal = () => {
    if (profile) {
      setEditName(profile.name)
      setEditDesc(profile.description || '')
      setShowEditModal(true)
    }
  }

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'bg-yellow-100 text-yellow-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
      skipped: 'bg-gray-100 text-gray-800',
    }
    const labels: Record<string, string> = {
      pending: '处理中',
      completed: '完成',
      failed: '失败',
      skipped: '跳过',
    }
    return (
      <span className={`px-2 py-1 rounded text-xs ${colors[status] || 'bg-gray-100'}`}>
        {labels[status] || status}
      </span>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">加载中...</div>
      </div>
    )
  }

  if (!profile) {
    return (
      <div className="p-6">
        <div className="text-center text-gray-500">档案不存在</div>
        <Link to="/voice-prints" className="text-blue-600 hover:underline block mt-4 text-center">
          返回列表
        </Link>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <Link to="/voice-prints" className="text-blue-600 hover:underline">
          ← 返回列表
        </Link>
      </div>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h1 className="text-2xl font-bold">{profile.name}</h1>
            {profile.description && (
              <p className="text-gray-600 mt-2">{profile.description}</p>
            )}
          </div>
          <button
            onClick={openEditModal}
            className="px-3 py-1 border rounded text-sm hover:bg-gray-50"
          >
            编辑
          </button>
        </div>

        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-gray-500">样本数量</span>
            <div className="font-medium">{profile.sample_count}</div>
          </div>
          <div>
            <span className="text-gray-500">状态</span>
            <div className="font-medium">
              {profile.status === 'pending' && '待训练'}
              {profile.status === 'ready' && '已就绪'}
              {profile.status === 'trained' && '已优化'}
            </div>
          </div>
          <div>
            <span className="text-gray-500">创建时间</span>
            <div className="font-medium">{new Date(profile.created_at).toLocaleString()}</div>
          </div>
        </div>

        {profile.embedding && (
          <div className="mt-4 p-3 bg-green-50 rounded text-sm">
            <span className="text-green-700">✓ 声纹特征已提取</span>
            <span className="text-gray-500 ml-2">维度: {profile.embedding.length}</span>
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold">音频样本</h2>
          <label className={`px-4 py-2 bg-blue-600 text-white rounded cursor-pointer hover:bg-blue-700 ${uploading ? 'opacity-50' : ''}`}>
            {uploading ? '上传中...' : '上传音频'}
            <input
              type="file"
              accept="audio/*"
              onChange={handleUpload}
              className="hidden"
              disabled={uploading}
            />
          </label>
        </div>

        {samples.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            暂无音频样本，请上传
          </div>
        ) : (
          <div className="space-y-3">
            {samples.map((sample) => (
              <div key={sample.id} className="flex items-center justify-between border rounded p-3">
                <div className="flex items-center gap-4">
                  <div>
                    <div className="font-medium">{sample.audio_path.split('/').pop()}</div>
                    <div className="text-sm text-gray-500">
                      时长: {formatDuration(sample.duration)}
                    </div>
                  </div>
                  {getStatusBadge(sample.status)}
                </div>
                <button
                  onClick={() => handleDeleteSample(sample.id)}
                  className="text-red-600 hover:underline text-sm"
                >
                  删除
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold mb-4">匹配记录</h2>
        {matches.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            暂无匹配记录
          </div>
        ) : (
          <div className="space-y-2">
            {matches.map((match) => (
              <div key={match.id} className="flex items-center justify-between border rounded p-3">
                <div>
                  {match.interview_id && (
                    <span className="font-medium">面试: {match.interview_id.slice(0, 8)}...</span>
                  )}
                  {match.speaker_label && (
                    <span className="text-gray-500 ml-2">说话人: {match.speaker_label}</span>
                  )}
                </div>
                <div className="text-right">
                  <div className="font-medium text-green-600">
                    置信度: {(match.confidence * 100).toFixed(1)}%
                  </div>
                  <div className="text-sm text-gray-500">
                    {new Date(match.matched_at).toLocaleString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {showEditModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-96">
            <h2 className="text-xl font-bold mb-4">编辑声纹档案</h2>
            <div className="mb-4">
              <label className="block text-sm font-medium mb-1">姓名</label>
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full border rounded px-3 py-2"
              />
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium mb-1">描述</label>
              <textarea
                value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
                className="w-full border rounded px-3 py-2"
                rows={3}
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowEditModal(false)}
                className="px-4 py-2 border rounded hover:bg-gray-50"
              >
                取消
              </button>
              <button
                onClick={handleUpdate}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}