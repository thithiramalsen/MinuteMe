import { Routes, Route } from "react-router-dom";
import {
  SignedIn,
  SignedOut,
  RedirectToSignIn,
  SignIn,
  SignUp,
  UserButton,
  useAuth,
} from "@clerk/clerk-react";
import { useEffect, useState } from "react";
import { setupAxiosInterceptors } from "./lib/axios";
import { AutomationProvider } from "./context/AutomationContext";
import AutomationStatusBar from "./components/AutomationStatusBar";

import Dashboard from "./pages/Dashboard";
import Agenda from "./pages/Agenda";
import Minutes from "./pages/Minutes";
import MinuteDetail from "./pages/MinuteDetail"; // Import the new detail page
import ActionItems from "./pages/ActionItems";
import History from "./pages/History";
import Settings from "./pages/Settings";
// --- NEW: Import custom auth pages ---
import SignInPage from "./pages/SignInPage";
import SignUpPage from "./pages/SignUpPage";
// CreateAgenda is no longer needed as a separate page
import Calendar from "./pages/Calendar"; // Import the new Calendar page
import Transcripts from "./pages/Transcripts";
import Navbar from "./components/Navbar";
import Meetings from "./pages/Meetings";
import AdminDashboard from "./pages/Admin"; // Import the new admin page
import NotificationCenter from "./components/NotificationCenter";
import Sidebar from "./components/Sidebar";
import Upgrade from "./pages/Upgrade";
import "./App.css";
import "./components/UI.css";

function App() {
  const { getToken } = useAuth();
  const [sidebarVisible, setSidebarVisible] = useState(false);

  // Setup Axios interceptor when the component mounts with error handling
  useEffect(() => {
    if (getToken) {
      setupAxiosInterceptors(getToken);
    }
  }, [getToken]);

  return (
    <AutomationProvider>
      <div className="App">
        <Sidebar visible={sidebarVisible} onClose={() => setSidebarVisible(false)} />
        {/* Remove marginLeft logic here */}
        <div>
          <AutomationStatusBar />
          <header>
            <SignedIn>
              <div className="header-container">
                <Navbar onBrandClick={() => setSidebarVisible(true)} />
                <NotificationCenter />
              </div>
            </SignedIn>
          </header>
          <main>
            <Routes>
              {/* --- MODIFIED: Use custom auth pages --- */}
              <Route
                path="/sign-in/*"
                element={<SignInPage />}
              />
              <Route
                path="/sign-up/*"
                element={<SignUpPage />}
              />
              <Route
                path="/"
                element={
                  <>
                    <SignedIn>
                      <Dashboard />
                    </SignedIn>
                    <SignedOut>
                      <RedirectToSignIn />
                    </SignedOut>
                  </>
                }
              />
              {/* The /create-agenda route is no longer needed */}
              <Route
                path="/agenda"
                element={
                  <SignedIn>
                    <Agenda />
                  </SignedIn>
                }
              />
              <Route
                path="/calendar"
                element={
                  <SignedIn>
                    <Calendar />
                  </SignedIn>
                }
              />
              <Route
                path="/minutes"
                element={
                  <SignedIn>
                    <Minutes />
                  </SignedIn>
                }
              />
              <Route
                path="/minutes/:id" // Add route for specific minute
                element={
                  <SignedIn>
                    <MinuteDetail />
                  </SignedIn>
                }
              />
              <Route
                path="/action-items"
                element={
                  <SignedIn>
                    <ActionItems />
                  </SignedIn>
                }
              />
              <Route
                path="/history"
                element={
                  <SignedIn>
                    <History />
                  </SignedIn>
                }
              />
              <Route
                path="/settings"
                element={
                  <SignedIn>
                    <Settings />
                  </SignedIn>
                }
              />
              <Route
                path="/transcripts"
                element={
                  <SignedIn>
                    <Transcripts />
                  </SignedIn>
                }
              />
              <Route
                path="/meetings"
                element={
                  <SignedIn>
                    <Meetings />
                  </SignedIn>
                }
              />
              {/* Add the new Admin route */}
              <Route
                path="/admin"
                element={
                  <SignedIn>
                    <AdminDashboard />
                  </SignedIn>
                }
              />
              <Route path="/upgrade" element={<SignedIn><Upgrade /></SignedIn>} />
            </Routes>
          </main>
        </div>
      </div>
    </AutomationProvider>
  );
}

export default App;
