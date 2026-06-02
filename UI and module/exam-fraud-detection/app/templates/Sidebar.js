import React from 'react';

export const Sidebar = ({ activePage, setActivePage }) => {
    const menus = [
        { id: 'dashboard', icon: '📊', label: 'Dashboard tổng quan' },
        { id: 'rooms', icon: '🏠', label: 'Danh sách phòng thi' },
        { id: 'monitor', icon: '👁️', label: 'Giám sát phòng thi' },
        { id: 'candidates', icon: '👥', label: 'Quản lý thí sinh' },
        { id: 'ai-config', icon: '⚙️', label: 'Cấu hình AI' },
    ];

    return (
        <nav className="app-sidebar">
            <div className="sidebar-header">
                <div className="logo-dot"></div>
                <div className="sidebar-logo-text">AI-Proctor</div>
            </div>
            <div className="sidebar-nav">
                {menus.map(menu => (
                    <div 
                        key={menu.id}
                        className={`sidebar-link ${activePage === menu.id ? 'active' : ''}`}
                        onClick={() => setActivePage(menu.id)}
                    >
                        <span>{menu.icon}</span> {menu.label}
                    </div>
                ))}
            </div>
        </nav>
    );
};