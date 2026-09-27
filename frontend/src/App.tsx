import { useStaff } from './auth/AuthContext'
import StaffGate from './auth/StaffGate'
import { BrowserRouter, Link, Navigate, Route, Routes, useParams } from 'react-router-dom'
import HomePage from './HomePage'
import DoctorLayout from './doctor/DoctorLayout'
import EncounterDetailPage from './doctor/EncounterDetailPage'
import EncounterListPage from './doctor/EncounterListPage'
import ProtocolsPage from './doctor/ProtocolsPage'
import TasksPage from './doctor/TasksPage'
import BodyPage from './patient/BodyPage'
import ConfirmPage from './patient/ConfirmPage'
import DescribePage from './patient/DescribePage'
import DonePage from './patient/DonePage'
import EncounterLayout from './patient/EncounterLayout'
import QuestionsPage from './patient/QuestionsPage'
import StartPage from './patient/StartPage'
import UrgentPage from './patient/UrgentPage'
import PrintPage from './doctor/PrintPage'
import SlipPage from './doctor/SlipPage'
import HandoverPage from './doctor/HandoverPage'
import ComponentLab from './lab/ComponentLab'

function EncounterRoute() {
  const { id } = useParams()
  return <EncounterLayout key={id} />
}

function DoctorRecordRoute() {
  const { id } = useParams()
  return <EncounterDetailPage key={id} />
}

function DoctorIndex() {
  const { user } = useStaff()
  return user.role === 'doctor' || user.role === 'nurse' ? <EncounterListPage /> : <Navigate to="/d/tasks" replace />
}

function NotFound() {
  return (
    <div className="home">
      <h1>页面不存在</h1>
      <p>
        <Link to="/">返回首页</Link>
      </p>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />

        <Route path="/p" element={<StartPage />} />
        <Route path="/p/e/:id" element={<EncounterRoute />}>
          <Route index element={<Navigate to="body" replace />} />
          <Route path="body" element={<BodyPage />} />
          <Route path="describe" element={<DescribePage />} />
          <Route path="questions" element={<QuestionsPage />} />
          <Route path="urgent" element={<UrgentPage />} />
          <Route path="confirm" element={<ConfirmPage />} />
          <Route path="done" element={<DonePage />} />
        </Route>

        <Route element={<StaffGate />}>
        <Route path="/d/e/:id/print" element={<PrintPage />} />
        <Route path="/d/e/:id/slip" element={<SlipPage />} />
        <Route path="/d/handover" element={<HandoverPage />} />
        <Route path="/d" element={<DoctorLayout />}>
          <Route index element={<DoctorIndex />} />
          <Route path="e/:id" element={<DoctorRecordRoute />} />
          <Route path="tasks" element={<TasksPage />} />
          <Route path="protocols" element={<ProtocolsPage />} />
        </Route>

        </Route>
        <Route path="/lab" element={<ComponentLab />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  )
}
