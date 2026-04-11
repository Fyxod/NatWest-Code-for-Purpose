import React from 'react';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { Map as MapIcon, FileText, Sparkles, Download, Trash2, Plus, FileSpreadsheet, Settings } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import MindMapModal from './MindMapModal';
import SummaryModal from './SummaryModal';
import ExcelSkillModal from './ExcelSkillModal';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

import { Thread, getAuthToken, api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { toast } from 'sonner';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { API_URL } from '../../config';

interface Props {
  threadId?: string;
  threads?: Record<string, Thread>;
  // controlled collapsed state from parent (true = collapsed)
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

const buildDocumentUrl = (userId: string, threadId: string, fileName: string, token?: string | null) => {
  const basePath = `${API_URL}/data/${encodeURIComponent(userId)}/threads/${encodeURIComponent(threadId)}/uploads/${encodeURIComponent(fileName)}`;
  if (token) {
    return `${basePath}?token=${encodeURIComponent(token)}`;
  }
  return basePath;
};

const RightSidebar: React.FC<Props> = ({ threadId, threads = {}, collapsed = false, onToggleCollapse }) => {
  const { refreshUser, user } = useAuth();
  // internal open state for modals
  const [mindOpen, setMindOpen] = React.useState(false);
  const [docsOpen, setDocsOpen] = React.useState(false);
  const [summaryOpen, setSummaryOpen] = React.useState(false);
  const [excelSkillOpen, setExcelSkillOpen] = React.useState(false);
  const [deleteConfirmDocId, setDeleteConfirmDocId] = React.useState<string | null>(null);
  const [deleting, setDeleting] = React.useState(false);
  const [importOpen, setImportOpen] = React.useState(false);
  const [selectedSourceThread, setSelectedSourceThread] = React.useState<string>('');
  const [addingDocId, setAddingDocId] = React.useState<string | null>(null);
  const [switches, setSwitches] = React.useState<Record<string, boolean>>({});
  const [settingsOpen, setSettingsOpen] = React.useState(false);

  // Fetch switches when settings panel opens
  React.useEffect(() => {
    if (!settingsOpen) return;
    api.getSwitches()
      .then((data) => setSwitches(data.switches))
      .catch((err) => console.error('Failed to load switches:', err));
  }, [settingsOpen]);

  const handleSwitchToggle = async (key: string, value: boolean) => {
    // Optimistic update
    setSwitches((prev) => ({ ...prev, [key]: value }));
    try {
      await api.updateSwitch(key, value);
    } catch (err) {
      // Revert on failure
      setSwitches((prev) => ({ ...prev, [key]: !value }));
      toast.error(err instanceof Error ? err.message : 'Failed to update setting');
    }
  };

  const handleDeleteDocument = async (docId: string) => {
    if (!threadId || deleting) return;
    setDeleting(true);
    try {
      const response = await api.deleteDocument(threadId, docId);
      if (response?.status === 'success') {
        toast.success('Document deleted');
        await refreshUser();
      } else {
        toast.error('Failed to delete document');
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to delete document');
    } finally {
      setDeleting(false);
      setDeleteConfirmDocId(null);
    }
  };

  const documents = React.useMemo(() => {
    if (!threadId) return [];
    const t = threads[threadId];
    return t?.documents || [];
  }, [threadId, threads]);
  const authToken = React.useMemo(() => getAuthToken(), [user?.userId]);

  // Other threads with documents (for import feature)
  const otherThreads = React.useMemo(() => {
    if (!threadId) return [];
    return Object.entries(threads)
      .filter(([id]) => id !== threadId)
      .filter(([, t]) => t.documents && t.documents.length > 0);
  }, [threadId, threads]);

  const sourceDocuments = React.useMemo(() => {
    if (!selectedSourceThread) return [];
    return threads[selectedSourceThread]?.documents || [];
  }, [selectedSourceThread, threads]);

  // Exclude docs already in current thread
  const availableSourceDocs = React.useMemo(() => {
    const existingIds = new Set(documents.map((d: any) => d.docId));
    return sourceDocuments.filter((d: any) => !existingIds.has(d.docId));
  }, [sourceDocuments, documents]);

  const handleAddExisting = async (docId: string) => {
    if (!threadId || !selectedSourceThread || addingDocId) return;
    setAddingDocId(docId);
    try {
      await api.addExistingDocument(threadId, selectedSourceThread, docId);
      toast.success('Document added to thread');
      await refreshUser();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to add document');
    } finally {
      setAddingDocId(null);
    }
  };

  const openAfterRefresh = async (setter: (v: boolean) => void) => {
    try {
      // Fetch latest user/threads so documents reflect recent uploads
      await refreshUser();
    } catch (e) {
      // Non-blocking: if refresh fails, still open with current data
      console.debug('RightSidebar refreshUser failed (non-blocking):', e);
    } finally {
      setter(true);
    }
  };

  return (
    <div className="h-full min-h-0 min-w-0 flex flex-col">
      {/* Match the header sizing/style used in `ThreadSidebar` so the collapse control lines up visually */}
      <div
        className="w-full flex items-center justify-center border-l bg-sidebar p-4 border-b cursor-pointer"
        role="button"
        tabIndex={0}
        aria-label={collapsed ? 'Expand right sidebar' : 'Collapse right sidebar'}
        onClick={() => onToggleCollapse && onToggleCollapse()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggleCollapse && onToggleCollapse();
          }
        }}
      >
        <Button variant="ghost" className="h-10 w-10" onClick={(e) => { e.stopPropagation(); onToggleCollapse && onToggleCollapse(); }} aria-label={collapsed ? 'Expand' : 'Collapse'}>
          {collapsed ? <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M9 5l7 7-7 7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg> : <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M15 19l-7-7 7-7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>}
        </Button>
      </div>

      <div className="right-sidebar-scroll flex-1 min-h-0 w-full flex flex-col items-start pt-4 px-3 border-l bg-background overflow-y-auto overflow-x-hidden">
        {/* Studio buttons moved up here. When collapsed, show icon-only column; when expanded show labeled buttons */}
        {collapsed ? (
          <div className="flex flex-col items-center w-full space-y-3">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" onClick={() => openAfterRefresh(setDocsOpen)} disabled={!threadId} aria-label="Documents">
                  <FileText className="w-5 h-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Documents</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" onClick={() => openAfterRefresh(setSummaryOpen)} disabled={!threadId} aria-label="Summary">
                  <Sparkles className="w-5 h-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Summary</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" onClick={() => openAfterRefresh(setMindOpen)} disabled={!threadId} aria-label="Mind Map">
                  <MapIcon className="w-5 h-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Mind Map</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" onClick={() => openAfterRefresh(setExcelSkillOpen)} disabled={!threadId} aria-label="Excel Builder">
                  <FileSpreadsheet className="w-5 h-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Excel Builder</TooltipContent>
            </Tooltip>
            {/* Export Button (Collapsed) */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => {
                    if (!threadId) return;
                    window.open(`${API_URL}/export/${threadId}/html?token=${encodeURIComponent(authToken || '')}`, '_blank');
                  }}
                  disabled={!threadId}
                  aria-label="Export Chat"
                >
                  <Download className="w-5 h-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Export Chat</TooltipContent>
            </Tooltip>
            <div className="border-t w-full my-1" />
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" onClick={() => setSettingsOpen(!settingsOpen)} aria-label="Settings">
                  <Settings className="w-5 h-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Settings</TooltipContent>
            </Tooltip>
          </div>
        ) : (
          <div className="w-full">
            <div className="mb-2 font-semibold">Studio</div>
            <div className="space-y-2">
              <Button className="w-full justify-start" variant="ghost" onClick={() => openAfterRefresh(setDocsOpen)} disabled={!threadId}>
                <FileText className="w-4 h-4 mr-2" /> Documents
              </Button>
              <Button className="w-full justify-start" variant="ghost" onClick={() => openAfterRefresh(setSummaryOpen)} disabled={!threadId}>
                <Sparkles className="w-4 h-4 mr-2" /> Summary
              </Button>
              <Button className="w-full justify-start" variant="ghost" onClick={() => openAfterRefresh(setMindOpen)} disabled={!threadId}>
                <MapIcon className="w-4 h-4 mr-2" /> Mind Map
              </Button>
              <Button className="w-full justify-start" variant="ghost" onClick={() => openAfterRefresh(setExcelSkillOpen)} disabled={!threadId}>
                <FileSpreadsheet className="w-4 h-4 mr-2" /> Excel Builder
              </Button>
              <Button
                className="w-full justify-start text-muted-foreground hover:text-primary"
                variant="ghost"
                onClick={() => {
                  if (!threadId) return;
                  window.open(`${API_URL}/export/${threadId}/html?token=${encodeURIComponent(authToken || '')}`, '_blank');
                }}
                disabled={!threadId}
              >
                <Download className="w-4 h-4 mr-2" /> Export Chat
              </Button>
              <div className="border-t my-2" />
              <Button
                className="w-full justify-start"
                variant="ghost"
                onClick={() => setSettingsOpen(!settingsOpen)}
              >
                <Settings className="w-4 h-4 mr-2" /> Settings
              </Button>
              {settingsOpen && (
                <div className="space-y-3 px-2 py-2 rounded-md bg-muted/50">
                  <div className="flex items-center justify-between">
                    <label className="text-sm" htmlFor="sw-disable-thinking">Disable Thinking</label>
                    <Switch
                      id="sw-disable-thinking"
                      checked={switches['DISABLE_THINKING'] ?? true}
                      onCheckedChange={(v) => handleSwitchToggle('DISABLE_THINKING', v)}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <label className="text-sm" htmlFor="sw-decomposition">Query Decomposition</label>
                    <Switch
                      id="sw-decomposition"
                      checked={switches['DECOMPOSITION'] ?? true}
                      onCheckedChange={(v) => handleSwitchToggle('DECOMPOSITION', v)}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      <MindMapModal open={mindOpen} onOpenChange={setMindOpen} threadId={threadId ?? ''} />
      <SummaryModal open={summaryOpen} onOpenChange={setSummaryOpen} threadId={threadId ?? ''} documents={documents} />

      {/* Summary handled by SummaryModal above */}

      <Dialog open={docsOpen} onOpenChange={setDocsOpen}>
        <DialogContent className="max-w-lg max-h-[80vh] flex flex-col overflow-hidden">
          <DialogHeader>
            <DialogTitle>Documents</DialogTitle>
            <DialogDescription>Documents in this thread</DialogDescription>
          </DialogHeader>
          <div className="mt-2 overflow-hidden flex-1">
            <div className="h-64 border rounded-md p-2 overflow-y-auto">
                {documents.length === 0 ? (
                  <p className="text-sm text-muted-foreground p-4">No documents in this thread.</p>
                ) : (
                  <div className="space-y-2">
                    {documents.map((d: any) => {
                      const href = user && threadId
                        ? buildDocumentUrl(user.userId, threadId, d.file_name, authToken ?? undefined)
                        : undefined;

                      return (
                        <div key={d.docId} className="flex items-center gap-2 p-2 rounded hover:bg-accent/60 dark:hover:bg-accent/30">
                          {href ? (
                            <a
                              href={href}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex-1 min-w-0 overflow-hidden"
                            >
                              <div className="font-medium truncate" title={d.title}>{d.title}</div>
                              <div className="text-sm text-muted-foreground truncate">{d.type} &bull; {new Date(d.time_uploaded).toLocaleDateString()}</div>
                            </a>
                          ) : (
                            <div className="flex-1 min-w-0 overflow-hidden">
                              <div className="font-medium truncate" title={d.title}>{d.title}</div>
                              <div className="text-sm text-muted-foreground truncate">{d.type} &bull; {new Date(d.time_uploaded).toLocaleDateString()}</div>
                            </div>
                          )}
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 flex-none text-muted-foreground hover:text-destructive"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setDeleteConfirmDocId(d.docId);
                                }}
                                disabled={deleting}
                                aria-label={`Delete ${d.title}`}
                              >
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Delete document</TooltipContent>
                          </Tooltip>
                        </div>
                      );
                    })}
                  </div>
                )}
            </div>
            {/* Import from Another Thread */}
            {otherThreads.length > 0 && (
              <div className="mt-3 border-t pt-3">
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => {
                    setSelectedSourceThread('');
                    setImportOpen(true);
                  }}
                >
                  <Plus className="w-4 h-4 mr-2" /> Import from Another Thread
                </Button>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Import Document Dialog */}
      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent className="max-w-lg max-h-[80vh] flex flex-col overflow-hidden">
          <DialogHeader>
            <DialogTitle>Import Document from Another Thread</DialogTitle>
            <DialogDescription>
              Select a thread and choose a document to add without re-processing.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 mt-2">
            <Select value={selectedSourceThread} onValueChange={setSelectedSourceThread}>
              <SelectTrigger>
                <SelectValue placeholder="Select source thread..." />
              </SelectTrigger>
              <SelectContent>
                {otherThreads.map(([id, t]) => (
                  <SelectItem key={id} value={id}>
                    {t.thread_name} ({t.documents.length} docs)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {selectedSourceThread && (
              <div className="h-48 border rounded-md p-2 overflow-y-auto space-y-2">
                {availableSourceDocs.length === 0 ? (
                  <p className="text-sm text-muted-foreground p-2">
                    {sourceDocuments.length > 0
                      ? 'All documents from this thread already exist here.'
                      : 'No documents in this thread.'}
                  </p>
                ) : (
                  availableSourceDocs.map((d: any) => (
                    <div key={d.docId} className="flex items-center gap-2 p-2 rounded hover:bg-accent/60">
                      <div className="flex-1 min-w-0 overflow-hidden">
                        <div className="font-medium truncate text-sm" title={d.title}>{d.title}</div>
                        <div className="text-xs text-muted-foreground">{d.type}</div>
                      </div>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => handleAddExisting(d.docId)}
                        disabled={addingDocId === d.docId}
                      >
                        {addingDocId === d.docId ? 'Adding...' : 'Add'}
                      </Button>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteConfirmDocId} onOpenChange={(open) => { if (!open) setDeleteConfirmDocId(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete document?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently remove the document, its parsed data, and all associated embeddings. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleting}
              onClick={async () => {
                if (deleteConfirmDocId) {
                  await handleDeleteDocument(deleteConfirmDocId);
                }
              }}
            >
              {deleting ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <ExcelSkillModal open={excelSkillOpen} onOpenChange={setExcelSkillOpen} threadId={threadId ?? ''} documents={documents} />
    </div>
  );
};

export default RightSidebar;
