import { useCallback, useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Upload, Send, Brain, Globe, Loader2, X, Edit2, Check, Trash2, MessageSquare, ListChecks } from 'lucide-react';
import { api, Chat, Thread } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { ChatMessage } from '@/components/ChatMessage';
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
import MindMapModal from '@/components/MindMapModal';
import ThreadInstructionsModal from '@/components/ThreadInstructionsModal';

const ThreadView = () => {
  const { threadId } = useParams();
  const { user, setUser } = useAuth();
  const [chats, setChats] = useState<Chat[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [webEnhanced, setWebEnhanced] = useState(false);
  const [useSelfKnowledge, setUseSelfKnowledge] = useState(false);
  const [documents, setDocuments] = useState<any[]>([]);
  const [lastSources, setLastSources] = useState<any>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [fileNames, setFileNames] = useState<Record<number, string>>({});
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [progressMap, setProgressMap] = useState<Record<number, number>>({});
  const [mindMapOpen, setMindMapOpen] = useState(false);
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [useContext, setUseContext] = useState(false);
  const [instructionsOpen, setInstructionsOpen] = useState(false);

  const selfKnowledgePreferenceKey = user?.userId
    ? `selfKnowledgePreference:${user.userId}`
    : null;

  const contextPreferenceKey = user?.userId && threadId
    ? `contextPreference:${user.userId}:${threadId}`
    : null;

  const updateUserThreadState = useCallback(
    (nextChats: Chat[], extra?: Partial<Thread>) => {
      if (!user || !threadId) return;

      const existingThread = user.threads?.[threadId];
      const nowIso = new Date().toISOString();

      const updatedThread: Thread = {
        thread_name: extra?.thread_name ?? existingThread?.thread_name ?? 'New Chat',
        createdAt: extra?.createdAt ?? existingThread?.createdAt ?? nowIso,
        updatedAt: extra?.updatedAt ?? existingThread?.updatedAt ?? nowIso,
        documents: extra?.documents ?? existingThread?.documents ?? [],
        chats: nextChats,
      };

      const updatedUser = {
        ...user,
        threads: {
          ...user.threads,
          [threadId]: updatedThread,
        },
      };

      setUser(updatedUser);
    },
    [setUser, threadId, user]
  );

  useEffect(() => {
    if (!threadId || !user?.userId) {
      return;
    }
    loadThread();
  }, [threadId, user?.userId]);

  // Sync local documents state when user context changes (e.g. after document deletion from RightSidebar)
  useEffect(() => {
    if (!threadId || !user?.threads?.[threadId]) return;
    const contextDocs = user.threads[threadId].documents || [];
    setDocuments(contextDocs);
  }, [threadId, user?.threads?.[threadId]?.documents]);

  useEffect(() => {
    if (!selfKnowledgePreferenceKey || typeof window === 'undefined') {
      setUseSelfKnowledge(false);
      return;
    }

    const storedPreference = window.localStorage.getItem(selfKnowledgePreferenceKey);
    setUseSelfKnowledge(storedPreference === 'true');
  }, [selfKnowledgePreferenceKey]);

  useEffect(() => {
    if (!contextPreferenceKey || typeof window === 'undefined') {
      setUseContext(false);
      return;
    }

    const storedContextPref = window.localStorage.getItem(contextPreferenceKey);
    setUseContext(storedContextPref === 'true');
  }, [contextPreferenceKey]);

  useEffect(() => {
    scrollToBottom();
  }, [chats]);

  const scrollToBottom = () => {
    if (scrollRef.current) {
      const rootEl = scrollRef.current as HTMLElement;
      const viewport = rootEl.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement | null;
      if (viewport) {
        try {
          viewport.scrollTo({ top: viewport.scrollHeight, behavior: 'smooth' });
        } catch {
          viewport.scrollTop = viewport.scrollHeight;
        }
      } else {
        try {
          rootEl.scrollTo({ top: rootEl.scrollHeight, behavior: 'smooth' });
        } catch {
          rootEl.scrollTop = rootEl.scrollHeight;
        }
      }
    }
  };

  const loadThread = async (options?: { suppressErrorToast?: boolean }) => {
    if (!threadId) return;

    try {
      const thread = await api.getThread(threadId);
      const nextChats = thread.chats || [];
      setChats(nextChats);
      setDocuments(thread.documents || []);
      updateUserThreadState(nextChats, {
        documents: thread.documents || [],
        thread_name: thread.thread_name,
        createdAt: thread.createdAt,
        updatedAt: thread.updatedAt,
      });
    } catch (error) {
      if (!options?.suppressErrorToast) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to load thread';
        toast.error(errorMessage);
      }
    }
  };

  const handleDeleteChat = async (index: number) => {
    if (!threadId) return;

    try {
      const response = await api.deleteChat(threadId, index);
      const status = response?.status;
      const isSuccess =
        (typeof status === 'string' && status.toLowerCase() === 'success') ||
        (typeof status === 'boolean' && status);

      if (isSuccess) {
        if (Array.isArray(response?.chats)) {
          const next = response.chats;
          setChats(next);
          updateUserThreadState(next, { updatedAt: new Date().toISOString() });
        } else {
          setChats(prev => {
            const updated = prev.filter((_, chatIndex) => chatIndex !== index);
            updateUserThreadState(updated, { updatedAt: new Date().toISOString() });
            return updated;
          });
        }
        setLastSources(null);
        toast.success('Message deleted');
        return;
      }

      toast.error('Failed to delete message');
      await loadThread({ suppressErrorToast: true });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete message';
      toast.error(errorMessage);
      await loadThread({ suppressErrorToast: true });
    }
  };

  const handleClearChats = async () => {
    if (!threadId) {
      setClearConfirmOpen(false);
      return;
    }

    if (chats.length === 0) {
      setClearConfirmOpen(false);
      return;
    }

    try {
      const response = await api.clearThreadChats(threadId);
      const status = response?.status;
      const isSuccess =
        (typeof status === 'string' && status.toLowerCase() === 'success') ||
        (typeof status === 'boolean' && status);

      if (isSuccess) {
        const fresh = response?.chats ?? [];
        setChats(fresh);
        updateUserThreadState(fresh, { updatedAt: new Date().toISOString() });
        setLastSources(null);
        toast.success('All messages cleared');
      } else {
        toast.error('Failed to clear messages');
        await loadThread({ suppressErrorToast: true });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to clear messages';
      toast.error(errorMessage);
      await loadThread({ suppressErrorToast: true });
    } finally {
      setClearConfirmOpen(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const files = Array.from(e.target.files);
    setPendingFiles(prev => [...prev, ...files]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removePendingFile = (index: number) => {
    setPendingFiles(prev => prev.filter((_, i) => i !== index));
    setFileNames(prev => {
      const updated = { ...prev };
      delete updated[index];
      return updated;
    });
    setProgressMap(prev => {
      const updated = { ...prev };
      delete updated[index];
      return updated;
    });
    if (editingIndex === index) setEditingIndex(null);
  };

  const updateFileName = (index: number, newName: string) => {
    setFileNames(prev => ({ ...prev, [index]: newName }));
  };

  const uploadPendingFiles = async () => {
    if (!threadId || pendingFiles.length === 0) return;

    const processed = pendingFiles.map((file, idx) => {
      const name = fileNames[idx];
      return name ? new File([file], name, { type: file.type }) : file;
    });

    setUploading(true);
    setProgressMap({});

    try {
      const response = await api.uploadFilesWithProgress({
        thread_id: threadId,
        files: processed,
        onProgress: ({ fileIndex, percent }) => {
          setProgressMap(prev => ({ ...prev, [fileIndex]: percent }));
        },
      });
      setDocuments(prev => [...prev, ...response.documents]);
      toast.success('Files uploaded successfully!');

      setPendingFiles([]);
      setFileNames({});
      setProgressMap({});
      setEditingIndex(null);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to upload files';
      toast.error(errorMessage);
    } finally {
      setUploading(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || !threadId || loading) return;

    const userMessage: Chat = {
      type: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setChats(prev => {
      const updated = [...prev, userMessage];
      updateUserThreadState(updated, { updatedAt: new Date().toISOString() });
      return updated;
    });
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setLoading(true);

    const agentMessage: Chat = {
      type: 'agent',
      content: '',
      timestamp: new Date().toISOString(),
    };
    setChats(prev => {
      const updated = [...prev, agentMessage];
      updateUserThreadState(updated, { updatedAt: new Date().toISOString() });
      return updated;
    });

    try {
      const mode = webEnhanced ? 'External' : 'Internal';
      const response = await api.query(
        threadId,
        userMessage.content,
        mode,
        mode === 'Internal' ? useSelfKnowledge : false,
        useContext
      );

      // Support both legacy shape and new `sources` wrapper; default to empty arrays
      const docsUsed = response.sources?.documents_used ?? response.docs_used ?? [];
      const webUsed = response.sources?.web_used ?? response.web_used ?? [];
      const chartsUsed = response.sources?.charts_used ?? [];
      const sqlUsed = response.sources?.sql_used ?? [];

      setChats(prev => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          content: response.answer,
          sources: {
            documents_used: docsUsed,
            web_used: webUsed,
            charts_used: chartsUsed,
            sql_used: sqlUsed,
          },
          // Map enhanced metadata from backend
          thought_process: response.thought_process,
        };
        updateUserThreadState(updated, { updatedAt: new Date().toISOString() });
        return updated;
      });

      setLastSources({
        docsUsed,
        webUsed,
        chartsUsed,
        sqlUsed,
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to get response';
      toast.error(errorMessage);
      setChats(prev => {
        const updated = prev.slice(0, -2);
        updateUserThreadState(updated, { updatedAt: new Date().toISOString() });
        return updated;
      });
      setInput(userMessage.content);
    } finally {
      setLoading(false);
    }
  };


  const handleModeToggle = (checked: boolean) => {
    setWebEnhanced(checked);

    if (checked) {
      setUseSelfKnowledge(false);
      return;
    }

    if (!selfKnowledgePreferenceKey || typeof window === 'undefined') {
      setUseSelfKnowledge(false);
      return;
    }

    const storedPreference = window.localStorage.getItem(selfKnowledgePreferenceKey);
    setUseSelfKnowledge(storedPreference === 'true');
  };

  const handleSelfKnowledgeToggle = (checked: boolean) => {
    setUseSelfKnowledge(checked);

    if (!selfKnowledgePreferenceKey || typeof window === 'undefined') {
      return;
    }

    window.localStorage.setItem(selfKnowledgePreferenceKey, String(checked));
  };

  const handleContextToggle = (checked: boolean) => {
    setUseContext(checked);

    if (!contextPreferenceKey || typeof window === 'undefined') {
      return;
    }

    window.localStorage.setItem(contextPreferenceKey, String(checked));
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="border-b p-4 flex items-center justify-between bg-background">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            {webEnhanced ? (
              <Globe className="w-5 h-5 text-primary" />
            ) : (
              <Brain className="w-5 h-5 text-primary" />
            )}
            <div>
              <p className="font-medium">
                {webEnhanced ? 'Web Enhanced' : 'Internal Knowledge'}
              </p>
              <p className="text-xs text-muted-foreground">
                {webEnhanced ? 'Uses documents + web search' : 'Uses only uploaded documents'}
              </p>
            </div>
          </div>
          <Switch checked={webEnhanced} onCheckedChange={handleModeToggle} />
          {!webEnhanced && (
            <div className="flex items-center gap-2">
              <Label htmlFor="self-knowledge-toggle" className="text-sm">
                Self Knowledge
              </Label>
              <Switch
                id="self-knowledge-toggle"
                checked={useSelfKnowledge}
                onCheckedChange={handleSelfKnowledgeToggle}
              />
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setInstructionsOpen(true)}
            disabled={!threadId}
            title="Thread Instructions"
          >
            <ListChecks className="w-4 h-4 mr-2" />
            Instructions
          </Button>
          <div className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-muted-foreground" />
            <Label htmlFor="context-toggle" className="text-sm">
              Chat Context
            </Label>
            <Switch
              id="context-toggle"
              checked={useContext}
              onCheckedChange={handleContextToggle}
            />
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setClearConfirmOpen(true)}
            disabled={!threadId || chats.length === 0}
          >
            <Trash2 className="w-4 h-4 mr-2" />
            Clear All
          </Button>
        </div>

      </div>

      {/* Chat Area */}
      <ScrollArea ref={scrollRef} className="flex-1 p-4">
        <div className="max-w-4xl mx-auto space-y-4">
          {chats.map((chat, index) => {
            const isPendingAgentResponse =
              loading &&
              index === chats.length - 1 &&
              chat.type === 'agent' &&
              chat.content === '';

            return (
              <div key={index}>
                <ChatMessage
                  chat={chat}
                  threadId={threadId}
                  onDelete={isPendingAgentResponse ? undefined : () => handleDeleteChat(index)}
                />
              </div>
            );
          })}
          {loading && chats[chats.length - 1]?.type === 'agent' && chats[chats.length - 1]?.content === '' && (
            <div className="flex gap-3 p-4">
              <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                <Loader2 className="w-5 h-5 text-primary animate-spin" />
              </div>
              <div className="bg-muted rounded-2xl px-4 py-3">
                <p className="text-sm">Thinking...</p>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input Area */}
      <div className="border-t p-4 bg-background">
        <div className="max-w-4xl mx-auto flex gap-2">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileSelect}
            className="hidden"
            accept=".xls,.xlsx,.csv,.jpg,.jpeg,.png,.tiff,.bmp,.gif"
          />
          <Button
            variant="outline"
            size="icon"
            onClick={() => fileInputRef.current?.click()}
            disabled={loading}
          >
            <Upload className="w-4 h-4" />
          </Button>
          {/* Pending attachments list with rename/remove and progress */}
          {pendingFiles.length > 0 && (
            <div className="flex-1 flex flex-col gap-2 max-h-40 overflow-y-auto p-2 border rounded-md">
              <p className="text-xs text-muted-foreground">Attachments ready to upload:</p>
              {pendingFiles.map((file, index) => (
                <div key={index} className="flex items-center gap-2 bg-muted/50 p-2 rounded">
                  {editingIndex === index ? (
                    <Input
                      value={fileNames[index] || file.name}
                      onChange={(e) => updateFileName(index, e.target.value)}
                      className="flex-1 h-8"
                      autoFocus
                    />
                  ) : (
                    <span className="flex-1 text-sm truncate" title={fileNames[index] || file.name}>{fileNames[index] || file.name}</span>
                  )}
                  {typeof progressMap[index] === 'number' && (
                    <span className="text-xs text-muted-foreground w-12 text-right">{progressMap[index]}%</span>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setEditingIndex(editingIndex === index ? null : index)}
                    disabled={uploading}
                  >
                    {editingIndex === index ? <Check className="w-4 h-4" /> : <Edit2 className="w-4 h-4" />}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => removePendingFile(index)}
                    disabled={uploading}
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
          <Textarea
            ref={textareaRef}
            placeholder="Ask a question..."
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              // Auto-resize: reset to single row then expand to content
              e.target.style.height = 'auto';
              e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            disabled={loading}
            rows={1}
            className="flex-1 min-h-[40px] max-h-[160px] resize-none py-2"
          />
          <div className="flex items-center gap-2">
            {pendingFiles.length > 0 && (
              <Button
                onClick={uploadPendingFiles}
                disabled={uploading}
                variant="secondary"
              >
                {uploading ? 'Uploading…' : 'Upload'}
              </Button>
            )}
            <Button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="bg-gradient-primary"
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>
      {/* Mind Map Modal */}
      {threadId && (
        <MindMapModal open={mindMapOpen} onOpenChange={setMindMapOpen} threadId={threadId} />
      )}

      {/* Thread Instructions Modal */}
      {threadId && (
        <ThreadInstructionsModal
          open={instructionsOpen}
          onOpenChange={setInstructionsOpen}
          threadId={threadId}
        />
      )}

      <AlertDialog open={clearConfirmOpen} onOpenChange={setClearConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Clear all messages?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes every chat message in this thread. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel type="button">Cancel</AlertDialogCancel>
            <AlertDialogAction
              type="button"
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={async () => {
                await handleClearChats();
              }}
            >
              Clear
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default ThreadView;
