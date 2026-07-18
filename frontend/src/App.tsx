import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import Metrics from "./pages/Metrics";
import MyTickets from "./pages/MyTickets";
import NewTicket from "./pages/NewTicket";
import TicketDetail from "./pages/TicketDetail";

function Shell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const loc = useLocation();
  if (!user) return <Navigate to="/login" replace />;
  const links =
    user.role === "agent"
      ? [
          { to: "/dashboard", label: "Dashboard" },
          { to: "/metrics", label: "Metrics" },
        ]
      : [
          { to: "/tickets", label: "My Tickets" },
          { to: "/tickets/new", label: "New Ticket" },
        ];
  return (
    <>
      <header className="topbar">
        <span className="brand">⚡ QuickDesk</span>
        <nav>
          {links.map((l) => (
            <Link key={l.to} to={l.to} className={loc.pathname === l.to ? "active" : ""}>
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="spacer" />
        <span className="whoami">
          {user.email} <span className={`badge role-${user.role}`}>{user.role}</span>
        </span>
        <button className="ghost" onClick={logout}>
          Log out
        </button>
      </header>
      <main>{children}</main>
    </>
  );
}

export default function App() {
  const { user } = useAuth();
  const home = user ? (user.role === "agent" ? "/dashboard" : "/tickets") : "/login";
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={home} replace /> : <Login />} />
      <Route path="/tickets" element={<Shell><MyTickets /></Shell>} />
      <Route path="/tickets/new" element={<Shell><NewTicket /></Shell>} />
      <Route path="/tickets/:id" element={<Shell><TicketDetail /></Shell>} />
      <Route path="/dashboard" element={<Shell><Dashboard /></Shell>} />
      <Route path="/metrics" element={<Shell><Metrics /></Shell>} />
      <Route path="*" element={<Navigate to={home} replace />} />
    </Routes>
  );
}
