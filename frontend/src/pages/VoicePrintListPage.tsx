import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { voicePrintApi, VoicePrintProfile } from '../services/api'

export function VoicePrintListPage() {
  const [profiles, setProfiles] = useState<VoicePrintProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    loadProfiles()
  }, [])

  const loadProfiles = async () => {
    try {
      const res = await voicePrintApi.listProfiles({ limit: 100 })
      setProfiles(res.data)
    } catch (err) {
      console.error('Failed to load profiles:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async () => {
    if (!newName.trim()) return
    setCreating(true)
    try {
      await voicePrintApi.createProfile({ name: newName, description: newDesc })
      setShowModal(false)
      setNewName('')
      setNewDesc('')
      loadProfiles()
    } catch (err) {
      console.error('Failed to create profile:', err)
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除此声纹档案？')) return
    try {
      await voicePrintApi.deleteProfile(id)
      loadProfiles()
    } catch (err) {
      console.error('Failed to delete profile:', err)
    }
  }

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'bg-yellow-100 text-yellow-800',
      ready: 'bg-green-100 text-green-800',
      trained: 'bg-blue-100 text-blue-800',
    }
    const labels: Record<string, string> = {
      pending: '待训练',
      ready: '已就绪',
      trained: '已优化',
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

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">声纹库管理</h1>
        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          新建人员
        </button>
      </div>

      {profiles.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          暂无声纹档案，请创建第一个人员
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {profiles.map((profile) => (
            <div
              key={profile.id}
              className="border rounded-lg p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex justify-between items-start mb-2">
                <Link
                  to={`/voice-prints/${profile.id}`}
                  className="text-lg font-semibold text-blue-600 hover:underline"
                >
                  {profile.name}
                </Link>
                {getStatusBadge(profile.status)}
              </div>
              {profile.description && (
                <p className="text-gray-600 text-sm mb-3 line-clamp-2">
                  {profile.description}
                </p>
              )}
              <div className="text-sm text-gray-500 mb-3">
                样本数: {profile.sample_count}
              </div>
              <div className="flex gap-2">
                <Link
                  to={`/voice-prints/${profile.id}`}
                  className="text-sm text-blue-600 hover:underline"
                >
                  查看详情
                </Link>
                <button
                  onClick={() => handleDelete(profile.id)}
                  className="text-sm text-red-600 hover:underline"
                >
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-96">
            <h2 className="text-xl font-bold mb-4">新建声纹档案</h2>
            <div className="mb-4">
              <label className="block text-sm font-medium mb-1">姓名</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="w-full border rounded px-3 py-2"
                placeholder="请输入姓名"
              />
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium mb-1">描述</label>
              <textarea
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                className="w-full border rounded px-3 py-2"
                rows={3}
                placeholder="可选描述"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowModal(false)}
                className="px-4 py-2 border rounded hover:bg-gray-50"
              >
                取消
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !newName.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {creating ? '创建中...' : '创建'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}