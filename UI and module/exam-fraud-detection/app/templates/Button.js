import React from 'react';

export const Button = ({ children, isLoading, onClick, className, ...props }) => {
    return (
        <button 
            className={`${className} btn-interact`} 
            onClick={onClick} 
            disabled={isLoading}
            {...props}
        >
            {isLoading ? <span className="loading-spinner"></span> : children}
        </button>
    );
};