import { useEffect, useMemo, useRef, useState } from 'react';
import { Outlet, useNavigate, useMatch } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { ThreadSidebar } from '@/components/ThreadSidebar';
import RightSidebar from '@/components/RightSidebar';
import { useAuth } from '@/lib/auth-context';
import { useTheme } from '@/lib/theme-context';
import { removeAuthToken, removeCurrentUser, getAuthToken } from '@/lib/api';
import { API_URL } from '../../config';
import { io, Socket } from 'socket.io-client';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import AppNavbar from '@/components/AppNavbar';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable';

const Dashboard = () => {
  const { user, logout, isLoading, setUser } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  // Persist sidebar width across sessions
  const storageKey = 'dashboard:sidebar:layout';
  const defaultLayout = useMemo(() => {
    const raw = localStorage.getItem(storageKey);
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        // support both 2-panel and 3-panel layouts stored previously
        if (Array.isArray(parsed) && parsed.length === 3) return parsed as number[];
        if (Array.isArray(parsed) && parsed.length === 2) return [parsed[0], parsed[1], 0] as number[];
      } catch {}
    }
    return [18, 64, 18] as number[]; // percentage widths: left, middle, right
  }, []);
  const [layout, setLayout] = useState<number[]>(defaultLayout);
  const prevSidebarSizeRef = useRef<number>(layout[0]);
  const prevRightSizeRef = useRef<number>(layout[2]);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [collapsedPercent, setCollapsedPercent] = useState<number>(6);
  // Minimum width for the RIGHT sidebar when expanded (as a % of container).
  // We compute this from a pixel target so it adapts to screen size.
  const [expandedRightMinPercent, setExpandedRightMinPercent] = useState<number>(18);
  const panelRef = useRef<any>(null);
  const middlePanelRef = useRef<any>(null);
  const rightPanelRef = useRef<any>(null);
  // Start the right sidebar collapsed by default
  const [rightCollapsed, setRightCollapsed] = useState<boolean>(true);
  const titleSocketRef = useRef<Socket | null>(null);
  const latestUserRef = useRef(user);
  useEffect(() => { latestUserRef.current = user; }, [user]);

  // Keep collapsed width ~64px and enforce a minimum expanded width for the RIGHT sidebar (~260px)
  useEffect(() => {
    const updatePercents = () => {
      const width = containerRef.current?.getBoundingClientRect().width || window.innerWidth || 1200;
      // Collapsed: ~64px
      const collapsedPx = 64;
      const collapsedPct = Math.max(2, Math.min(20, (collapsedPx / Math.max(1, width)) * 100));
      setCollapsedPercent(collapsedPct);

  // Expanded RIGHT min: ~220px (slightly smaller but still readable)
  const rightMinPx = 220;
      let rightMinPct = (rightMinPx / Math.max(1, width)) * 100;
      // Clamp to reasonable range so it plays well with left/min middle constraints
      rightMinPct = Math.max(12, Math.min(30, rightMinPct));
      setExpandedRightMinPercent(rightMinPct);
    };
    updatePercents();
    window.addEventListener('resize', updatePercents);
    return () => window.removeEventListener('resize', updatePercents);
  }, []);
  const match = useMatch('/dashboard/threads/:threadId');
  const activeThreadId = match?.params.threadId;

  // Normalize initial middle/right sizes after first paint to avoid partial render/clipping
  useEffect(() => {
    requestAnimationFrame(() => {
      const left = layout[0];
      const desiredRight = rightCollapsed
        ? collapsedPercent
        : Math.min(40, Math.max(expandedRightMinPercent, layout[2] ?? defaultLayout[2] ?? 18));
      const desiredMiddle = Math.max(40, 100 - left - desiredRight);

      if (middlePanelRef.current?.resize) middlePanelRef.current.resize(desiredMiddle);
      if (rightPanelRef.current?.resize) rightPanelRef.current.resize(desiredRight);
    });
  }, []);

  // Handle sidebar collapse/expand by resizing the panel
  useEffect(() => {
    if (panelRef.current && panelRef.current.resize) {
      if (sidebarCollapsed) {
        // Collapsing: save current size and resize to collapsed width
        const currentSize = layout[0];
        if (currentSize > collapsedPercent) {
          prevSidebarSizeRef.current = currentSize;
        }
        panelRef.current.resize(collapsedPercent);
      } else {
        // Expanding: restore previous size
        const restoredSize = prevSidebarSizeRef.current || defaultLayout[0];
        const targetSize = Math.min(40, Math.max(12, restoredSize));
        panelRef.current.resize(targetSize);
      }
    }
  }, [sidebarCollapsed, collapsedPercent]);

  // Handle right panel collapse/expand by resizing the right panel
  useEffect(() => {
    if (rightPanelRef.current && rightPanelRef.current.resize) {
      if (rightCollapsed) {
        const currentSize = layout[2];
        if (currentSize > collapsedPercent) {
          prevRightSizeRef.current = currentSize;
        }
        // Collapse right; expand middle to take freed space
        const left = layout[0];
        const targetRight = collapsedPercent;
        const targetMiddle = Math.max(40, 100 - left - targetRight);
        // Resize middle first then right to avoid clamping
        if (middlePanelRef.current?.resize) middlePanelRef.current.resize(targetMiddle);
        rightPanelRef.current.resize(targetRight);
      } else {
        const restoredSize = prevRightSizeRef.current || defaultLayout[2] || 18;
        const targetRight = Math.min(40, Math.max(expandedRightMinPercent, restoredSize));
        const left = layout[0];
        // Allocate remaining width to middle respecting its min (40)
        const targetMiddle = Math.max(40, 100 - left - targetRight);
        // Apply in an animation frame to ensure layout is ready
        requestAnimationFrame(() => {
          if (middlePanelRef.current?.resize) middlePanelRef.current.resize(targetMiddle);
          rightPanelRef.current.resize(targetRight);
        });
      }
    }
  }, [rightCollapsed, collapsedPercent, expandedRightMinPercent]);

  useEffect(() => {
    if (isLoading) return;
    if (!user) {
      navigate('/login');
    }
  }, [user, navigate, isLoading]);

  // Listen for server-driven title updates and update sidebar threads
  useEffect(() => {
    // Clean up any previous socket when user changes or component unmounts
    const cleanup = () => {
      if (titleSocketRef.current) {
        try { titleSocketRef.current.disconnect(); } catch {}
      }
      titleSocketRef.current = null;
    };

    if (!user) {
      cleanup();
      return;
    }

    const token = getAuthToken();
    try {
      const socket = io(API_URL, {
        path: '/socket.io',
        transports: ['websocket'],
        auth: token ? { token } : undefined,
      });
      titleSocketRef.current = socket;

      const eventName = `${user.userId}/title_update`;
      const onTitleUpdate = (payload: { thread_id?: string; new_title?: string } | undefined) => {
        if (!payload || !payload.thread_id || typeof payload.new_title !== 'string') return;
        const { thread_id, new_title } = payload;
        // Update local user state so ThreadSidebar re-renders with the new title
        const prev = latestUserRef.current;
        if (!prev) return;
        const existing = prev.threads?.[thread_id];
        if (!existing) return; // Unknown thread, ignore
        const next = {
          ...prev,
          threads: {
            ...prev.threads,
            [thread_id]: { ...existing, thread_name: new_title },
          },
        };
        setUser(next);
      };

      socket.on('connect_error', (err) => {
        if (import.meta.env.DEV) console.debug('title_update socket connect_error', err);
      });
      socket.on(eventName, onTitleUpdate);

      return () => {
        try {
          socket.off(eventName, onTitleUpdate);
          socket.disconnect();
        } catch {}
        if (titleSocketRef.current === socket) {
          titleSocketRef.current = null;
        }
      };
    } catch {
      // If socket init fails, ensure ref is cleared
      titleSocketRef.current = null;
    }
  }, [user?.userId]);

  const handleLogout = () => {
    removeAuthToken();
    removeCurrentUser();
    logout();
    navigate('/');
  };

  if (isLoading) {
    return <div className="h-screen flex items-center justify-center">Loading…</div>;
  }
  if (!user) return null;

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <AppNavbar />

      {/* Main Content */}
  <div ref={containerRef} className="flex-1 flex overflow-hidden min-h-0 min-w-0">
        <ResizablePanelGroup
          direction="horizontal"
          className="w-full min-h-0 min-w-0"
          onLayout={(sizes) => {
            // Save last known sizes; also keep ref updated
            prevSidebarSizeRef.current = sizes[0];
            setLayout(sizes);
            localStorage.setItem(storageKey, JSON.stringify(sizes));
          }}
        >
            <ResizablePanel
              ref={panelRef}
              defaultSize={sidebarCollapsed ? collapsedPercent : layout[0]}
              minSize={sidebarCollapsed ? collapsedPercent : 12}
              maxSize={sidebarCollapsed ? collapsedPercent : 40}
              collapsible={false}
            >
            <div className="h-full min-h-0 min-w-0">
              <ThreadSidebar
                threads={user.threads || {}}
                activeThreadId={activeThreadId}
                collapsed={sidebarCollapsed}
                onToggleCollapse={() => {
                  setSidebarCollapsed((prev) => !prev);
                }}
              />
            </div>
          </ResizablePanel>
          {!sidebarCollapsed && <ResizableHandle withHandle />}
          <ResizablePanel ref={middlePanelRef} defaultSize={sidebarCollapsed ? 100 - collapsedPercent - (rightCollapsed ? collapsedPercent : layout[2]) : layout[1]} minSize={40}>
            <main className="h-full overflow-hidden min-h-0 min-w-0">
              <Outlet />
            </main>
          </ResizablePanel>
          {!rightCollapsed && <ResizableHandle withHandle />}
          <ResizablePanel
            ref={rightPanelRef}
            defaultSize={rightCollapsed ? collapsedPercent : layout[2]}
            minSize={rightCollapsed ? collapsedPercent : expandedRightMinPercent}
            maxSize={rightCollapsed ? collapsedPercent : 40}
            collapsible={false}
          >
            <div className="h-full min-h-0 min-w-0">
              <RightSidebar
                threadId={activeThreadId}
                threads={user.threads}
                collapsed={rightCollapsed}
                onToggleCollapse={() => setRightCollapsed((p) => !p)}
              />
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
        
      </div>
    </div>
  );
};

export default Dashboard;
