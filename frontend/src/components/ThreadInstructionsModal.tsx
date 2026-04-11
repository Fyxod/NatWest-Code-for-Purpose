import { useCallback, useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Plus, Pencil, Trash2, Check, X, Loader2 } from 'lucide-react';
import { api, ThreadInstruction } from '@/lib/api';
import { toast } from 'sonner';

type Props = {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  threadId: string;
};

const ThreadInstructionsModal = ({ open, onOpenChange, threadId }: Props) => {
  const [instructions, setInstructions] = useState<ThreadInstruction[]>([]);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newText, setNewText] = useState('');
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');

  const getInstructionPreview = (text: string, maxWords = 8, maxChars = 80) => {
    const normalized = text.replace(/\s+/g, ' ').trim();
    if (!normalized) return '';

    const words = normalized.split(' ');
    if (words.length > maxWords) {
      return `${words.slice(0, maxWords).join(' ')}...`;
    }

    if (normalized.length > maxChars) {
      return `${normalized.slice(0, maxChars)}...`;
    }

    return normalized;
  };

  const fetchInstructions = useCallback(async () => {
    if (!threadId) return;
    setLoading(true);
    try {
      const result = await api.getInstructions(threadId);
      setInstructions(result);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load instructions');
    } finally {
      setLoading(false);
    }
  }, [threadId]);

  useEffect(() => {
    if (open) {
      fetchInstructions();
      setAdding(false);
      setNewText('');
      setEditingId(null);
    }
  }, [open, fetchInstructions]);

  const handleAdd = async () => {
    if (!newText.trim()) return;
    setSaving(true);
    try {
      const created = await api.addInstruction(threadId, newText.trim());
      setInstructions((prev) => [...prev, created]);
      setNewText('');
      setAdding(false);
      toast.success('Instruction added');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add instruction');
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (instruction: ThreadInstruction) => {
    const newSelected = !instruction.selected;
    // Optimistic update
    setInstructions((prev) =>
      prev.map((i) => (i.id === instruction.id ? { ...i, selected: newSelected } : i))
    );
    try {
      await api.updateInstruction(threadId, instruction.id, { selected: newSelected });
    } catch (err) {
      // Revert
      setInstructions((prev) =>
        prev.map((i) =>
          i.id === instruction.id ? { ...i, selected: instruction.selected } : i
        )
      );
      toast.error('Failed to update selection');
    }
  };

  const handleEdit = async (id: string) => {
    if (!editText.trim()) return;
    setSaving(true);
    try {
      const updated = await api.updateInstruction(threadId, id, { text: editText.trim() });
      setInstructions((prev) => prev.map((i) => (i.id === id ? updated : i)));
      setEditingId(null);
      setEditText('');
      toast.success('Instruction updated');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update instruction');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    // Optimistic removal
    const prev = instructions;
    setInstructions((list) => list.filter((i) => i.id !== id));
    try {
      await api.deleteInstruction(threadId, id);
      toast.success('Instruction deleted');
    } catch (err) {
      setInstructions(prev);
      toast.error('Failed to delete instruction');
    }
  };

  const startEdit = (instruction: ThreadInstruction) => {
    setEditingId(instruction.id);
    setEditText(instruction.text);
    setAdding(false);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditText('');
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl w-[90vw] max-h-[85vh] flex flex-col">
        <DialogHeader className="flex-shrink-0">
          <div className="flex items-center justify-between">
            <div>
              <DialogTitle>Thread Instructions</DialogTitle>
              <DialogDescription className="mt-1">
                These instructions are automatically included with every message in this
                thread.
              </DialogDescription>
            </div>
            {!adding && !editingId && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setAdding(true);
                  setEditingId(null);
                }}
              >
                <Plus className="w-4 h-4 mr-1" />
                Add instruction
              </Button>
            )}
          </div>
        </DialogHeader>

        {/* Add new instruction form */}
        {adding && (
          <div className="flex flex-col gap-2 border rounded-lg p-3 bg-muted/30 flex-shrink-0">
            <Textarea
              placeholder="Type your instruction here..."
              value={newText}
              onChange={(e) => setNewText(e.target.value)}
              className="min-h-[100px] max-h-[200px] resize-y"
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setAdding(false);
                  setNewText('');
                }}
                disabled={saving}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleAdd}
                disabled={saving || !newText.trim()}
              >
                {saving ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-1" />
                ) : (
                  <Check className="w-4 h-4 mr-1" />
                )}
                Save
              </Button>
            </div>
          </div>
        )}

        {/* Instructions list */}
        <ScrollArea className="flex-1 min-h-0">
          <div className="space-y-2 pr-2">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
              </div>
            ) : instructions.length === 0 && !adding ? (
              <p className="text-center text-muted-foreground py-8 text-sm">
                No instructions yet. Click "Add instruction" to create one.
              </p>
            ) : (
              instructions.map((instruction, index) => (
                <div
                  key={instruction.id}
                  className="border rounded-lg p-3 flex gap-3 items-start hover:bg-muted/30 transition-colors"
                >
                  {editingId === instruction.id ? (
                    <div className="flex-1 flex flex-col gap-2">
                      <Textarea
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                        className="min-h-[80px] max-h-[200px] resize-y"
                        autoFocus
                      />
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={cancelEdit}
                          disabled={saving}
                        >
                          <X className="w-4 h-4 mr-1" />
                          Cancel
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => handleEdit(instruction.id)}
                          disabled={saving || !editText.trim()}
                        >
                          {saving ? (
                            <Loader2 className="w-4 h-4 animate-spin mr-1" />
                          ) : (
                            <Check className="w-4 h-4 mr-1" />
                          )}
                          Save
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <span className="text-xs text-muted-foreground mt-0.5 w-5 text-right flex-shrink-0">
                        {index + 1}.
                      </span>
                      <Checkbox
                        checked={instruction.selected}
                        onCheckedChange={() => handleToggle(instruction)}
                        className="mt-0.5"
                      />
                      <div className="flex-1 w-0 min-w-0" title={instruction.text}>
                        <p className="text-sm truncate block">
                          {getInstructionPreview(instruction.text)}
                        </p>
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => startEdit(instruction)}
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive hover:text-destructive"
                          onClick={() => handleDelete(instruction.id)}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
};

export default ThreadInstructionsModal;
