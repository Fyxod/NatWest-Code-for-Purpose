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
import { Card } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  ArrowLeft,
  BarChart3,
  Download,
  FolderOpen,
  LineChart,
  Loader2,
  PieChart,
  Plus,
  Trash2,
  Sparkles,
} from 'lucide-react';
import { api, ChartSkillListItem, Document, getAuthToken } from '@/lib/api';
import { toast } from 'sonner';
import { API_URL } from '../../config';
import ChartModal from './ChartModal';

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  threadId: string;
  documents: Document[];
}

type View = 'history' | 'generate' | 'result';

const QUICK_ACTIONS = [
  {
    label: 'Monthly trend',
    chartType: 'line',
    prompt: 'Create a monthly trend chart showing changes over time with clear series labels.',
  },
  {
    label: 'Category compare',
    chartType: 'bar',
    prompt: 'Create a category comparison chart with top categories and their totals.',
  },
  {
    label: 'Part to whole',
    chartType: 'pie',
    prompt: 'Create a part-to-whole chart that highlights percentage share per category.',
  },
  {
    label: 'Metric dashboard',
    chartType: 'composed',
    prompt: 'Create a multi-metric dashboard chart combining bars and lines for key indicators.',
  },
];

const ChartSkillModal: React.FC<Props> = ({ open, onOpenChange, threadId, documents }) => {
  const [view, setView] = useState<View>('history');

  const [savedCharts, setSavedCharts] = useState<ChartSkillListItem[]>([]);
  const [loadingList, setLoadingList] = useState(false);

  const [requestText, setRequestText] = useState('');
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [chartType, setChartType] = useState<string>('auto');
  const [generating, setGenerating] = useState(false);
  const [trackingId, setTrackingId] = useState<string | null>(null);
  const [result, setResult] = useState<ChartSkillListItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = React.useRef<ReturnType<typeof setInterval> | null>(null);

  const [previewChartId, setPreviewChartId] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState<string>('Interactive Chart');
  const [previewJsonUrl, setPreviewJsonUrl] = useState<string | undefined>(undefined);
  const [previewCsvUrl, setPreviewCsvUrl] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const loadSavedCharts = useCallback(async () => {
    setLoadingList(true);
    try {
      const res = await api.chartSkillList(threadId);
      setSavedCharts(res.charts);
    } catch {
      setSavedCharts([]);
    } finally {
      setLoadingList(false);
    }
  }, [threadId]);

  useEffect(() => {
    if (open && view === 'history') {
      loadSavedCharts();
    }
  }, [open, view, loadSavedCharts]);

  const toggleDoc = (docId: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  const handleGenerate = async () => {
    if (!requestText.trim()) {
      toast.error('Please describe the chart you want to create');
      return;
    }

    setGenerating(true);
    setError(null);
    setResult(null);

    try {
      const response = await api.chartSkillGenerate(
        threadId,
        requestText.trim(),
        chartType === 'auto' ? undefined : chartType,
        selectedDocIds,
      );

      if (response.tracking_id) {
        setTrackingId(response.tracking_id);

        pollRef.current = setInterval(async () => {
          try {
            const status = await api.chartSkillStatus(response.tracking_id!);
            if (status.status && status.result) {
              setResult(status.result);
              setGenerating(false);
              setView('result');
              if (pollRef.current) clearInterval(pollRef.current);
            } else if (status.failed) {
              setError(status.error || 'Chart generation failed');
              setGenerating(false);
              if (pollRef.current) clearInterval(pollRef.current);
            }
          } catch (e) {
            console.error('Polling error:', e);
          }
        }, 2000);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start chart generation');
      setGenerating(false);
    }
  };

  const openDownload = (url?: string | null) => {
    if (!url) return;
    const token = getAuthToken();
    const full = `${API_URL}${url}${token ? `?token=${encodeURIComponent(token)}` : ''}`;
    window.open(full, '_blank');
  };

  const handleDelete = async (item: ChartSkillListItem) => {
    try {
      await api.chartSkillDelete(threadId, item.tracking_id);
      setSavedCharts((prev) => prev.filter((chart) => chart.tracking_id !== item.tracking_id));
      toast.success('Chart deleted');
    } catch {
      toast.error('Failed to delete chart');
    }
  };

  const openPreview = (item: {
    chart_id: string;
    title: string;
    download_json_url?: string;
    download_csv_url?: string | null;
  }) => {
    setPreviewChartId(item.chart_id);
    setPreviewTitle(item.title);
    setPreviewJsonUrl(item.download_json_url);
    setPreviewCsvUrl(item.download_csv_url);
  };

  const handleResetGenerate = () => {
    setRequestText('');
    setChartType('auto');
    setSelectedDocIds([]);
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
    loadSavedCharts();
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

  const descriptionText =
    view === 'history'
      ? 'View generated charts or create a new one.'
      : view === 'generate'
      ? 'Describe the visualization you want and choose a chart type.'
      : 'Your interactive chart is ready.';

  return (
    <>
      <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose(); }}>
        <DialogContent className="w-[96vw] max-w-4xl h-[85vh] flex flex-col overflow-hidden">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-sky-600" />
              Chart Builder
            </DialogTitle>
            <DialogDescription>{descriptionText}</DialogDescription>
          </DialogHeader>

          {view === 'history' && (
            <div className="flex-1 min-h-0 flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-muted-foreground">Generated Charts</h3>
                <Button size="sm" onClick={goToGenerate}>
                  <Plus className="w-4 h-4 mr-1" /> Create New
                </Button>
              </div>

              <div className="flex-1 min-h-0 overflow-y-auto pr-2">
                <div className="space-y-2 pb-1">
                  {loadingList && (
                    <div className="flex justify-center py-8">
                      <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                    </div>
                  )}

                  {!loadingList && savedCharts.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                      <FolderOpen className="w-12 h-12 text-muted-foreground/40 mb-3" />
                      <p className="text-sm text-muted-foreground">No charts yet.</p>
                      <p className="text-xs text-muted-foreground mt-1">Create your first chart to get started.</p>
                      <Button size="sm" className="mt-4" onClick={goToGenerate}>
                        <Plus className="w-4 h-4 mr-1" /> Create Your First
                      </Button>
                    </div>
                  )}

                  {!loadingList && savedCharts.map((item) => (
                    <Card key={item.tracking_id} className="p-4 hover:bg-accent/20 transition-colors">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0 pr-1">
                          <div className="flex items-center gap-2">
                            {item.chart_type === 'line' ? (
                              <LineChart className="w-4 h-4 text-sky-600 flex-none" />
                            ) : item.chart_type === 'pie' ? (
                              <PieChart className="w-4 h-4 text-orange-500 flex-none" />
                            ) : (
                              <BarChart3 className="w-4 h-4 text-sky-600 flex-none" />
                            )}
                            <span className="font-medium text-sm truncate">{item.title}</span>
                          </div>
                          <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{item.description}</p>
                          <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                            <span>{item.chart_type}</span>
                            <span>{item.row_count} points</span>
                            {item.created_at && <span>{formatDate(item.created_at)}</span>}
                          </div>
                        </div>
                        <div className="flex items-center gap-1 flex-none shrink-0">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => openPreview(item)}
                            title="Open"
                          >
                            <Sparkles className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => openDownload(item.download_json_url)}
                            title="Download JSON"
                          >
                            <Download className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-destructive hover:text-destructive"
                            onClick={() => handleDelete(item)}
                            title="Delete"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
            </div>
          )}

          {view === 'generate' && (
            <div className="flex-1 min-h-0 overflow-y-auto pr-2">
              <div className="space-y-4 py-2">
                <div>
                  <label className="text-sm font-medium mb-1.5 block">Quick Actions</label>
                  <div className="flex flex-wrap gap-2">
                    {QUICK_ACTIONS.map((action) => (
                      <Button
                        key={action.label}
                        variant="outline"
                        size="sm"
                        className="text-xs"
                        onClick={() => {
                          setRequestText(action.prompt);
                          setChartType(action.chartType);
                        }}
                        disabled={generating}
                      >
                        {action.label}
                      </Button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium mb-1.5 block">Chart Type</label>
                  <Select value={chartType} onValueChange={setChartType}>
                    <SelectTrigger>
                      <SelectValue placeholder="Auto" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="auto">Auto</SelectItem>
                      <SelectItem value="bar">Bar</SelectItem>
                      <SelectItem value="line">Line</SelectItem>
                      <SelectItem value="area">Area</SelectItem>
                      <SelectItem value="pie">Pie</SelectItem>
                      <SelectItem value="scatter">Scatter</SelectItem>
                      <SelectItem value="radar">Radar</SelectItem>
                      <SelectItem value="composed">Composed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label className="text-sm font-medium mb-1.5 block">Describe the chart</label>
                  <Textarea
                    placeholder="e.g., Create a line chart of monthly revenue by region with clear labels and trend comparison."
                    value={requestText}
                    onChange={(e) => setRequestText(e.target.value)}
                    rows={4}
                    disabled={generating}
                    className="resize-none"
                  />
                </div>

                {documents.length > 0 && (
                  <div>
                    <label className="text-sm font-medium mb-1.5 block">
                      Source Documents <span className="text-muted-foreground font-normal">(optional)</span>
                    </label>
                    <p className="text-xs text-muted-foreground mb-2">
                      If none are selected, uploaded files will be ignored for this chart.
                    </p>
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

                <Button className="w-full" onClick={handleGenerate} disabled={generating || !requestText.trim()}>
                  {generating ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Generating Chart...
                    </>
                  ) : (
                    <>
                      <BarChart3 className="w-4 h-4 mr-2" />
                      Generate Chart
                    </>
                  )}
                </Button>

                {error && (
                  <div className="bg-destructive/10 text-destructive text-sm rounded-md p-3">
                    {error}
                    <Button variant="ghost" size="sm" className="mt-2" onClick={handleResetGenerate}>
                      Try Again
                    </Button>
                  </div>
                )}

                <Button variant="outline" className="w-full" onClick={goToHistory} disabled={generating}>
                  <ArrowLeft className="w-4 h-4 mr-2" /> Back to Charts
                </Button>
              </div>
            </div>
          )}

          {view === 'result' && result && (
            <div className="space-y-4 py-2">
              <div className="bg-sky-50 dark:bg-sky-950/30 border border-sky-200 dark:border-sky-900 rounded-md p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-sky-600" />
                  <span className="font-medium">{result.title}</span>
                </div>
                <p className="text-sm text-muted-foreground">{result.description}</p>
                <div className="flex gap-4 text-sm">
                  <span><strong>{result.chart_type}</strong> type</span>
                  <span><strong>{result.row_count}</strong> points</span>
                </div>
                <div className="flex gap-2">
                  <Button className="flex-1" onClick={() => openPreview(result)}>
                    <Sparkles className="w-4 h-4 mr-2" />
                    Open Interactive Chart
                  </Button>
                  <Button variant="outline" onClick={() => openDownload(result.download_json_url)}>
                    <Download className="w-4 h-4 mr-2" /> JSON
                  </Button>
                </div>
              </div>

              <Button variant="outline" className="w-full" onClick={goToGenerate}>
                <Plus className="w-4 h-4 mr-2" /> Create Another
              </Button>
              <Button variant="outline" className="w-full" onClick={goToHistory}>
                <ArrowLeft className="w-4 h-4 mr-2" /> Back to Charts
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <ChartModal
        open={!!previewChartId}
        onOpenChange={(v) => {
          if (!v) {
            setPreviewChartId(null);
            setPreviewTitle('Interactive Chart');
            setPreviewJsonUrl(undefined);
            setPreviewCsvUrl(undefined);
          }
        }}
        threadId={threadId}
        chartId={previewChartId}
        fallbackTitle={previewTitle}
        downloadJsonUrl={previewJsonUrl}
        downloadCsvUrl={previewCsvUrl}
      />
    </>
  );
};

export default ChartSkillModal;
