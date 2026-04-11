import React, { useState, useRef, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Loader2, RefreshCcw, ShieldAlert } from 'lucide-react';
import { Document, api } from '@/lib/api';
import { toast } from 'sonner';
import SafeMarkdownRenderer from './SafeMarkdownRenderer';

type Props = {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  threadId: string;
  documents: Document[];
};

const ALL_DOCS_ID = '__ALL_DOCS__';

const MAX_POLL_COUNT = 60;

const SummaryModal: React.FC<Props> = ({ open, onOpenChange, threadId, documents }) => {
  const [selectedDoc, setSelectedDoc] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [progressMessages, setProgressMessages] = useState<string[]>([]);
  const [view, setView] = useState<'select' | 'progress' | 'display' | 'error'>('select');

  const pollingActiveRef = useRef<boolean>(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastPolledDocRef = useRef<string | null>(null);
  const lastPolledIsRegenerateRef = useRef<boolean>(false);
  const pollCountRef = useRef<number>(0);

  const handleToggle = (docId: string) => {
    setSelectedDoc(prev => (prev === docId ? null : docId));
  };

  const generateSummary = async (isRegenerate: boolean = false) => {
    if (loading) return;
    if (!selectedDoc) {
      toast.error('Please select a document');
      return;
    }

    setLoading(true);
    setSummary(null);
    setMessage(null);

    try {
      const isAll = selectedDoc === ALL_DOCS_ID;
      const res = isAll ? await api.summaryGlobal(threadId, isRegenerate) : await api.summary(threadId, selectedDoc, isRegenerate);

      if (res?.status && res.summary) {
        setSummary(res.summary);
        toast.success('Summary generated');
        pollingActiveRef.current = false;
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
          timeoutRef.current = null;
        }
        setView('display');
        setLoading(false);
      } else if (res?.failed) {
        const err = res.error || 'Generation failed';
        setMessage(err);
        toast.error(err);
        pollingActiveRef.current = false;
        if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
        setView('error');
        setLoading(false);
      } else if (res?.status === false && res.error) {
        const msg = res.error;
        if (/disable|not enabled/i.test(msg)) {
          toast.info(msg);
          setLoading(false);
        } else {
          setMessage(msg);
          setProgressMessages((msgs) => (msgs[msgs.length - 1] === msg ? msgs : [...msgs, msg]));
          setView('progress');
          lastPolledDocRef.current = selectedDoc;
          lastPolledIsRegenerateRef.current = false;
          pollingActiveRef.current = true;
          pollCountRef.current = 0;
          schedulePoll();
        }
      } else {
        setMessage('Generating summary...');
        setProgressMessages((msgs) => (msgs[msgs.length - 1] === 'Generating summary...' ? msgs : [...msgs, 'Generating summary...']));
        setView('progress');
        lastPolledDocRef.current = selectedDoc;
        lastPolledIsRegenerateRef.current = false;
        pollingActiveRef.current = true;
        pollCountRef.current = 0;
        schedulePoll();
      }
    } catch (e) {
      console.error('Error generating summary:', e);
      toast.error('Failed to generate summary');
      setLoading(false);
    }
  };

  const schedulePoll = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    timeoutRef.current = setTimeout(async () => {
      if (!pollingActiveRef.current) return;
      const docId = lastPolledDocRef.current;
      if (!docId) return;
      try {
        pollCountRef.current += 1;
        if (pollCountRef.current >= MAX_POLL_COUNT) {
          pollingActiveRef.current = false;
          setMessage('Generation timed out. Please try again.');
          setView('error');
          setLoading(false);
          return;
        }
        const isAll = docId === ALL_DOCS_ID;
        const res = isAll ? await api.summaryGlobal(threadId, false) : await api.summary(threadId, docId, false);
        if (res?.status && res.summary) {
          setSummary(res.summary);
          setMessage(null);
          pollingActiveRef.current = false;
          setView('display');
          setLoading(false);
          return;
        }
        if (res?.failed) {
          pollingActiveRef.current = false;
          setMessage(res.error || 'Generation failed');
          setView('error');
          setLoading(false);
          return;
        }
        if (res?.error) {
          setMessage(res.error);
          setProgressMessages((msgs) => (msgs[msgs.length - 1] === res.error ? msgs : [...msgs, res.error!]));
          setView('progress');
        }
      } catch (e) {
        // non-fatal
      }
      if (pollingActiveRef.current) schedulePoll();
    }, 5000);
  };

  const handleClose = (open: boolean) => {
    if (!open) {
      setSelectedDoc(null);
      setSummary(null);
      setMessage(null);
      setProgressMessages([]);
      setView('select');
      setLoading(false);
      pollingActiveRef.current = false;
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      lastPolledDocRef.current = null;
      pollCountRef.current = 0;
    }
    onOpenChange(open);
  };

  useEffect(() => {
    if (!open) {
      pollingActiveRef.current = false;
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    }
  }, [open]);

  const selectedDocObj = selectedDoc && selectedDoc !== ALL_DOCS_ID ? documents.find(d => d.docId === selectedDoc) : null;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Generate Summary</DialogTitle>
          <DialogDescription>
            {view === 'select' && 'Select a document (or All Documents) and generate its summary'}
            {view === 'progress' && (
              <span>
                Generating for: <span className="font-medium">{selectedDoc === ALL_DOCS_ID ? 'All Documents in Thread' : (selectedDocObj?.title || 'Selected Document')}</span>
              </span>
            )}
            {view === 'display' && (
              <span>
                {selectedDoc === ALL_DOCS_ID ? (
                  <>Scope: <span className="font-medium">All Documents in Thread</span></>
                ) : selectedDocObj ? (
                  <>Document: <span className="font-medium">{selectedDocObj.title}</span></>
                ) : null}
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        {view === 'select' && (
          <div className="flex-1 overflow-hidden flex flex-col gap-6">
            {/* Document Selection */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-base font-semibold">Select Document</Label>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedDoc(null)}
                  disabled={!selectedDoc}
                >
                  Clear Selection
                </Button>
              </div>

              <ScrollArea className="h-64 border rounded-lg p-3">
                <div className="w-full overflow-hidden">
                  {documents.length === 0 ? (
                    <p className="text-center text-muted-foreground py-8">
                      No documents available in this thread
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {/* All Documents option */}
                      <div
                        key={ALL_DOCS_ID}
                        className={`flex items-start space-x-3 p-3 rounded-lg group hover:bg-accent/30 cursor-pointer transition-colors ${selectedDoc === ALL_DOCS_ID ? 'bg-accent/40' : ''}`}
                        onClick={() => handleToggle(ALL_DOCS_ID)}
                      >
                        <Checkbox
                          checked={selectedDoc === ALL_DOCS_ID}
                          onCheckedChange={() => handleToggle(ALL_DOCS_ID)}
                          className="mt-1 flex-shrink-0"
                        />
                        <div className="flex-1 min-w-0 overflow-hidden">
                          <p className="font-medium truncate block w-full group-hover:text-primary-foreground">All Documents in Thread</p>
                          <p className="text-sm text-muted-foreground group-hover:text-primary-foreground/90">Generate a summary using all uploaded documents.</p>
                        </div>
                      </div>
                      {documents.map((doc) => (
                        <div
                          key={doc.docId}
                          className={`flex items-start space-x-3 p-3 rounded-lg group hover:bg-accent/30 cursor-pointer transition-colors ${selectedDoc === doc.docId ? 'bg-accent/40' : ''}`}
                          onClick={() => handleToggle(doc.docId)}
                        >
                          <Checkbox
                            checked={selectedDoc === doc.docId}
                            onCheckedChange={() => handleToggle(doc.docId)}
                            className="mt-1 flex-shrink-0"
                          />
                          <div className="flex-1 min-w-0 overflow-hidden">
                            <p className="font-medium truncate block w-full group-hover:text-primary-foreground" title={doc.title}>{doc.title}</p>
                            <p className="text-sm text-muted-foreground group-hover:text-primary-foreground/90">
                              {doc.type.toUpperCase()} • {new Date(doc.time_uploaded).toLocaleDateString()}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </ScrollArea>

              <p className="text-sm text-muted-foreground">
                {selectedDoc ? (selectedDoc === ALL_DOCS_ID ? 'All documents selected' : '1 document selected') : 'No document selected'}
              </p>
            </div>

            {/* Generate Button */}
            <Button
              onClick={() => generateSummary(false)}
              disabled={loading || !selectedDoc}
              className="w-full bg-gradient-primary"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Requesting...
                </>
              ) : (
                'Generate Summary'
              )}
            </Button>
          </div>
        )}

        {view === 'progress' && (
          <div className="flex-1 flex flex-col items-center justify-center text-center gap-4">
            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
              <Loader2 className="w-6 h-6 text-primary animate-spin" />
            </div>
            <div>
              <h3 className="text-lg font-semibold mb-2">{selectedDoc === ALL_DOCS_ID ? 'All Documents in Thread' : (selectedDocObj?.title || 'Selected Document')}</h3>
              <div className="space-y-2">
                {progressMessages.length > 0 ? (
                  progressMessages.map((m, idx) => (
                    <p key={idx} className="text-sm text-muted-foreground whitespace-pre-wrap">{m}</p>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">Generating summary…</p>
                )}
              </div>
            </div>
            <div className="mt-4">
              <Button
                variant="outline"
                onClick={() => {
                  pollingActiveRef.current = false;
                  if (timeoutRef.current) {
                    clearTimeout(timeoutRef.current);
                    timeoutRef.current = null;
                  }
                  setView('select');
                  setProgressMessages([]);
                  setMessage(null);
                  setSelectedDoc(null);
                  setLoading(false);
                }}
              >
                Back to documents
              </Button>
            </div>
          </div>
        )}

        {view === 'error' && (
          <div className="flex-1 flex flex-col items-center justify-center text-center gap-4">
            <div className="w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center">
              <ShieldAlert className="w-6 h-6 text-destructive" />
            </div>
            <div>
              <h3 className="text-lg font-semibold mb-2">Generation Failed</h3>
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">{message || 'An unexpected error occurred.'}</p>
            </div>
            <div className="flex gap-3 mt-4">
              <Button variant="outline" onClick={() => { pollingActiveRef.current = false; if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; } setView('select'); setProgressMessages([]); setMessage(null); setSelectedDoc(null); setLoading(false); }}>
                Back to documents
              </Button>
              <Button onClick={() => generateSummary(true)} disabled={loading}>
                {loading ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Retrying...</> : <><RefreshCcw className="w-4 h-4 mr-2" />Retry</>}
              </Button>
            </div>
          </div>
        )}

        {view === 'display' && summary && (
          <div className="flex-1 overflow-hidden flex flex-col gap-4">
            {/* Summary Display */}
            <ScrollArea className="flex-1 border rounded-lg p-4 bg-muted/30 h-[50vh] md:h-[60vh] overflow-auto">
              <SafeMarkdownRenderer content={summary} enableMarkdown />
            </ScrollArea>

            {/* Action Button */}
            <div className="flex gap-3">
              <Button
                variant="outline"
                className="ml-auto"
                onClick={() => generateSummary(true)}
                disabled={loading}
              >
                <RefreshCcw className="w-4 h-4 mr-2" />
                Regenerate
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default SummaryModal;
