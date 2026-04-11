import React, { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card } from '@/components/ui/card';
import {
  ArrowLeft,
  Download,
  FileSpreadsheet,
  FolderOpen,
  Loader2,
  Plus,
  Trash2,
} from 'lucide-react';
import { api, Document, ExcelSkillListItem } from '@/lib/api';
import { toast } from 'sonner';
import { API_URL } from '../../config';
import { getAuthToken } from '@/lib/api';

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  threadId: string;
  documents: Document[];
}

type View = 'history' | 'generate' | 'result';

const QUICK_ACTIONS = [
  { label: 'Export all data', prompt: 'Export all spreadsheet data to Excel with proper formatting' },
  { label: 'Pivot table', prompt: 'Create a pivot table summarizing the data with key aggregations' },
  { label: 'Summary report', prompt: 'Create a summary report with key metrics and a chart' },
  { label: 'Filtered view', prompt: 'Create a filtered and sorted view of the most important data' },
];

const ExcelSkillModal: React.FC<Props> = ({ open, onOpenChange, threadId, documents }) => {
  // View state
  const [view, setView] = useState<View>('history');

  // History view
  const [savedFiles, setSavedFiles] = useState<ExcelSkillListItem[]>([]);
  const [loadingList, setLoadingList] = useState(false);

  // Generate view
  const [requestText, setRequestText] = useState('');
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [generating, setGenerating] = useState(false);
  const [trackingId, setTrackingId] = useState<string | null>(null);
  const [result, setResult] = useState<{
    file_name: string;
    download_url: string;
    description: string;
    sheet_count: number;
    total_rows: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = React.useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Load saved files when opening in history view
  const loadSavedFiles = useCallback(async () => {
    setLoadingList(true);
    try {
      const res = await api.excelSkillList(threadId);
      setSavedFiles(res.files);
    } catch {
      // silently fail — show empty list
    } finally {
      setLoadingList(false);
    }
  }, [threadId]);

  useEffect(() => {
    if (open && view === 'history') {
      loadSavedFiles();
    }
  }, [open, view, loadSavedFiles]);

  const toggleDoc = (docId: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  const handleGenerate = async () => {
    if (!requestText.trim()) {
      toast.error('Please describe what Excel file you want to create');
      return;
    }

    setGenerating(true);
    setError(null);
    setResult(null);

    try {
      const response = await api.excelSkillGenerate(
        threadId,
        requestText.trim(),
        selectedDocIds.length > 0 ? selectedDocIds : undefined
      );

      if (response.tracking_id) {
        setTrackingId(response.tracking_id);
        pollRef.current = setInterval(async () => {
          try {
            const status = await api.excelSkillStatus(response.tracking_id!);
            if (status.status && status.result) {
              setResult(status.result);
              setGenerating(false);
              setView('result');
              if (pollRef.current) clearInterval(pollRef.current);
            } else if (status.failed) {
              setError(status.error || 'Generation failed');
              setGenerating(false);
              if (pollRef.current) clearInterval(pollRef.current);
            }
          } catch (e) {
            console.error('Polling error:', e);
          }
        }, 2000);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start generation');
      setGenerating(false);
    }
  };

  const handleDownloadUrl = (downloadUrl: string) => {
    const token = getAuthToken();
    const url = `${API_URL}${downloadUrl}${token ? `?token=${encodeURIComponent(token)}` : ''}`;
    window.open(url, '_blank');
  };

  const handleDownload = () => {
    if (!result) return;
    handleDownloadUrl(result.download_url);
  };

  const handleDelete = async (trackingId: string) => {
    try {
      await api.excelSkillDelete(threadId, trackingId);
      setSavedFiles((prev) => prev.filter((f) => f.tracking_id !== trackingId));
      toast.success('File deleted');
    } catch {
      toast.error('Failed to delete file');
    }
  };

  const handleResetGenerate = () => {
    setRequestText('');
    setResult(null);
    setError(null);
    setTrackingId(null);
    setGenerating(false);
    if (pollRef.current) clearInterval(pollRef.current);
  };

  const handleClose = () => {
    handleResetGenerate();
    setView('history');
    onOpenChange(false);
  };

  const goToGenerate = () => {
    handleResetGenerate();
    setView('generate');
  };

  const goToHistory = () => {
    handleResetGenerate();
    setView('history');
    loadSavedFiles();
  };

  const formatDate = (iso: string) => {
    if (!iso) return '';
    try {
      const d = new Date(iso);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
        + ' ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    } catch {
      return iso;
    }
  };

  const getDescription = () => {
    switch (view) {
      case 'history': return 'View generated files or create a new one.';
      case 'generate': return 'Describe the Excel file you want to create from your documents.';
      case 'result': return 'Your Excel file is ready to download.';
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose(); }}>
      <DialogContent className="max-w-lg max-h-[85vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileSpreadsheet className="w-5 h-5 text-green-600" />
            Excel Builder
          </DialogTitle>
          <DialogDescription>{getDescription()}</DialogDescription>
        </DialogHeader>

        {/* ── History View ── */}
        {view === 'history' && (
          <div className="flex-1 min-h-0 flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-muted-foreground">Generated Files</h3>
              <Button size="sm" onClick={goToGenerate}>
                <Plus className="w-4 h-4 mr-1" /> Create New
              </Button>
            </div>

            <ScrollArea className="flex-1 pr-2">
              <div className="space-y-2">
                {loadingList && (
                  <div className="flex justify-center py-8">
                    <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                  </div>
                )}

                {!loadingList && savedFiles.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <FolderOpen className="w-12 h-12 text-muted-foreground/40 mb-3" />
                    <p className="text-sm text-muted-foreground">No Excel files yet.</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Create your first file to get started.
                    </p>
                    <Button size="sm" className="mt-4" onClick={goToGenerate}>
                      <Plus className="w-4 h-4 mr-1" /> Create Your First
                    </Button>
                  </div>
                )}

                {!loadingList && savedFiles.map((item) => (
                  <Card key={item.tracking_id} className="p-4 hover:bg-accent/20 transition-colors">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <FileSpreadsheet className="w-4 h-4 text-green-600 flex-none" />
                          <span className="font-medium text-sm truncate">{item.file_name}</span>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                          {item.description}
                        </p>
                        <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                          <span>{item.sheet_count} sheet(s)</span>
                          <span>{item.total_rows} rows</span>
                          {item.created_at && (
                            <span>{formatDate(item.created_at)}</span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-1 flex-none">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => handleDownloadUrl(item.download_url)}
                          title="Download"
                        >
                          <Download className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive hover:text-destructive"
                          onClick={() => handleDelete(item.tracking_id)}
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </ScrollArea>
          </div>
        )}

        {/* ── Generate View ── */}
        {view === 'generate' && (
          <ScrollArea className="flex-1 pr-2">
            <div className="space-y-4 py-2">
              {/* Quick action chips */}
              <div>
                <label className="text-sm font-medium mb-1.5 block">Quick Actions</label>
                <div className="flex flex-wrap gap-2">
                  {QUICK_ACTIONS.map((action) => (
                    <Button
                      key={action.label}
                      variant="outline"
                      size="sm"
                      className="text-xs"
                      onClick={() => setRequestText(action.prompt)}
                      disabled={generating}
                    >
                      {action.label}
                    </Button>
                  ))}
                </div>
              </div>

              {/* Request text */}
              <div>
                <label className="text-sm font-medium mb-1.5 block">What do you want to create?</label>
                <Textarea
                  placeholder="e.g., Create a pivot table of sales by region with a bar chart and totals row..."
                  value={requestText}
                  onChange={(e) => setRequestText(e.target.value)}
                  rows={4}
                  disabled={generating}
                  className="resize-none"
                />
              </div>

              {/* Document selection */}
              {documents.length > 0 && (
                <div>
                  <label className="text-sm font-medium mb-1.5 block">
                    Source Documents <span className="text-muted-foreground font-normal">(optional — all docs used if none selected)</span>
                  </label>
                  <div className="border rounded-md p-2 space-y-1.5 max-h-32 overflow-y-auto">
                    {documents.map((doc) => (
                      <label
                        key={doc.docId}
                        className="flex items-center gap-2 text-sm cursor-pointer hover:bg-accent/40 rounded px-1 py-0.5"
                      >
                        <Checkbox
                          checked={selectedDocIds.includes(doc.docId)}
                          onCheckedChange={() => toggleDoc(doc.docId)}
                          disabled={generating}
                        />
                        <span className="truncate" title={doc.title}>{doc.title}</span>
                        <span className="text-xs text-muted-foreground ml-auto flex-none">{doc.type}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* Generate button */}
              <Button
                className="w-full"
                onClick={handleGenerate}
                disabled={generating || !requestText.trim()}
              >
                {generating ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Generating Excel...
                  </>
                ) : (
                  <>
                    <FileSpreadsheet className="w-4 h-4 mr-2" />
                    Generate Excel
                  </>
                )}
              </Button>

              {/* Error */}
              {error && (
                <div className="bg-destructive/10 text-destructive text-sm rounded-md p-3">
                  {error}
                  <Button variant="ghost" size="sm" className="mt-2" onClick={handleResetGenerate}>
                    Try Again
                  </Button>
                </div>
              )}

              {/* Back button */}
              <Button variant="outline" className="w-full" onClick={goToHistory} disabled={generating}>
                <ArrowLeft className="w-4 h-4 mr-2" /> Back to Files
              </Button>
            </div>
          </ScrollArea>
        )}

        {/* ── Result View ── */}
        {view === 'result' && result && (
          <div className="space-y-4 py-2">
            <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-900 rounded-md p-4 space-y-3">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="w-5 h-5 text-green-600" />
                <span className="font-medium">{result.file_name}</span>
              </div>
              <p className="text-sm text-muted-foreground">{result.description}</p>
              <div className="flex gap-4 text-sm">
                <span><strong>{result.sheet_count}</strong> sheet(s)</span>
                <span><strong>{result.total_rows}</strong> rows</span>
              </div>
              <div className="flex gap-2">
                <Button onClick={handleDownload} className="flex-1">
                  <Download className="w-4 h-4 mr-2" />
                  Download
                </Button>
                <Button variant="outline" onClick={goToGenerate}>
                  Create Another
                </Button>
              </div>
            </div>
            <Button variant="outline" className="w-full" onClick={goToHistory}>
              <ArrowLeft className="w-4 h-4 mr-2" /> Back to Files
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default ExcelSkillModal;
