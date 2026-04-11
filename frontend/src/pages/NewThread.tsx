import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Upload, X, Edit2, Check } from 'lucide-react';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { toast } from 'sonner';

const NewThread = () => {
  const [threadName, setThreadName] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [fileNames, setFileNames] = useState<Record<number, string>>({});
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const { refreshUser, user, setUser } = useAuth();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files);
      setFiles(prev => [...prev, ...newFiles]);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const newFiles = Array.from(e.dataTransfer.files);
      setFiles(prev => [...prev, ...newFiles]);
    }
  };

  const handleUploadAreaClick = () => {
    fileInputRef.current?.click();
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
    setFileNames(prev => {
      const updated = { ...prev };
      delete updated[index];
      return updated;
    });
  };

  const updateFileName = (index: number, newName: string) => {
    setFileNames(prev => ({ ...prev, [index]: newName }));
  };

  const handleSubmit = async () => {
    if (!threadName.trim()) {
      toast.error('Please enter a thread name');
      return;
    }

    setLoading(true);
    try {
      // Create files with updated names if edited
      const processedFiles = files.map((file, index) => {
        if (fileNames[index]) {
          return new File([file], fileNames[index], { type: file.type });
        }
        return file;
      });

      const response = await api.uploadFiles({
        thread_name: threadName,
        files: processedFiles,
      });

      toast.success('Thread created successfully!');
      // Ensure sidebar reflects the new thread before navigating
      try {
        await refreshUser();
      } catch (_) {
        // Optimistic fallback: add the new thread locally if refresh fails
        const now = new Date().toISOString();
        if (user) {
          setUser({
            ...user,
            threads: {
              ...(user.threads || {}),
              [response.thread_id]: {
                thread_name: threadName,
                createdAt: now,
                updatedAt: now,
                documents: [],
                chats: [],
              },
            },
          });
        }
      }
      navigate(`/dashboard/threads/${response.thread_id}`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to create thread';
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex items-center justify-center p-6 bg-gradient-hero">
      <Card className="w-full max-w-2xl shadow-lg">
        <CardHeader>
          <CardTitle className="text-2xl">Create New Thread</CardTitle>
          <CardDescription>
            Start a new conversation by giving it a name and optionally uploading documents
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="threadName">Thread Name *</Label>
            <Input
              id="threadName"
              placeholder="e.g., Research Papers, Meeting Notes"
              value={threadName}
              onChange={(e) => setThreadName(e.target.value)}
            />
          </div>

          <div className="space-y-3">
            <Label>Upload Files (Optional)</Label>
            <div 
              className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                isDragging 
                  ? 'border-primary bg-primary/5' 
                  : 'border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50'
              }`}
              onClick={handleUploadAreaClick}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <Upload className="w-12 h-12 mx-auto mb-3 text-muted-foreground" />
              <p className="text-sm text-muted-foreground mb-3">
                Click to upload or drag and drop files
              </p>
              <Input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleFileChange}
                className="hidden"
                accept=".xls,.xlsx,.csv,.jpg,.jpeg,.png,.tiff,.bmp,.gif"
              />
            </div>

            {files.length > 0 && (
              <div className="space-y-2 mt-4 max-h-60 overflow-y-auto">
                <p className="text-sm font-medium">Selected Files:</p>
                {files.map((file, index) => (
                  <div key={index} className="flex items-center gap-2 p-3 bg-muted rounded-lg">
                    {editingIndex === index ? (
                      <Input
                        value={fileNames[index] || file.name}
                        onChange={(e) => updateFileName(index, e.target.value)}
                        className="flex-1"
                        autoFocus
                      />
                    ) : (
                      <span className="flex-1 text-sm truncate" title={fileNames[index] || file.name}>
                        {fileNames[index] || file.name}
                      </span>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setEditingIndex(editingIndex === index ? null : index)}
                    >
                      {editingIndex === index ? (
                        <Check className="w-4 h-4" />
                      ) : (
                        <Edit2 className="w-4 h-4" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => removeFile(index)}
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <Button 
            onClick={handleSubmit} 
            disabled={loading || !threadName.trim()}
            className="w-full bg-gradient-primary"
          >
            {loading ? 'Creating...' : 'Create Thread'}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};

export default NewThread;
