# ReplayEntryPage 使用說明

## 問題修正

已移除 `react-router-dom` 依賴，改用回調函數處理導航。

## 使用方式

### 方式 1：使用回調函數（推薦）

```tsx
import ReplayEntryPage from './components/ReplayEntryPage';

function App() {
  const handleNavigate = (page: 'stats' | 'game' | 'practice') => {
    // 根據 page 參數切換顯示的組件
    switch (page) {
      case 'stats':
        // 顯示統計頁面
        setCurrentPage('stats');
        break;
      case 'game':
        // 顯示遊玩模式回放列表
        setCurrentPage('game');
        break;
      case 'practice':
        // 顯示練習模式回放列表
        setCurrentPage('practice');
        break;
    }
  };

  return <ReplayEntryPage onNavigate={handleNavigate} />;
}
```

### 方式 2：使用狀態管理

```tsx
import { useState } from 'react';
import ReplayEntryPage from './components/ReplayEntryPage';
import StatsPage from './components/StatsPage';
import ReplayListPage from './components/ReplayListPage';

function ReplaySection() {
  const [currentPage, setCurrentPage] = useState<'entry' | 'stats' | 'game' | 'practice'>('entry');

  const handleNavigate = (page: 'stats' | 'game' | 'practice') => {
    setCurrentPage(page);
  };

  const handleBack = () => {
    setCurrentPage('entry');
  };

  // 根據當前頁面顯示不同組件
  switch (currentPage) {
    case 'stats':
      return <StatsPage onBack={handleBack} />;
    case 'game':
      return <ReplayListPage mode="game" onBack={handleBack} />;
    case 'practice':
      return <ReplayListPage mode="practice" onBack={handleBack} />;
    default:
      return <ReplayEntryPage onNavigate={handleNavigate} />;
  }
}
```

### 方式 3：安裝 react-router-dom（可選）

如果您想使用路由，可以安裝依賴：

```bash
cd frontend
npm install react-router-dom
npm install --save-dev @types/react-router-dom
```

然後恢復使用路由版本的組件。

## 組件屬性

### ReplayEntryPageProps

| 屬性 | 類型 | 必填 | 說明 |
|------|------|------|------|
| onNavigate | `(page: 'stats' \| 'game' \| 'practice') => void` | 否 | 導航回調函數 |

### 導航參數

- `'stats'` - 個人統計分析
- `'game'` - 遊玩模式回放
- `'practice'` - 練習模式回放

## 錯誤已修正

✓ 移除 `react-router-dom` 依賴
✓ 使用回調函數處理導航
✓ 組件可獨立使用
✓ TypeScript 類型完整
