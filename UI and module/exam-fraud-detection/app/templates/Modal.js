import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

export const Modal = ({ isOpen, onClose, title, children }) => {
    const modalRef = useRef();

    useEffect(() => {
        const handleEsc = (e) => { if (e.key === 'Escape') onClose(); };
        if (isOpen) window.addEventListener('keydown', handleEsc);
        return () => window.removeEventListener('keydown', handleEsc);
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    return createPortal(
        <div className="modal-overlay show" onClick={onClose} style={{ display: 'flex', opacity: 1 }}>
            <div 
                className="modal-content fade-scale-enter" 
                ref={modalRef} 
                onClick={(e) => e.stopPropagation()} // Ngăn click bên trong làm đóng modal
            >
                <div className="modal-header">
                    <div className="modal-title">{title}</div>
                    <button className="close-modal-btn" onClick={onClose}>✕</button>
                </div>
                <div className="modal-body">{children}</div>
            </div>
        </div>,
        document.body
    );
};