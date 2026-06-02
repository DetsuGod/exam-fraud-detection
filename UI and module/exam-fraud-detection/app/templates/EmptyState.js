import React from 'react';

export const EmptyState = ({ message, actionText, onAction }) => (
    <div className="panel-card" style={{ alignItems: 'center', padding: '3rem', borderStyle: 'dashed' }}>
        <span style={{ fontSize: '2rem', opacity: 0.5 }}>📂</span>
        <p style={{ margin: '1rem 0', color: 'var(--text-secondary)' }}>{message}</p>
        {actionText && (
            <button className="cam-trigger-btn btn-interact" onClick={onAction}>
                {actionText}
            </button>
        )}
    </div>
);