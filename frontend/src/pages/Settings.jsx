import { useEffect, useState } from "react";
import { useLocation, useNavigate, Link } from "react-router-dom";
import { UserProfile } from "@clerk/clerk-react";
import api from "../lib/axios";
import { useUserRole } from "../hooks/useUserRole";

function Settings() {
    const [isGoogleConnected, setIsGoogleConnected] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [message, setMessage] = useState("");
    const location = useLocation();
    const navigate = useNavigate();
    const { isPremium } = useUserRole();

    // Check Google connection status on load
    useEffect(() => {
        const checkStatus = async () => {
            try {
                setIsLoading(true);
                const response = await api.get("/auth/google/status");
                setIsGoogleConnected(response.data.is_connected);
            } catch (error) {
                setMessage("Could not check calendar connection status.");
            } finally {
                setIsLoading(false);
            }
        };
        checkStatus();
    }, []);

    // Handle OAuth redirect from Google
    useEffect(() => {
        const exchangeCode = async (code) => {
            try {
                setMessage("Connecting to Google Calendar...");
                await api.post("/auth/google/exchange", { code });
                setIsGoogleConnected(true);
                setMessage("✅ Successfully connected to Google Calendar!");
                // Remove code from URL after exchange
                navigate("/settings", { replace: true });
            } catch (error) {
                setMessage("❌ Failed to connect to Google Calendar.");
            }
        };

        const queryParams = new URLSearchParams(location.search);
        const code = queryParams.get("code");
        if (code) {
            exchangeCode(code);
        }
    }, [location, navigate]);

    const handleConnect = async () => {
        if (!isPremium) {
            alert("Google Calendar integration is a premium feature.");
            navigate("/upgrade");
            return;
        }
        try {
            const response = await api.get("/auth/google/url");
            window.location.href = response.data.authorization_url;
        } catch (error) {
            console.error("Failed to get Google auth URL:", error);
            alert("Could not start Google connection process. Please try again.");
        }
    };

    const handleDisconnect = async () => {
        if (window.confirm("Are you sure you want to disconnect your Google Calendar?")) {
            try {
                await api.post("/auth/google/disconnect");
                setIsGoogleConnected(false);
                setMessage("Google Calendar has been disconnected.");
            } catch (error) {
                setMessage("Failed to disconnect. Please try again.");
            }
        }
    };

    return (
        <div className="settings-container">
            <h1>Settings</h1>
            
            {message && <div className="message-banner">{message}</div>}

            <div className="card">
                <h2>Integrations</h2>
                <div className="integration-row">
                    <div className="integration-info">
                        <h3>Google Calendar</h3>
                        <p>Automatically schedule action items in your calendar.</p>
                        {!isPremium && <p className="premium-tag">This is a premium feature.</p>}
                    </div>
                    <div className="integration-action">
                        {isLoading ? (
                            <p>Loading...</p>
                        ) : isGoogleConnected ? (
                            <button onClick={handleDisconnect} className="secondary-action-btn danger">
                                Disconnect
                            </button>
                        ) : (
                            <button onClick={handleConnect} className="primary-action-btn" disabled={!isPremium}>
                                Connect
                            </button>
                        )}
                    </div>
                </div>
            </div>

            <div className="card">
                <h2>Profile Management</h2>
                <UserProfile routing="path" path="/settings" />
            </div>
        </div>
    );
}

export default Settings;
