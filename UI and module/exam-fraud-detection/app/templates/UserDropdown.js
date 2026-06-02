import React, { useState, useRef } from 'react';
import { useOnClickOutside } from '../../hooks/useOnClickOutside';

export const UserDropdown = () => {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef();
    
    useOnClickOutside(dropdownRef, () => setIsOpen(false));

    return (
        <div className="user-dropdown-wrapper" ref={dropdownRef}>
            <div className="user-avatar" onClick={() => setIsOpen(!isOpen)}>AD</div>
            {isOpen && (
                <div className="user-dropdown show fade-scale-enter">
                    <div style={{ padding: '1rem', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <div style={{ fontWeight: 600, color: '#fff' }}>Admin Proctor</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>admin@uit.edu.vn</div>
                    </div>
                    <a className="user-dropdown-item" onClick={() => setIsOpen(false)}>Hồ sơ cá nhân</a>
                    <a className="user-dropdown-item" onClick={() => setIsOpen(false)}>Cài đặt</a>
                    <a className="user-dropdown-item" style={{ color: 'var(--danger)' }}>Đăng xuất</a>
                </div>
            )}
        </div>
    );
};