import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ExternalLink, FileText, ChevronDown, ChevronUp } from 'lucide-react';

interface SourcesDisplayProps {
  docsUsed: Array<{
    title: string;
    document_id: string;
    page_no: number;
  }>;
  webUsed: Array<{
    title: string;
    url: string;
    favicon: string | null;
  }>;
}

export const SourcesDisplay = ({ docsUsed, webUsed }: SourcesDisplayProps) => {
  const [isOpen, setIsOpen] = useState(false);

  // Defensive: ensure arrays
  const safeDocs = Array.isArray(docsUsed) ? docsUsed : [];
  const safeWeb = Array.isArray(webUsed) ? webUsed : [];

  // Optional: dedupe identical doc entries (same doc id and page)
  const dedupedDocs = (() => {
    const seen = new Set<string>();
    const out: typeof safeDocs = [];
    for (const d of safeDocs) {
      const key = `${d.document_id}:${d.page_no}`;
      if (!seen.has(key)) {
        seen.add(key);
        out.push(d);
      }
    }
    return out;
  })();

  // Group documents by document_id
  const groupedDocs = dedupedDocs.reduce((acc, doc) => {
    if (!acc[doc.document_id]) {
      acc[doc.document_id] = {
        title: doc.title,
        pages: [],
      };
    }
    acc[doc.document_id].pages.push(doc.page_no);
    return acc;
  }, {} as Record<string, { title: string; pages: number[] }>);

  // Count unique sources: number of unique documents + number of web sources
  const uniqueSourceCount = Object.keys(groupedDocs).length + safeWeb.length;

  if (safeDocs.length === 0 && safeWeb.length === 0) return null;

  return (
    <div className="mt-2">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        className="text-xs"
      >
        {isOpen ? <ChevronUp className="w-3 h-3 mr-1" /> : <ChevronDown className="w-3 h-3 mr-1" />}
        View Sources ({uniqueSourceCount})
      </Button>

      {isOpen && (
        <Card className="mt-2 p-3 space-y-3">
          {Object.entries(groupedDocs).length > 0 && (
            <div>
              <h4 className="text-xs font-semibold mb-2 flex items-center gap-1">
                <FileText className="w-3 h-3" />
                Documents
              </h4>
              <div className="space-y-1">
                {Object.entries(groupedDocs).map(([docId, doc]) => (
                  <div key={docId} className="text-xs min-w-0">
                    <span className="font-medium truncate block" title={doc.title}>{doc.title}</span>
                    <span className="text-muted-foreground">
                      (Pages: {Array.from(new Set(doc.pages)).sort((a, b) => a - b).join(', ')})
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {safeWeb.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold mb-2 flex items-center gap-1">
                <ExternalLink className="w-3 h-3" />
                Web Sources
              </h4>
              <div className="space-y-1">
                {safeWeb.map((web, index) => (
                  <a
                    key={index}
                    href={web.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-xs hover:underline text-primary min-w-0"
                    title={web.title}
                  >
                    {web.favicon && (
                      <img src={web.favicon} alt="" className="w-4 h-4 flex-shrink-0" />
                    )}
                    <span className="truncate">{web.title}</span>
                  </a>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
};
