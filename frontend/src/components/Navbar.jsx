import { Link, useLocation } from "react-router-dom";
import { UserButton } from "@clerk/clerk-react";
import { useUserRole } from "../hooks/useUserRole";
import {
  Home,
  CalendarDays,
  ClipboardList,
  FileText,
  ListChecks,
  History,
  Settings,
  Users,
  Crown,
  Menu,
  MoreHorizontal,
  Bell,
  User,
} from "lucide-react";
import { useState } from "react";
import "../App.css";
import NotificationCenter from "./NotificationCenter";

const mainLinks = [
  { to: "/", label: "Dashboard", icon: <Home size={18} /> },
  { to: "/agenda", label: "Agendas", icon: <ClipboardList size={18} /> },
  { to: "/meetings", label: "Meetings", icon: <CalendarDays size={18} /> },
  { to: "/transcripts", label: "Transcripts", icon: <FileText size={18} /> }, // <-- Move here
  { to: "/minutes", label: "Minutes", icon: <FileText size={18} /> },
  { to: "/action-items", label: "Actions", icon: <ListChecks size={18} /> },
  { to: "/calendar", label: "Calendar", icon: <CalendarDays size={18} /> },
];

const moreLinks = [
  { to: "/history", label: "History", icon: <History size={18} /> },
  { to: "/settings", label: "Settings", icon: <Settings size={18} /> },
];

function Navbar({ onBrandClick }) {
  const location = useLocation();
  const { isAdmin, isPremium, tier, isLoading } = useUserRole();
  const [showMore, setShowMore] = useState(false);

  return (
    <nav className="navbar">
      <div className="navbar-left">
        <span
          className="navbar-brand"
          onClick={onBrandClick}
          style={{ cursor: "pointer" }}
        >
          <Crown size={22} style={{ color: "#3b82f6" }} />
          <span>MinuteMe</span>
        </span>
        <ul className="navbar-links">
          {mainLinks.map((link) => (
            <li key={link.to}>
              <Link
                to={link.to}
                className={location.pathname === link.to ? "active" : ""}
                style={{ display: "flex", alignItems: "center", gap: "0.5em" }}
              >
                {link.icon}
                <span className="nav-label">{link.label}</span>
              </Link>
            </li>
          ))}
          <li className="navbar-more">
            <button
              className="navbar-more-btn"
              onClick={() => setShowMore((v) => !v)}
              aria-label="More"
            >
              <MoreHorizontal size={18} />
            </button>
            {showMore && (
              <ul className="navbar-dropdown">
                {moreLinks.map((link) => (
                  <li key={link.to}>
                    <Link
                      to={link.to}
                      className={
                        location.pathname === link.to ? "active" : ""
                      }
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.5em",
                      }}
                    >
                      {link.icon}
                      <span className="nav-label">{link.label}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </li>
          {!isLoading && isAdmin && (
            <li>
              <Link
                to="/admin"
                className={location.pathname === "/admin" ? "active" : ""}
                style={{ display: "flex", alignItems: "center", gap: "0.5em" }}
              >
                <Users size={18} />
                Admin
              </Link>
            </li>
          )}
        </ul>
      </div>
      <div className="user-controls">
        {/* <NotificationCenter /> */}
        <span className={`tier-badge tier-${tier}`}>
          {tier === "premium" ? <Crown size={14} /> : null}
          {tier === "premium" ? "Premium" : "Free"}
        </span>
        {!isPremium && (
          <Link to="/upgrade" className="upgrade-button">
            <Crown size={16} style={{ marginRight: 4 }} />
            Upgrade
          </Link>
        )}
        <UserButton afterSignOutUrl="/sign-in" />
      </div>
    </nav>
  );
}

export default Navbar;
