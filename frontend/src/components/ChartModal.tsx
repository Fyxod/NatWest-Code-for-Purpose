import React from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Loader2, Download, Maximize2, Minimize2 } from 'lucide-react';
import { api, getAuthToken } from '@/lib/api';
import { API_URL } from '../../config';
import ChartRenderer from './ChartRenderer';

interface ChartModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  threadId: string;
  chartId: string | null;
  fallbackTitle?: string;
  downloadJsonUrl?: string;
  downloadCsvUrl?: string | null;
}

const ChartModal: React.FC<ChartModalProps> = ({
  open,
  onOpenChange,
  threadId,
  chartId,
  fallbackTitle,
  downloadJsonUrl,
  downloadCsvUrl,
}) => {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = React.useState(false);
  const [chartHeight, setChartHeight] = React.useState(430);
  const chartContainerRef = React.useRef<HTMLDivElement | null>(null);
  const syncFullscreenState = React.useCallback(() => {
    const container = chartContainerRef.current;
    const fullscreenElement = document.fullscreenElement;
    setIsFullscreen(Boolean(container && fullscreenElement && fullscreenElement === container));
  }, []);
  const [chart, setChart] = React.useState<{
    title: string;
    description: string;
    chart_type: string;
    x_key: string;
    y_keys: string[];
    data: Array<Record<string, string | number | null>>;
  } | null>(null);

  React.useEffect(() => {
    const load = async () => {
      if (!open || !threadId || !chartId) return;
      setLoading(true);
      setError(null);

      try {
        const response = await api.chartSkillItem(threadId, chartId);
        setChart(response.chart);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load chart');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [open, threadId, chartId]);

  React.useEffect(() => {
    document.addEventListener('fullscreenchange', syncFullscreenState);
    return () => {
      document.removeEventListener('fullscreenchange', syncFullscreenState);
    };
  }, [syncFullscreenState]);

  React.useEffect(() => {
    syncFullscreenState();
  }, [open, chart, syncFullscreenState]);

  React.useEffect(() => {
    if (!isFullscreen) {
      setChartHeight(430);
      return;
    }

    const updateHeight = () => {
      setChartHeight(Math.max(560, window.innerHeight - 180));
    };

    updateHeight();
    window.addEventListener('resize', updateHeight);
    return () => {
      window.removeEventListener('resize', updateHeight);
    };
  }, [isFullscreen]);

  React.useEffect(() => {
    if (open) {
      return;
    }

    setIsFullscreen(false);

    if (document.fullscreenElement === chartContainerRef.current) {
      void document.exitFullscreen().catch(() => {});
    }
  }, [open]);

  const openDownload = (url?: string | null) => {
    if (!url) return;
    const token = getAuthToken();
    const full = `${API_URL}${url}${token ? `?token=${encodeURIComponent(token)}` : ''}`;
    window.open(full, '_blank');
  };

  const toggleFullscreen = async () => {
    const chartContainer = chartContainerRef.current;
    if (!chartContainer) {
      return;
    }

    try {
      if (document.fullscreenElement === chartContainer) {
        await document.exitFullscreen();
        syncFullscreenState();
        return;
      }

      if (document.fullscreenElement) {
        await document.exitFullscreen();
      }

      await chartContainer.requestFullscreen();
      syncFullscreenState();
    } catch (e) {
      console.error('Unable to toggle fullscreen for chart.', e);
      syncFullscreenState();
    }
  };

  const chartDescription = (chart?.description || '').trim();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>{chart?.title || fallbackTitle || 'Interactive Chart'}</DialogTitle>
          <DialogDescription>Explore and download this chart artifact.</DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-auto pr-2">
          {loading && (
            <div className="h-72 flex items-center justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {!loading && error && (
            <div className="text-sm text-destructive bg-destructive/10 rounded-md p-3">{error}</div>
          )}

          {!loading && !error && chart && (
            <div
              ref={chartContainerRef}
              className={isFullscreen ? 'h-full w-full bg-background p-4 overflow-auto' : ''}
            >
              <div
                className={
                  isFullscreen
                    ? 'mb-3 flex items-center justify-end sticky top-0 z-10 bg-background/95 backdrop-blur py-1'
                    : 'mb-3 flex items-center justify-end'
                }
              >
                <Button variant="outline" size="sm" onClick={toggleFullscreen} className="gap-2">
                  {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
                  {isFullscreen ? 'Exit Full Screen' : 'Full Screen'}
                </Button>
              </div>

              <ChartRenderer
                chartType={chart.chart_type}
                data={chart.data}
                xKey={chart.x_key}
                yKeys={chart.y_keys}
                title={chart.title}
                height={chartHeight}
              />

              {chartDescription && (
                <div className="mt-4 rounded-md border bg-muted/30 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-foreground/80">
                    Chart Analysis
                  </p>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground whitespace-pre-line">
                    {chartDescription}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="pt-3 border-t flex items-center justify-end gap-2">
          <Button variant="outline" onClick={() => openDownload(downloadJsonUrl)} disabled={!downloadJsonUrl}>
            <Download className="w-4 h-4 mr-2" /> JSON
          </Button>
          <Button variant="outline" onClick={() => openDownload(downloadCsvUrl)} disabled={!downloadCsvUrl}>
            <Download className="w-4 h-4 mr-2" /> CSV
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ChartModal;
