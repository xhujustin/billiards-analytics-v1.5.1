import { useRef, useState, type PointerEvent } from 'react';
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

  const [refreshKey, setRefreshKey] = useState(0);
  const [pullDistance, setPullDistance] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const pullStartYRef = useRef<number | null>(null);
  const isPullingRef = useRef(false);
  const activePointerIdRef = useRef<number | null>(null);

  const refreshThreshold = 72;
  const maxPullDistance = 96;

  const openDataSection = (section: DataSection) => {
    setDataSection(section);
    setActiveTab('數據');
  };

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (window.scrollY > 0 || isRefreshing) {
      pullStartYRef.current = null;
      isPullingRef.current = false;
      activePointerIdRef.current = null;
      return;
    }

    activePointerIdRef.current = event.pointerId;
    pullStartYRef.current = event.clientY;
    isPullingRef.current = true;
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (activePointerIdRef.current !== event.pointerId) {
      return;
    }
    if (!isPullingRef.current || pullStartYRef.current === null || window.scrollY > 0) {
      return;
    }

    const delta = event.clientY - pullStartYRef.current;
    if (delta <= 0) {
      setPullDistance(0);
      return;
    }

    event.preventDefault();
    setPullDistance(Math.min(maxPullDistance, Math.round(delta * 0.55)));
  };

  const handlePointerEnd = (event: PointerEvent<HTMLDivElement>) => {
    if (activePointerIdRef.current !== event.pointerId) {
      return;
    }
    if (!isPullingRef.current) {
      return;
    }

    const shouldRefresh = pullDistance >= refreshThreshold;
    pullStartYRef.current = null;
    isPullingRef.current = false;
    activePointerIdRef.current = null;
    event.currentTarget.releasePointerCapture(event.pointerId);

    if (!shouldRefresh) {
      setPullDistance(0);
      return;
    }

    setIsRefreshing(true);
    setPullDistance(refreshThreshold);
    setRefreshKey((current) => current + 1);
    window.setTimeout(() => {
      setIsRefreshing(false);
      setPullDistance(0);
    }, 700);
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
        <div
          className="relative min-h-[844px] pb-24"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerEnd}
          onPointerCancel={handlePointerEnd}
          style={{ touchAction: pullDistance > 0 ? 'none' : 'pan-y' }}
        >
          <div
            className="pointer-events-none absolute left-0 right-0 top-0 z-20 flex justify-center transition-transform duration-200"
            style={{ transform: `translateY(${Math.max(0, pullDistance - 48)}px)` }}
          >
            <div className="rounded-full border border-cue-line bg-white px-3 py-1.5 text-[11px] font-black text-cue-muted shadow-card">
              {isRefreshing ? '更新中...' : pullDistance >= refreshThreshold ? '放開刷新' : '下拉刷新'}
            </div>
          </div>
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
          <div
            key={`${activeTab}-${dataSection}-${refreshKey}`}
            className="px-5 transition-transform duration-200"
            style={{ transform: `translateY(${pullDistance}px)` }}
          >
            {renderPage()}
          </div>
          <BottomNav activeTab={activeTab} onChange={setActiveTab} />
        </div>
      </section>
    </main>
  );
}
