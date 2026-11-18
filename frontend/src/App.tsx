import { Routes, Route } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import Dashboard from './pages/Dashboard';
import Events from './pages/Events';
import EventDetail from './pages/EventDetail';
import Assessments from './pages/Assessments';
import SubmitEvent from './pages/SubmitEvent';

export default function App() {
  return (
    <div className="min-h-screen flex" style={{ backgroundColor: '#0a0f1e' }}>
      <Sidebar />
      <div className="flex-1 ml-[220px]">
        <TopBar />
        <main className="pt-14 p-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/events" element={<Events />} />
            <Route path="/events/:id" element={<EventDetail />} />
            <Route path="/assessments" element={<Assessments />} />
            <Route path="/submit" element={<SubmitEvent />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
