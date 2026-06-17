"use client";

import { FormEvent, useState } from "react";

import { Button, Panel } from "@/components/ui";
import { api } from "@/lib/api";

export function AuthGate({ onToken }: { onToken: (token: string) => void }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const result = await api.login({ username, password });
      const token = result.access_token;
      localStorage.setItem("iceyard_token", token);
      onToken(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 p-6">
      <Panel title="Login">
        <form onSubmit={submit} className="w-full max-w-md space-y-3">
          <label className="block">
            <span className="mb-1 block text-xs text-zinc-500">Username</span>
            <input className="w-full rounded-md border border-zinc-300 px-3 py-2" value={username} onChange={(event) => setUsername(event.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-zinc-500">Password</span>
            <input className="w-full rounded-md border border-zinc-300 px-3 py-2" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          {error ? <div className="rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div> : null}
          <div className="flex items-center justify-between gap-3">
            <Button type="submit" variant="primary">
              Login
            </Button>
          </div>
        </form>
      </Panel>
    </div>
  );
}
