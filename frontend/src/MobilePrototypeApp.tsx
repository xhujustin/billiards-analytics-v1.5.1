import { useState } from 'react';
import BottomNav, { type MainTab } from './components/BottomNav';
import BallPerformancePage from './pages/BallPerformancePage';
import DataOverviewPage from './pages/DataOverviewPage';
import FriendsPage from './pages/FriendsPage';
import HomePage from './pages/HomePage';
import MatchHistoryPage from './pages/MatchHistoryPage';
import ProfilePage from './pages/ProfilePage';
import ScanPage from './pages/ScanPage';
import TrainingDataPage from './pages/TrainingDataPage';

export type DataSection =
  | '總覽'
  | '對戰記錄'
  | '進攻數據'
  | '防守數據'
  | '球型表現'
  | '走位分析'
  | '失誤分析';

export default function MobilePrototypeApp() {
  const [activeTab, setActiveTab] = useState<MainTab>('首頁');
  const [dataSection, setDataSection] = useState<DataSection>('總覽');

  const openDataSection = (section: DataSection) => {
    setDataSection(section);
    setActiveTab('數據');
  };

  const renderPage = () => {
    if (activeTab === '首頁') return <HomePage />;
    if (activeTab === '掃碼') return <ScanPage />;
    if (activeTab === '好友') return <FriendsPage />;
    if (activeTab === '我的') return <ProfilePage />;
    if (dataSection === '對戰記錄') return <MatchHistoryPage value={dataSection} onChange={openDataSection} />;
    if (dataSection === '進攻數據') return <TrainingDataPage value={dataSection} onChange={openDataSection} />;
    if (dataSection === '球型表現') return <BallPerformancePage value={dataSection} onChange={openDataSection} />;
    return <DataOverviewPage value={dataSection} onChange={openDataSection} />;
  };

  return (
    <main className="min-h-screen bg-slate-200 px-3 py-5">
      <section className="mx-auto min-h-[844px] w-full max-w-[390px] overflow-hidden rounded-[32px] border border-slate-200 bg-cue-bg shadow-soft">
        <div className="relative min-h-[844px] pb-24">
          <div className="px-5 pt-4">
            <div className="mb-6 flex items-center justify-between px-1 text-[13px] font-bold text-cue-ink">
              <span>9:41</span>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-4 rounded-sm bg-cue-ink" />
                <span className="h-2.5 w-3 rounded-sm bg-cue-ink" />
                <span className="h-2.5 w-5 rounded-sm border border-cue-ink">
                  <span className="block h-full w-4 rounded-sm bg-cue-ink" />
                </span>
              </div>
            </div>
          </div>
          <div className="px-5">{renderPage()}</div>
          <BottomNav activeTab={activeTab} onChange={setActiveTab} />
        </div>
      </section>
    </main>
  );
}
