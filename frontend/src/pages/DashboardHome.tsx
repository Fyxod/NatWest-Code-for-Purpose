import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Plus, MessageSquare } from 'lucide-react';

const DashboardHome = () => {
  const navigate = useNavigate();

  return (
    <div className="h-full flex items-center justify-center p-6 bg-gradient-hero">
      <div className="text-center space-y-6 max-w-lg">
        <div className="w-20 h-20 mx-auto bg-primary/10 rounded-full flex items-center justify-center">
          <MessageSquare className="w-10 h-10 text-primary" />
        </div>
        <h2 className="text-3xl font-bold">Start a New Conversation</h2>
        <p className="text-muted-foreground text-lg">
          Create a new thread to begin chatting with your documents or explore your existing conversations from the sidebar.
        </p>
        <Button 
          size="lg" 
          onClick={() => navigate('/dashboard/new')}
          className="bg-gradient-primary shadow-glow"
        >
          <Plus className="w-5 h-5 mr-2" />
          New Thread
        </Button>
      </div>
    </div>
  );
};

export default DashboardHome;
