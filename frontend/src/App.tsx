import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./lib/auth-context";
import { ThemeProvider } from "./lib/theme-context";
import React, { useEffect } from "react";
import { PROJECT_NAME } from "../config";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import DashboardHome from "./pages/DashboardHome";
import NewThread from "./pages/NewThread";
import ThreadView from "./pages/ThreadView";
import Profile from "./pages/Profile";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

// Decides what to do at the root path.
const RootRedirect = () => {
  const { isLoading } = useAuth();

  if (isLoading) {
    return <div className="h-screen flex items-center justify-center">Loading…</div>;
  }

  return <Navigate to="/dashboard" replace />;
};

const App = () => {
  useEffect(() => {
    // Update the document title and meta tags at runtime using the project name
    try {
      if (PROJECT_NAME) {
        document.title = PROJECT_NAME;
        const metaDesc = document.querySelector('meta[name="description"]');
        if (metaDesc) metaDesc.setAttribute('content', PROJECT_NAME);
        const og = document.querySelector('meta[property="og:title"]');
        if (og) og.setAttribute('content', PROJECT_NAME);
      }
    } catch (e) {
      // ignore in environments where DOM isn't available
    }
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
    <ThemeProvider>
      <AuthProvider>
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<RootRedirect />} />
              <Route path="/landing" element={<Landing />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/dashboard" element={<Dashboard />}>
                <Route index element={<DashboardHome />} />
                <Route path="new" element={<NewThread />} />
                <Route path="threads/:threadId" element={<ThreadView />} />
                <Route path="profile" element={<Profile />} />
              </Route>
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </TooltipProvider>
      </AuthProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

};

export default App;
