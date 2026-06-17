"use client";

import { FormEvent, useState } from "react";

import { Button, Panel } from "@/components/ui";
import { api } from "@/lib/api";

export function AuthGate({ onToken }: { onToken: (token: string) => void }) {
  const [mode, setMode] = useState<"login" | "bootstrap">("bootstrap");
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("change-this-password");
  const [displayName, setDisplayName] = useState("Platform Admin");
  const [workspaceName, setWorkspaceName] = useState("Iceyard");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const result =
        mode === "bootstrap"
          ? await api.bootstrap({ workspace_name: workspaceName, email, password, display_name: displayName })
          : await api.login({ email, password });
      const token = "token" in result ? result.token.access_token : result.access_token;
      localStorage.setItem("iceyard_token", token);
      onToken(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 p-6">
      <Panel title={mode === "bootstrap" ? "Bootstrap workspace" : "Login"}>
        <form onSubmit={submit} className="w-full max-w-md space-y-3">
          {mode === "bootstrap" ? (
            <>
              <label className="block">
                <span className="mb-1 block text-xs text-zinc-500">Workspace</span>
                <input className="w-full rounded-md border border-zinc-300 px-3 py-2" value={workspaceName} onChange={(event) => setWorkspaceName(event.target.value)} />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs text-zinc-500">Display name</span>
                <input className="w-full rounded-md border border-zinc-300 px-3 py-2" value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
              </label>
            </>
          ) : null}
          <label className="block">
            <span className="mb-1 block text-xs text-zinc-500">Email</span>
            <input className="w-full rounded-md border border-zinc-300 px-3 py-2" value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-zinc-500">Password</span>
            <input className="w-full rounded-md border border-zinc-300 px-3 py-2" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          {error ? <div className="rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div> : null}
          <div className="flex items-center justify-between gap-3">
            <Button type="submit" variant="primary">
              Continue
            </Button>
            <button type="button" className="text-sm text-zinc-500 hover:text-zinc-900" onClick={() => setMode(mode === "bootstrap" ? "login" : "bootstrap")}>
              {mode === "bootstrap" ? "Use login" : "Use bootstrap"}
            </button>
          </div>
        </form>
      </Panel>
    </div>
  );
}
