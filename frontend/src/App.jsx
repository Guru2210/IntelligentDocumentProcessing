import { BrowserRouter, Routes, Route, Navigate, NavLink, useLocation } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { 
  FolderOpen, FileText, Tag, Brain, Zap, Eye, BarChart3, 
  CheckSquare, GitBranch, Settings, ChevronRight
} from 'lucide-react'

import ProjectsPage from './pages/ProjectsPage'
import DocumentsPage from './pages/DocumentsPage'
import LabelStudio from './pages/LabelStudio'
import TrainingPage from './pages/TrainingPage'
import ExtractionPage from './pages/ExtractionPage'
import ReviewPage from './pages/ReviewPage'
import ModelsPage from './pages/ModelsPage'

function Sidebar() {
  const location = useLocation()

  const navItems = [
    { section: 'WORKSPACE' },
    { to: '/projects', icon: FolderOpen, label: 'Projects' },
    { section: 'STUDIO' },
    { to: '/documents', icon: FileText, label: 'Documents' },
    { to: '/label', icon: Tag, label: 'Label Studio' },
    { section: 'MODELS' },
    { to: '/train', icon: Brain, label: 'Training' },
    { to: '/models', icon: GitBranch, label: 'Models' },
    { section: 'INFERENCE' },
    { to: '/extract', icon: Zap, label: 'Extract' },
    { to: '/review', icon: CheckSquare, label: 'Review Queue' },
  ]

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">🧠</div>
        <div>
          <div className="sidebar-logo-text">IDP Studio</div>
          <span className="sidebar-logo-sub">Document Intelligence</span>
        </div>
      </div>
      <nav className="sidebar-nav">
        {navItems.map((item, i) =>
          item.section ? (
            <div key={`sec-${i}`} className="sidebar-section-label">{item.section}</div>
          ) : (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              <item.icon className="nav-icon" size={17} />
              {item.label}
            </NavLink>
          )
        )}
      </nav>

      <div style={{ padding: '12px', borderTop: '1px solid var(--border)' }}>
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="nav-link"
          style={{ fontSize: '0.8rem' }}
        >
          <Settings size={15} className="nav-icon" />
          API Docs
          <ChevronRight size={12} style={{ marginLeft: 'auto', opacity: 0.4 }} />
        </a>
      </div>
    </aside>
  )
}

function TopBar() {
  const location = useLocation()
  const titles = {
    '/projects': 'Projects',
    '/documents': 'Documents',
    '/label': 'Label Studio',
    '/train': 'Training',
    '/models': 'Models',
    '/extract': 'Extract',
    '/review': 'Review Queue',
  }
  const title = Object.entries(titles).find(([path]) => location.pathname.startsWith(path))?.[1] || 'IDP Studio'
  
  return (
    <header style={{
      height: '48px',
      borderBottom: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      padding: '0 20px',
      background: 'var(--bg-sidebar)',
      flexShrink: 0,
      gap: 8,
    }}>
      <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>IDP Studio</span>
      <ChevronRight size={12} style={{ color: 'var(--text-muted)' }} />
      <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>{title}</span>
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className="badge badge-green" style={{ fontSize: '0.65rem' }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--green)', display: 'inline-block', marginRight: 4 }} />
          API Connected
        </span>
      </div>
    </header>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Sidebar />
        <div className="main-content">
          <TopBar />
          <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <Routes>
              <Route path="/" element={<Navigate to="/projects" replace />} />
              <Route path="/projects" element={<ProjectsPage />} />
              <Route path="/documents" element={<DocumentsPage />} />
              <Route path="/label" element={<LabelStudio />} />
              <Route path="/label/:projectId/:docId" element={<LabelStudio />} />
              <Route path="/train" element={<TrainingPage />} />
              <Route path="/train/:projectId" element={<TrainingPage />} />
              <Route path="/models" element={<ModelsPage />} />
              <Route path="/extract" element={<ExtractionPage />} />
              <Route path="/review" element={<ReviewPage />} />
            </Routes>
          </div>
        </div>
      </div>
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: 'var(--bg-card)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
          },
        }}
      />
    </BrowserRouter>
  )
}
