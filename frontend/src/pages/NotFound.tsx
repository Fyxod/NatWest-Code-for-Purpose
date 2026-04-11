import { useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { FileSearch, Home, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const NotFound = () => {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    console.error("404 Error: User attempted to access non-existent route:", location.pathname);
    const prevTitle = document.title;
    document.title = "404 • Page not found";
    return () => {
      document.title = prevTitle;
    };
  }, [location.pathname]);

  const state = (location.state as any) || {};
  const backendMessage = state?.message as string | undefined;
  const backendPath = state?.path as string | undefined;
  const backendCode = state?.code as number | undefined;

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-background">
      {/* Subtle background decoration */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(45rem_30rem_at_50%_-10%,hsl(var(--primary)/0.08),transparent)]"
      />

      <Card className="relative mx-4 w-full max-w-xl border-muted/50 shadow-lg">
        <CardContent className="p-8 text-center">
          <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary">
            <FileSearch className="h-7 w-7" aria-hidden />
          </div>

          <h1 className="mb-2 text-6xl font-extrabold leading-none tracking-tight">
            <span className="bg-gradient-to-r from-primary to-fuchsia-500 bg-clip-text text-transparent">404</span>
          </h1>
          <p className="mb-1 text-xl font-medium">Page not found</p>
          <div className="mb-6 space-y-2 text-sm text-muted-foreground">
            <p>
              We couldn't find
              <span className="mx-1 rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{backendPath || location.pathname}</span>
              .
            </p>
            {backendMessage && (
              <p className="text-foreground"><span className="font-semibold">Server:</span> {backendMessage}{backendCode ? ` (code ${backendCode})` : ''}</p>
            )}
          </div>

          <div className="flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button asChild>
              <Link to="/">
                <Home className="mr-2 h-4 w-4" /> Go Home
              </Link>
            </Button>
            <Button variant="outline" onClick={() => navigate(-1)}>
              <ArrowLeft className="mr-2 h-4 w-4" /> Go Back
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default NotFound;
