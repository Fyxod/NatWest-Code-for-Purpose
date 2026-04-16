import React from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Loader2, Download } from 'lucide-react';
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

  const openDownload = (url?: string | null) => {
    if (!url) return;
    const token = getAuthToken();
    const full = `${API_URL}${url}${token ? `?token=${encodeURIComponent(token)}` : ''}`;
    window.open(full, '_blank');
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
            <>
              <ChartRenderer
                chartType={chart.chart_type}
                data={chart.data}
                xKey={chart.x_key}
                yKeys={chart.y_keys}
                title={chart.title}
                height={430}
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
            </>
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
