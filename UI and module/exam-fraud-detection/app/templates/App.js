import React, { useState } from 'react';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { Dashboard } from './views/Dashboard';
import { CandidateManagement } from './views/CandidateManagement';
// import các views khác...

export const App = () => {
    // State quản lý Routing SPA
    const [activePage, setActivePage] = useState('dashboard');

    const renderView = () => {
        switch(activePage) {
            case 'dashboard': return <Dashboard navigateTo={setActivePage} />;
            case 'candidates': return <CandidateManagement />;
            // Map các case khác
            default: return <EmptyState message="Tính năng đang phát triển" />;
        }
    };

    return (
        <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
            {/* Sidebar */}
            <Sidebar activePage={activePage} setActivePage={setActivePage} />

            {/* Main Area */}
            <div className="app-main-wrapper">
                <Header />
                <main>
                    <div className="views-container">
                        {/* Khu vực render Component có animation */}
                        {renderView()}
                    </div>
                    {/* Right Sidebar nếu cần (phụ thuộc logic activePage) */}
                </main>
            </div>
        </div>
    );
};