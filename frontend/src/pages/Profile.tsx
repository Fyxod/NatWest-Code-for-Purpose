import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/lib/auth-context';
import { User, Mail, MessageSquare, FileText } from 'lucide-react';
import { useEffect, useState } from 'react';

const Profile = () => {
  const { user, refreshUser } = useAuth();
  const [isRefreshing, setIsRefreshing] = useState(false);

  useEffect(() => {
    // Fetch fresh user data only once when component mounts
    const fetchData = async () => {
      setIsRefreshing(true);
      await refreshUser();
      setIsRefreshing(false);
    };
    fetchData();
  }, [refreshUser]);

  if (isRefreshing && !user) {
    return (
      <div className="h-full flex items-center justify-center">
        <p className="text-muted-foreground">Loading profile...</p>
      </div>
    );
  }

  if (!user) return null;

  const totalThreads = Object.keys(user.threads || {}).length;
  const totalDocuments = Object.values(user.threads || {}).reduce(
    (acc, thread) => acc + (thread.documents?.length || 0),
    0
  );
  const totalChats = Object.values(user.threads || {}).reduce(
    (acc, thread) => acc + (thread.chats?.length || 0),
    0
  );

  return (
    <div className="h-full overflow-auto p-6 bg-gradient-hero">
      <div className="max-w-4xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold">Profile</h1>

        <Card>
          <CardHeader>
            <CardTitle>User Information</CardTitle>
            <CardDescription>Your account details</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <User className="w-4 h-4" />
                Name
              </Label>
              <p className="text-lg">{user.name}</p>
            </div>
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Mail className="w-4 h-4" />
                Email
              </Label>
              <p className="text-lg">{user.email}</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Usage Statistics</CardTitle>
            <CardDescription>Your activity overview</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-3 gap-4">
              <div className="p-4 bg-muted rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <MessageSquare className="w-5 h-5 text-primary" />
                  <p className="text-sm text-muted-foreground">Threads</p>
                </div>
                <p className="text-3xl font-bold">{totalThreads}</p>
              </div>
              
              <div className="p-4 bg-muted rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <FileText className="w-5 h-5 text-primary" />
                  <p className="text-sm text-muted-foreground">Documents</p>
                </div>
                <p className="text-3xl font-bold">{totalDocuments}</p>
              </div>
              
              <div className="p-4 bg-muted rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <MessageSquare className="w-5 h-5 text-primary" />
                  <p className="text-sm text-muted-foreground">Messages</p>
                </div>
                <p className="text-3xl font-bold">{totalChats}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Profile;
