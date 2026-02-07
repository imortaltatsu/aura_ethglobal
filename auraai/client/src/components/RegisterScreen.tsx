import { useState } from 'react';
import { Button, Card, Input } from '@pipecat-ai/voice-ui-kit';

const REGISTERED_KEY = 'auraai_registered_user';

export interface RegisteredUser {
  name: string;
  email: string;
}

function getStoredUser(): RegisteredUser | null {
  try {
    const raw = localStorage.getItem(REGISTERED_KEY);
    return raw ? (JSON.parse(raw) as RegisteredUser) : null;
  } catch {
    return null;
  }
}

export function isRegistered(): boolean {
  return getStoredUser() !== null;
}

export function getRegisteredUser(): RegisteredUser | null {
  return getStoredUser();
}

interface RegisterScreenProps {
  onRegistered: () => void;
  onSkip: () => void;
}

export function RegisterScreen({ onRegistered, onSkip }: RegisterScreenProps) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const trimmedName = name.trim();
    const trimmedEmail = email.trim();
    if (!trimmedName) {
      setError('Name is required');
      return;
    }
    try {
      localStorage.setItem(
        REGISTERED_KEY,
        JSON.stringify({ name: trimmedName, email: trimmedEmail })
      );
      onRegistered();
    } catch (err) {
      setError('Could not save registration');
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-4">
      <Card className="w-full max-w-md p-6">
        <h1 className="text-xl font-semibold mb-2">Register</h1>
        <p className="text-sm text-muted-foreground mb-4">
          Enter your name and email to continue. This is stored locally.
        </p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="text-sm font-medium mb-1 block">Name</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
              autoComplete="name"
            />
          </div>
          <div>
            <label className="text-sm font-medium mb-1 block">Email</label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
            />
          </div>
          {error && (
            <p className="text-sm text-red-500">{error}</p>
          )}
          <div className="flex gap-3">
            <Button type="submit" className="flex-1">
              Register
            </Button>
            <Button type="button" variant="outline" onClick={onSkip}>
              Skip
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
