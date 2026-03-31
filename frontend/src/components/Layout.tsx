import { Outlet, Link, useLocation } from 'react-router-dom'
import { Layout as AntLayout, Menu } from 'antd'
import { HomeOutlined, VideoCameraOutlined, UploadOutlined, UserOutlined } from '@ant-design/icons'

const { Header, Content } = AntLayout

export function Layout() {
  const location = useLocation()

  const items = [
    { key: '/', icon: <HomeOutlined />, label: <Link to="/">首页</Link> },
    { key: '/interviews', icon: <VideoCameraOutlined />, label: <Link to="/interviews">访谈列表</Link> },
    { key: '/upload', icon: <UploadOutlined />, label: <Link to="/upload">上传视频</Link> },
    { key: '/voice-prints', icon: <UserOutlined />, label: <Link to="/voice-prints">声纹库</Link> },
  ]

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center' }}>
        <div style={{ color: 'white', fontSize: 20, fontWeight: 'bold', marginRight: 32 }}>
          Interview AI
        </div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[location.pathname]}
          items={items}
          style={{ flex: 1 }}
        />
      </Header>
      <Content style={{ padding: '24px 50px' }}>
        <Outlet />
      </Content>
    </AntLayout>
  )
}
