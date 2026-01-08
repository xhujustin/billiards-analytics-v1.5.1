/**
 * Layout Component - 主佈局框架
 * 包含頂部導航欄和側邊欄
 */

import React from 'react';
import './Layout.css';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  return (
    <div className="layout">
      {children}
    </div>
  );
};

export default Layout;
