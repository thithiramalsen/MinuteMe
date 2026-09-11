import { useState, useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import api from "../lib/axios";
import { format, isValid, parseISO } from "date-fns";
import { useAutomation } from "../context/AutomationContext";
import BlurrableText from "../components/BlurrableText";
// --- NEW: Import hook and icons ---
import { useUserRole } from "../hooks/useUserRole";
import { ExternalLink, Star } from "lucide-react";

function MinuteDetail() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [minute, setMinute] = useState(null);
    const [loading, setLoading] = useState(true);
    const [message, setMessage] = useState("");
    const [step, setStep] = useState("review"); // 'review', 'generating', 'done'
    // --- NEW: Get user tier ---
    const { isPremium } = useUserRole();

    useEffect(() => {
        const fetchMinute = async () => {
            try {
                setLoading(true);
                const response = await api.get(`/minutes/${id}`);
                const minuteData = response.data;
                
                // Check if action items already exist from a previous run
                if (minuteData.action_items?.length > 0) {
                    setStep("done");
                }
                setMinute(minuteData);

            } catch (error) {
                console.error("Failed to fetch minute details", error);
                setMessage("Could not load minute details.");
            } finally {
                setLoading(false);
            }
        };
        fetchMinute();
    }, [id]);

    const getStatusBadgeClass = (status, deadline) => {
        if (status === "completed") return "completed";
        if (status === "in-progress") return "in-progress";
        
        if (deadline && deadline !== "TBD") {
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

    const handleGenerateActions = async () => {
        setStep("generating");
        setMessage("Generating and scheduling action items... This may take a moment.");
        try {
            const response = await api.post("/generate-action-items", { minutes_id: id });
            const newActionItems = response.data;

            // Update the minute state with the new action items to display them immediately
            setMinute(prevMinute => ({
                ...prevMinute,
                action_items: newActionItems
            }));

            setMessage("✅ Action items generated and scheduled successfully!");
            setStep("done");
        } catch (error) {
            console.error("Failed to generate action items", error);
            setMessage(`❌ Error: ${error.response?.data?.detail || error.message}`);
            setStep("review");
        }
    };

    const handleDeleteMinute = async () => {
        if (!window.confirm("Are you sure you want to delete these minutes and all associated action items? This cannot be undone.")) {
            return;
        }
        setMessage("Deleting minutes...");
        try {
            await api.delete(`/minutes/${id}`);
            setMessage("Minutes deleted successfully. Redirecting...");
            setTimeout(() => navigate("/minutes"), 1500);
        } catch (error) {
            console.error("Failed to delete minute:", error);
            setMessage(`❌ Error: ${error.response?.data?.detail || error.message}`);
        }
    };

    const handleViewCalendar = () => {
        navigate("/calendar");
    };

    const handleGoogleCalendarClick = () => {
        if (isPremium) {
            window.open("https://calendar.google.com", "_blank");
        } else {
            navigate("/upgrade");
        }
    };

    if (loading) return (
        <div className="form-container">
            <div className="loading-container">
                <div className="loader"></div>
                <p>Loading minute details...</p>
            </div>
        </div>
    );
    if (!minute) return <p className="message-banner">Minute not found.</p>;

    const hasActionItems = minute.action_items?.length > 0;

    return (
        <div className="form-container">
            <div className="page-header">
                <h2>Meeting of {minute.date}</h2>
                {/* --- MODIFIED: Use the BlurrableText component --- */}
                <p className="subtitle">
                    {minute.meeting_name || <BlurrableText text={minute.meeting_id} prefix="ID:" />}
                </p>
            </div>
            
            {message && <div className="message-banner">{message}</div>}

            {/* Guided Step-by-Step Flow */}
            <div className="guided-flow-card">
                {step === "review" && (
                    <>
                        <h3>Next Step: Generate Action Items</h3>
                        <p>Let's extract tasks from the minutes and schedule them in your calendar.</p>
                        <button onClick={handleGenerateActions} className="primary-action-btn">
                            ✨ Generate & Schedule Action Items
                        </button>
                    </>
                )}
                {step === "generating" && (
                    <div className="processing-state" style={{padding: '1rem 0'}}>
                        <div className="loader"></div>
                        <p>Analyzing minutes and scheduling tasks...</p>
                    </div>
                )}
                {step === "done" && (
                     <>
                        <h3>Flow Complete!</h3>
                        <p>Action items have been generated and scheduled. You can review them below or view them on your calendar.</p>
                        {/* --- MODIFIED: Button Group --- */}
                        <div className="button-group">
                            <button onClick={handleViewCalendar} className="primary-action-btn">
                                📅 View In-App Calendar
                            </button>
                            <button onClick={handleGoogleCalendarClick} className="secondary-action-btn">
                                {isPremium ? (
                                    <>
                                        <ExternalLink size={16} style={{ marginRight: '8px' }} />
                                        Visit Google Calendar
                                    </>
                                ) : (
                                    <>
                                        <Star size={16} style={{ marginRight: '8px' }} />
                                        Upgrade for Sync
                                    </>
                                )}
                            </button>
                        </div>
                    </>
                )}
            </div>

            {/* This section will now appear after action items are generated */}
            {hasActionItems && (
                 <div className="detail-section">
                    <h3>Extracted Action Items</h3>
                    {/* Replace the simple list with the card-based grid */}
                    <div className="grid-container">
                        {minute.action_items.map((item, i) => {
                            const statusClass = getStatusBadgeClass(item.status, item.deadline);
                            return (
                                <div key={item._id || i} className="card action-item-card">
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
                                                {item.deadline && item.deadline !== "TBD" ? format(new Date(item.deadline), "MMM d, yyyy") : "TBD"}
                                            </span>
                                        </div>
                                    </div>
                                    {/* Action buttons can be added here in the future if needed */}
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            <div className="detail-section">
                <h3>Summary</h3>
                <p>{minute.summary}</p>
            </div>

            <div className="detail-section">
                <h3>Scheduling</h3>
                <p>
                    Next Meeting Date: {format(new Date(minute.next_meeting_date), "MMM d, yyyy")}
                    {minute.next_meeting_date_is_default && (
                        <span style={{ fontSize: '0.8em', color: 'var(--text-secondary)', marginLeft: '1em' }}>(Default date)</span>
                    )}
                </p>
            </div>

            <div className="detail-section">
                <h3>Key Decisions</h3>
                {minute.decisions?.length > 0 ? (
                    <ul className="styled-list">{minute.decisions.map((d, i) => <li key={i}>{d}</li>)}</ul>
                ) : <p>No key decisions were recorded.</p>}
            </div>

            <div className="detail-section">
                <h3>Topics for Future Discussion</h3>
                {minute.future_discussion_points?.length > 0 ? (
                    <ul className="styled-list">{minute.future_discussion_points.map((t, i) => <li key={i}>{t}</li>)}</ul>
                ) : <p>No future topics were recorded.</p>}
            </div>

            {/* Danger Zone for Deletion */}
            <div className="detail-section" style={{ marginTop: '2rem', borderTop: '1px solid var(--danger)' }}>
                <h3 style={{ color: 'var(--danger)' }}>Danger Zone</h3>
                <button onClick={handleDeleteMinute} className="form-submit-btn danger">
                    Delete This Minute
                </button>
            </div>
        </div>
    );
}

export default MinuteDetail;