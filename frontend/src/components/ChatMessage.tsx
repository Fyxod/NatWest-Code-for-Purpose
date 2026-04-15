import { Chat } from '@/lib/api';
import { User, Bot, Trash2, BarChart3, Volume2, Square } from 'lucide-react';
import { cn } from '@/lib/utils';
import React from 'react';
import SafeMarkdownRenderer from './SafeMarkdownRenderer';
import { Button } from '@/components/ui/button';
import ChartModal from './ChartModal';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { FileText, ExternalLink } from 'lucide-react';


interface ChatMessageProps {
  chat: Chat;
  onDelete?: () => void;
  threadId?: string;
}

export const ChatMessage = ({ chat, onDelete, threadId }: ChatMessageProps) => {
  const isUser = chat.type === 'user';
  const [activeChartId, setActiveChartId] = React.useState<string | null>(null);
  const [activeChartTitle, setActiveChartTitle] = React.useState<string>('Interactive Chart');
  const [activeJsonUrl, setActiveJsonUrl] = React.useState<string | undefined>(undefined);
  const [activeCsvUrl, setActiveCsvUrl] = React.useState<string | null | undefined>(undefined);
  const [isSpeaking, setIsSpeaking] = React.useState(false);
  const utteranceRef = React.useRef<SpeechSynthesisUtterance | null>(null);

  const chartsUsed = chat.sources?.charts_used ?? [];
  const supportsSpeech = typeof window !== 'undefined' && 'speechSynthesis' in window;

  const speechText = React.useMemo(() => {
    // Convert markdown-heavy content into cleaner plain text for TTS.
    return String(chat.content ?? '')
      .replace(/```[\s\S]*?```/g, ' code block omitted ')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1')
      .replace(/[*_>#-]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }, [chat.content]);

  const stopSpeaking = React.useCallback(() => {
    if (!supportsSpeech) {
      return;
    }
    window.speechSynthesis.cancel();
    utteranceRef.current = null;
    setIsSpeaking(false);
  }, [supportsSpeech]);

  const handleToggleSpeak = React.useCallback(() => {
    if (!supportsSpeech || !speechText) {
      return;
    }

    if (isSpeaking) {
      stopSpeaking();
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(speechText);
    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => {
      setIsSpeaking(false);
      utteranceRef.current = null;
    };
    utterance.onerror = () => {
      setIsSpeaking(false);
      utteranceRef.current = null;
    };

    utteranceRef.current = utterance;
    window.speechSynthesis.speak(utterance);
  }, [isSpeaking, speechText, stopSpeaking, supportsSpeech]);

  React.useEffect(() => {
    return () => {
      if (utteranceRef.current && supportsSpeech) {
        window.speechSynthesis.cancel();
      }
    };
  }, [supportsSpeech]);

  // Markdown is enabled by default for bot messages. Removed per-message toggle.
  const displayTime = React.useMemo(() => {
    // User-requested simple logic:
    // 1) Try new Date(chat.timestamp + 'Z') and format to IST
    // 2) If that yields an invalid date, use current time
    try {
      const raw = chat.timestamp ?? '';
      const parsed = new Date(String(raw) + 'Z');
      if (isNaN(parsed.getTime())) {
        return new Date().toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
          hour12: true,
          timeZone: 'Asia/Kolkata'
        });
      }

      return parsed.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
        timeZone: 'Asia/Kolkata'
      });
    } catch (e) {
      return new Date().toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
        timeZone: 'Asia/Kolkata'
      });
    }
  }, [chat.timestamp]);

  return (
    <div className={cn('group flex gap-3 p-4', isUser ? 'justify-end' : 'justify-start')}>
      {!isUser && (
        <div className="flex flex-col items-center gap-1 flex-shrink-0">
          <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
            <Bot className="w-5 h-5 text-primary" />
          </div>
          <Button
            variant="ghost"
            size="icon"
            type="button"
            aria-label={isSpeaking ? 'Stop reading message' : 'Read message out loud'}
            onClick={handleToggleSpeak}
            disabled={!supportsSpeech || !speechText}
            className={cn(
              'h-6 w-6 text-muted-foreground hover:text-primary transition-opacity',
              'opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto',
              isSpeaking && 'opacity-100 pointer-events-auto text-primary'
            )}
          >
            {isSpeaking ? <Square className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
          </Button>
        </div>
      )}

      {/* Markdown toggle removed; messages use Markdown by default */}

      <div
        className={cn(
          'relative max-w-[80%] rounded-2xl px-4 py-3',
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'bg-muted'
        )}
      >
        {onDelete && (
          <Button
            variant="ghost"
            size="icon"
            className="absolute -top-3 -right-3 h-7 w-7 text-muted-foreground hover:text-destructive"
            aria-label="Delete message"
            onClick={onDelete}
            type="button"
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        )}
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap break-words">{chat.content}</p>
        ) : (
          <div className="text-sm">
            <SafeMarkdownRenderer content={chat.content} />
          </div>
        )}

        {!isUser && chartsUsed.length > 0 && (
          <div className="mt-3 border-t pt-3 space-y-2">
            <p className="text-xs text-muted-foreground">Generated Charts</p>
            <div className="flex flex-wrap gap-2">
              {chartsUsed.map((chart) => (
                <Button
                  key={chart.chart_id}
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setActiveChartId(chart.chart_id);
                    setActiveChartTitle(chart.title || 'Interactive Chart');
                    setActiveJsonUrl(chart.download_json_url);
                    setActiveCsvUrl(chart.download_csv_url);
                  }}
                  disabled={!threadId}
                  className="text-xs"
                >
                  <BarChart3 className="w-3.5 h-3.5 mr-1" />
                  {chart.title || 'Open Chart'}
                </Button>
              ))}
            </div>
          </div>
        )}
        <p className="text-xs opacity-70 mt-2">{displayTime}</p>

        {/* Sources Accordion */}
        {!isUser && chat.sources && (
          (chat.sources.documents_used?.length || 0) > 0 ||
          (chat.sources.web_used?.length || 0) > 0 ||
          (chat.sources.charts_used?.length || 0) > 0
        ) && (
          <div className="mt-3 border-t pt-2">
            <Accordion type="single" collapsible className="w-full">
              <AccordionItem value="sources" className="border-b-0">
                <AccordionTrigger className="py-1 text-xs text-muted-foreground hover:no-underline hover:text-primary">
                  <span className="flex items-center gap-1">
                    <FileText className="w-3 h-3" />
                    Sources ({(chat.sources.documents_used?.length || 0) + (chat.sources.web_used?.length || 0) + (chat.sources.charts_used?.length || 0)})
                  </span>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="space-y-2 pt-1 text-xs text-muted-foreground">
                    {chat.sources.documents_used?.map((doc, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <div className="w-1 h-1 rounded-full bg-primary/40" />
                        <span className="font-medium text-foreground/80">{doc.title}</span>
                        <span className="opacity-70">(Page {doc.page_no})</span>
                      </div>
                    ))}
                    {chat.sources.web_used?.map((site, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <ExternalLink className="w-3 h-3" />
                        <a href={site.url} target="_blank" rel="noopener noreferrer" className="hover:underline text-blue-500">
                          {site.title || site.url}
                        </a>
                      </div>
                    ))}
                    {chat.sources.charts_used?.map((chart, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <BarChart3 className="w-3 h-3" />
                        <span>{chart.title || 'Generated chart'}</span>
                      </div>
                    ))}
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </div>
        )}

      </div>

      {!isUser && threadId && (
        <ChartModal
          open={!!activeChartId}
          onOpenChange={(v) => {
            if (!v) {
              setActiveChartId(null);
              setActiveChartTitle('Interactive Chart');
              setActiveJsonUrl(undefined);
              setActiveCsvUrl(undefined);
            }
          }}
          threadId={threadId}
          chartId={activeChartId}
          fallbackTitle={activeChartTitle}
          downloadJsonUrl={activeJsonUrl}
          downloadCsvUrl={activeCsvUrl}
        />
      )}

      {isUser && (
        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
          <User className="w-5 h-5 text-primary" />
        </div>
      )}
    </div>
  );
};
