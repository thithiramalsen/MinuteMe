import { useState, useEffect } from "react";
import api from "../lib/axios";
// --- NEW: Import hooks and icons ---
import { Link, useNavigate } from "react-router-dom";
import { useUserRole } from "../hooks/useUserRole";
import { ExternalLink, Star } from "lucide-react";
// --- MODIFIED: Import isValid to check for valid dates ---
import { format, isPast, parseISO, isValid } from "date-fns";
import "../App.css";

function ActionItems() {
    const [actionItems, setActionItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [filter, setFilter] = useState("all"); // all, pending, completed
    // --- NEW: Get user tier and navigation function ---
    const { isPremium } = useUserRole();
    const navigate = useNavigate();
    
    useEffect(() => {
        fetchActionItems();
    }, []);

    const fetchActionItems = async () => {
        try {
            setLoading(true);
            const response = await api.get("/action-items");
            const data = response.data;

            if (data) {
                const formattedItems = data.map((item) => ({
                    id: item._id,
                    task: item.task || item.action,
                    owner: item.owner || item.assignee,
                    deadline: item.deadline || item.due_date || "TBD",
                    status: item.status || "pending",
                    minutes_id: item.minutes_id || null,
                }));
                setActionItems(formattedItems);
            }
        } catch (error) {
            console.error("Error fetching action items:", error);
            setError("Failed to load action items");
        } finally {
            setLoading(false);
        }
    };

    const handleStatusChange = async (id, newStatus) => {
        try {
            await api.patch(`/action-items/${id}`, { status: newStatus });
            setActionItems(items =>
                items.map(item =>
                    item.id === id ? { ...item, status: newStatus } : item
                )
            );
        } catch (error) {
            console.error("Failed to update status", error);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm("Are you sure you want to delete this action item? This will also remove it from your calendar.")) {
            return;
        }
        try {
            await api.delete(`/action-items/${id}`);
            setActionItems(items => items.filter(item => item.id !== id));
        } catch (error) {
            console.error("Failed to delete action item", error);
            setError("Failed to delete action item. Please try again.");
        }
    };
    
    const filteredItems = actionItems.filter(item => {
        if (filter === "all") return true;
        return item.status === filter;
    });
    
    const getStatusBadgeClass = (status, deadline) => {
        if (status === "completed") return "completed";
        if (status === "in-progress") return "in-progress";
        
        // Check if deadline is past
        if (deadline !== "TBD") {
            try {
                const deadlineDate = parseISO(deadline);
                if (isPast(deadlineDate) && status !== "completed") {
                    return "overdue";
                }
            } catch (e) {
                // Invalid date format, just use pending
            }
        }
        
        return "pending";
    };

    if (loading) return (
        <div className="form-container">
            <h2>Action Items</h2>
            <div className="loading-container">
                <div className="loader"></div>
                <p>Loading action items...</p>
            </div>
        </div>
    );
    
    if (error) return <div className="error-container">{error}</div>;

    const handleGoogleCalendarClick = () => {
        if (isPremium) {
            window.open("https://calendar.google.com", "_blank");
        } else {
            navigate("/upgrade");
        }
    };

    return (
        <div className="form-container">
            <div className="page-header" style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h2>Action Items</h2>
                    <p className="subtitle">Track and manage tasks from your meetings</p>
                </div>
                {/* --- NEW: Conditional Button --- */}
                <button onClick={handleGoogleCalendarClick} className="secondary-action-btn">
                    {isPremium ? (
                        <>
                            <ExternalLink size={16} style={{ marginRight: '8px' }} />
                            Visit Google Calendar
                        </>
                    ) : (
                        <>
                            <Star size={16} style={{ marginRight: '8px' }} />
                            Upgrade for Calendar Sync
                        </>
                    )}
                </button>
            </div>
            
            <div className="filter-bar">
                <button 
                    className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
                    onClick={() => setFilter('all')}
                >
                    All
                </button>
                <button 
                    className={`filter-btn ${filter === 'pending' ? 'active' : ''}`}
                    onClick={() => setFilter('pending')}
                >
                    Pending
                </button>
                <button 
                    className={`filter-btn ${filter === 'in-progress' ? 'active' : ''}`}
                    onClick={() => setFilter('in-progress')}
                >
                    In Progress
                </button>
                <button 
                    className={`filter-btn ${filter === 'completed' ? 'active' : ''}`}
                    onClick={() => setFilter('completed')}
                >
                    Completed
                </button>
            </div>
            
            {filteredItems.length > 0 ? (
                <div className="grid-container">
                    {filteredItems.map((item) => {
                        const statusClass = getStatusBadgeClass(item.status, item.deadline);
                        
                        // --- MODIFIED: Safely parse the date ---
                        const deadlineDate = item.deadline ? parseISO(item.deadline) : null;
                        const isDeadlineValid = deadlineDate && isValid(deadlineDate);

                        return (
                            <div key={item.id} className="card action-item-card">
                                <div className="card-header">
                                    <span className={`status-badge ${statusClass}`}>
                                        {item.status === "pending" && statusClass === "overdue" ? "Overdue" : item.status}
                                    </span>
                                </div>
                                
                                <h3 className="item-task">{item.task}</h3>
                                
                                <div className="item-details">
                                    <div className="detail">
                                        <span className="label">Assignee:</span> 
                                        <span className="value">{item.owner}</span>
                                    </div>
                                    <div className="detail">
                                        <span className="label">Due:</span> 
                                        <span className="value">
                                            {/* --- MODIFIED: Render only if the date is valid --- */}
                                            {isDeadlineValid ? format(deadlineDate, "MMM d, yyyy") : "TBD"}
                                        </span>
                                    </div>
                                    {item.minutes_id && (
                                        <div className="detail">
                                            <span className="label">Meeting:</span>
                                            <Link to={`/minutes/${item.minutes_id}`} className="meeting-link">
                                                View Meeting
                                            </Link>
                                        </div>
                                    )}
                                </div>
                                
                                <div className="card-actions">
                                    {item.status !== "completed" && (
                                        <button 
                                            onClick={() => handleStatusChange(item.id, "completed")}
                                            className="action-btn complete-btn"
                                        >
                                            Mark Complete
                                        </button>
                                    )}
                                    {item.status === "pending" && (
                                        <button 
                                            onClick={() => handleStatusChange(item.id, "in-progress")}
                                            className="action-btn progress-btn"
                                        >
                                            Start Progress
                                        </button>
                                    )}
                                    {item.status === "completed" && (
                                        <button 
                                            onClick={() => handleStatusChange(item.id, "pending")}
                                            className="action-btn reopen-btn"
                                        >
                                            Reopen
                                        </button>
                                    )}
                                    <button
                                        onClick={() => handleDelete(item.id)}
                                        className="action-btn danger"
                                        style={{ marginLeft: 'auto' }}
                                    >
                                        Delete
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>
            ) : (
                <div className="empty-state">
                    <div className="empty-icon">✅</div>
                    <h3>No action items {filter !== "all" ? `with status "${filter}"` : ""}</h3>
                    <p>Action items will appear here after processing a meeting</p>
                </div>
            )}
        </div>
    );
}

export default ActionItems;
