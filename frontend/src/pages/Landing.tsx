import { useNavigate } from 'react-router-dom';
import { PROJECT_NAME } from '../../config';
import { Button } from '@/components/ui/button';
import { Brain, FileText, Sparkles, Zap, Moon, Sun } from 'lucide-react';
import { useTheme } from '@/lib/theme-context';
import { useAuth } from '@/lib/auth-context';

const Landing = () => {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const { isAuthenticated } = useAuth();

  const handleGetStarted = () => {
    if (isAuthenticated) {
      navigate('/dashboard');
    } else {
      navigate('/login');
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-2">
            {/* <Brain className="w-8 h-8 text-primary" /> */}
            <div>
              <h1 className="text-xl font-bold">{PROJECT_NAME}</h1>
              <p className="text-xs text-muted-foreground">GPU Version</p>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={toggleTheme}>
            {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
          </Button>
        </div>
      </header>

      {/* Hero Section */}
      <section className="container mx-auto px-4 py-20 md:py-32">
        <div className="max-w-4xl mx-auto text-center space-y-8">
          <div className="inline-block">
            <div className="bg-gradient-primary bg-clip-text text-transparent">
              <h2 className="text-5xl md:text-7xl font-bold mb-4 animate-fade-in">
                Transform Your Documents
              </h2>
            </div>
          </div>
          <p className="text-xl md:text-2xl text-muted-foreground animate-fade-in">
            Chat with your documents using AI-powered intelligence. 
            Get instant answers from spreadsheets, structured text files, and images.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center pt-8 animate-fade-in">
            <Button 
              size="lg" 
              onClick={handleGetStarted}
              className="bg-gradient-primary text-lg px-8 py-6 shadow-glow hover:shadow-lg transition-all"
            >
              <Sparkles className="mr-2 w-5 h-5" />
              Start Chatting with Your Documents
            </Button>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="container mx-auto px-4 py-20 bg-gradient-hero rounded-3xl">
        <div className="max-w-6xl mx-auto">
          <h3 className="text-3xl md:text-4xl font-bold text-center mb-16">
            Powerful Features
          </h3>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-card rounded-2xl p-8 shadow-md hover:shadow-lg transition-all">
              <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center mb-4">
                <FileText className="w-6 h-6 text-primary" />
              </div>
              <h4 className="text-xl font-semibold mb-3">Multi-Format Support</h4>
              <p className="text-muted-foreground">
                Upload Excel sheets, CSV files, and images.
                We process supported formats consistently and quickly.
              </p>
            </div>
            
            <div className="bg-card rounded-2xl p-8 shadow-md hover:shadow-lg transition-all">
              <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center mb-4">
                <Brain className="w-6 h-6 text-primary" />
              </div>
              <h4 className="text-xl font-semibold mb-3">AI-Powered Answers</h4>
              <p className="text-muted-foreground">
                Get intelligent responses based on your documents. 
                Choose between internal knowledge or web-enhanced mode.
              </p>
            </div>
            
            <div className="bg-card rounded-2xl p-8 shadow-md hover:shadow-lg transition-all">
              <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center mb-4">
                <Zap className="w-6 h-6 text-primary" />
              </div>
              <h4 className="text-xl font-semibold mb-3">Organized Threads</h4>
              <p className="text-muted-foreground">
                Keep your conversations organized in threads. 
                Easy to search, sort, and manage your knowledge base.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="container mx-auto px-4 py-8 mt-20 border-t">
        <div className="text-center text-muted-foreground">
          <p>{`© 2025 ${PROJECT_NAME}. All rights reserved.`}</p>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
