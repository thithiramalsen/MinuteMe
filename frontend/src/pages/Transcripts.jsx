import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom"; // Import useNavigate
import api from "../lib/axios";
import { formatDistanceToNow } from "date-fns";
import { useUserRole } from "../hooks/useUserRole";
import ProcessingModeToggle from "../components/ProcessingModeToggle";

function Transcripts() {
    const [transcripts, setTranscripts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [message, setMessage] = useState("");
    const { isPremium } = useUserRole();
    const [autoMode, setAutoMode] = useState(false);
    const [automationQuota, setAutomationQuota] = useState(5);
    const navigate = useNavigate(); // Initialize navigate

    useEffect(() => {
        async function fetchPageData() {
            try {
                setLoading(true);
                const transcriptsRes = await api.get("/transcripts");
                setTranscripts(transcriptsRes.data);

                if (!isPremium) {
                    const quotaRes = await api.get("/user/automation-quota");
                    setAutomationQuota(quotaRes.data.remaining);
                }
            } catch (error) {
                setMessage("Failed to load transcripts.");
            } finally {
                setLoading(false);
            }
        }
        fetchPageData();
    }, [isPremium]);

    const handleGenerateMinutes = async (transcript) => {
        setMessage(`Processing minutes for ${transcript.meeting_name}...`);
        try {
            if (autoMode) {
                // --- AUTOMATED FLOW ---
                await api.post("/process-automated", { 
                    transcript_text: transcript.transcript,
                    meeting_id: transcript.meeting_id 
                });
                setMessage("✅ Automation started! You'll get a notification when it's done.");

            } else {
                // --- MANUAL FLOW ---
                const response = await api.post("/generate-minutes", { transcript_id: transcript._id });
                const newMinutesId = response.data._id;
                if (newMinutesId) {
                    setMessage("Minutes generated successfully! Navigating...");
                    navigate(`/minutes/${newMinutesId}`); // Navigate to the new minute
                } else {
                    setMessage("Error: Could not get ID for new minutes.");
                }
            }
        } catch (error) {
            const errorDetail = error.response?.data?.detail || "An unknown error occurred.";
            setMessage(`❌ Error: ${errorDetail}`);
        }
    };

    const handleDeleteTranscript = async (transcriptId) => {
        if (!window.confirm("Are you sure you want to permanently delete this transcript?")) {
            return;
        }
        try {
            await api.delete(`/transcripts/${transcriptId}`);
            setTranscripts(prev => prev.filter(t => t._id !== transcriptId));
            setMessage("Transcript deleted successfully.");
        } catch (error) {
            const errorDetail = error.response?.data?.detail || "An unknown error occurred.";
            setMessage(`❌ Error: ${errorDetail}`);
        }
    };

    if (loading) return (
        <div className="form-container">
            <h2>Transcripts</h2>
            <div className="loading-container">
                <div className="loader"></div>
                <p>Loading transcripts...</p>
            </div>
        </div>
    );

    const formatTranscriptPreview = (text) => {
        if (!text) return "No transcript content";
        return text.length > 150 ? `${text.substring(0, 150)}...` : text;
    };

    return (
        <div className="form-container">
            <div className="page-header">
                <h2>Meeting Transcripts</h2>
                <p className="subtitle">View and process your meeting recordings</p>
            </div>
            
            {message && <div className="message-banner">{message}</div>}

            <ProcessingModeToggle 
                autoMode={autoMode}
                setAutoMode={setAutoMode}
                isPremium={isPremium}
                automationQuota={automationQuota}
            />
            
            {transcripts.length > 0 ? (
                <div className="grid-container">
                    {transcripts.map((transcript) => {
                        const createdAt = new Date(transcript.created_at);
                        
                        return (
                            <div key={transcript._id} className="card transcript-card">
                                <div className="card-header">
                                    <div className="date-time">
                                        <div className="date">{createdAt.toLocaleDateString()}</div>
                                        <div className="time">{createdAt.toLocaleTimeString()}</div>
                                    </div>
                                    <span className="time-ago">
                                        {formatDistanceToNow(createdAt, { addSuffix: true })}
                                    </span>
                                </div>
                                
                                <div className="transcript-preview">
                                    {formatTranscriptPreview(transcript.transcript)}
                                </div>
                                
                                <div className="card-actions">
                                    <button 
                                        onClick={() => handleGenerateMinutes(transcript)} 
                                        className="form-submit-btn"
                                    >
                                        {autoMode ? "🚀 Start Automation" : "Generate Minutes"}
                                    </button>
                                    <button
                                        onClick={() => {
                                            const blob = new Blob([transcript.transcript], { type: "text/plain" });
                                            const url = URL.createObjectURL(blob);
                                            const a = document.createElement("a");
                                            a.href = url;
                                            a.download = `${transcript.meeting_name || "transcript"}.txt`;
                                            a.click();
                                            URL.revokeObjectURL(url);
                                        }}
                                        className="form-submit-btn"
                                        style={{ marginLeft: "8px" }}
                                    >
                                        Download Transcript
                                    </button>
                                    <button
                                        onClick={() => handleDeleteTranscript(transcript._id)}
                                        className="form-submit-btn danger"
                                        style={{ marginLeft: "auto" }}
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
                    <div className="empty-icon">📝</div>
                    <h3>No transcripts yet</h3>
                    <p>Upload a meeting recording from the dashboard to get started</p>
                </div>
            )}
        </div>
    );
}

export default Transcripts;