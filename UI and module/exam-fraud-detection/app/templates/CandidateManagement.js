import React, { useState, useMemo } from 'react';
import { useDebounce } from '../hooks/useDebounce';
import { Button } from '../components/common/Button';
import { Modal } from '../components/common/Modal';
import { EmptyState } from '../components/common/EmptyState';

const MOCK_DATA = [
    { id: '22520001', name: 'Nguyễn Văn An', room: 'A101', status: 'safe', warnings: 0 },
    { id: '22520005', name: 'Bùi Tuấn Anh', room: 'B202', status: 'danger', warnings: 3 },
];

export const CandidateManagement = () => {
    const [searchTerm, setSearchTerm] = useState('');
    const [filterRoom, setFilterRoom] = useState('all');
    const [isExporting, setIsExporting] = useState(false);
    const [isModalOpen, setIsModalOpen] = useState(false);

    const debouncedSearch = useDebounce(searchTerm, 300);

    // Dùng useMemo tối ưu hiệu suất lọc dữ liệu
    const filteredData = useMemo(() => {
        return MOCK_DATA.filter(cand => {
            const matchSearch = cand.name.toLowerCase().includes(debouncedSearch.toLowerCase()) || 
                                cand.id.includes(debouncedSearch);
            const matchRoom = filterRoom === 'all' || cand.room === filterRoom;
            return matchSearch && matchRoom;
        });
    }, [debouncedSearch, filterRoom]);

    const handleExport = () => {
        setIsExporting(true);
        setTimeout(() => setIsExporting(false), 1500); // Mock loading 1.5s
    };

    return (
        <div className="view-section active-view page-enter">
            <div className="toolbar">
                <div style={{ display: 'flex', gap: '1rem' }}>
                    <input 
                        type="text" 
                        className="search-box" 
                        placeholder="Tìm MSSV, Họ tên..." 
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                    <select className="search-box" onChange={(e) => setFilterRoom(e.target.value)}>
                        <option value="all">Tất cả phòng</option>
                        <option value="A101">A101</option>
                        <option value="B202">B202</option>
                    </select>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <Button className="filter-btn" isLoading={isExporting} onClick={handleExport}>
                        Export Excel
                    </Button>
                    <Button className="cam-trigger-btn" onClick={() => setIsModalOpen(true)}>
                        + Thêm thí sinh
                    </Button>
                </div>
            </div>

            <div className="alerts-table-container">
                {filteredData.length > 0 ? (
                    <table className="alerts-table">
                        <thead>
                            <tr><th>MSSV</th><th>Họ tên</th><th>Phòng thi</th><th>Trạng thái</th><th>Thao tác</th></tr>
                        </thead>
                        <tbody>
                            {filteredData.map(cand => (
                                <tr key={cand.id}>
                                    <td>{cand.id}</td>
                                    <td>{cand.name}</td>
                                    <td>{cand.room}</td>
                                    <td><span className={`alert-tag ${cand.status === 'danger' ? 'tag-high' : ''}`}>{cand.status}</span></td>
                                    <td><Button className="filter-btn" style={{padding: '0.3rem'}}>Sửa</Button></td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                ) : (
                    <EmptyState message="Không tìm thấy thí sinh nào" actionText="Thêm ngay" onAction={() => setIsModalOpen(true)} />
                )}
            </div>

            {/* Modal Thêm Thí Sinh */}
            <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Thêm Thí Sinh Mới">
                <div className="form-group"><label className="form-label">MSSV</label><input type="text" className="form-input" /></div>
                <div className="form-group"><label className="form-label">Họ tên</label><input type="text" className="form-input" /></div>
                <Button className="cam-trigger-btn" style={{marginTop: '1rem'}} onClick={() => setIsModalOpen(false)}>Lưu lại</Button>
            </Modal>
        </div>
    );
};