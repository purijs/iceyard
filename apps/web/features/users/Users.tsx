"use client";

import { useMemo, useState } from "react";

import { Badge, Button, Panel } from "@/components/ui";
import { api } from "@/lib/api";
import type { RoleRead, UserDetailRead } from "@/types/api";

export function Users({
  token,
  users,
  roles,
  currentUserId,
  onRefresh
}: {
  token: string;
  users: UserDetailRead[];
  roles: RoleRead[];
  currentUserId: string | null;
  onRefresh: () => Promise<void>;
}) {
  const viewerRole = roles.find((role) => role.name === "viewer");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [roleIds, setRoleIds] = useState<string[]>(viewerRole ? [viewerRole.id] : []);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const sortedUsers = useMemo(
    () => [...users].sort((left, right) => left.username.localeCompare(right.username)),
    [users]
  );

  async function createUser() {
    setMessage(null);
    await api.createUser(token, { username, password, role_ids: roleIds });
    setUsername("");
    setPassword("");
    setRoleIds(viewerRole ? [viewerRole.id] : []);
    setMessage("User created.");
    await onRefresh();
  }

  async function toggleRole(user: UserDetailRead, roleId: string) {
    const existing = new Set(user.roles.map((role) => role.id));
    if (existing.has(roleId)) existing.delete(roleId);
    else existing.add(roleId);
    await api.updateUser(token, user.id, { role_ids: Array.from(existing) });
    await onRefresh();
  }

  async function deactivate(user: UserDetailRead) {
    await api.updateUser(token, user.id, { is_active: false });
    await onRefresh();
  }

  async function changePassword() {
    setMessage(null);
    await api.changePassword(token, {
      current_password: currentPassword,
      new_password: newPassword
    });
    setCurrentPassword("");
    setNewPassword("");
    setMessage("Password changed.");
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <Panel title="Users">
          <div className="divide-y divide-zinc-100">
            {sortedUsers.map((user) => (
              <div key={user.id} className="grid gap-3 py-3 lg:grid-cols-[220px_1fr_auto]">
                <div>
                  <div className="font-mono text-sm text-zinc-900">{user.username}</div>
                  <div className="mt-1 flex gap-1.5">
                    <Badge tone={user.is_active ? "healthy" : "neutral"}>
                      {user.is_active ? "active" : "inactive"}
                    </Badge>
                    {user.id === currentUserId ? <Badge>you</Badge> : null}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {roles.map((role) => {
                    const checked = user.roles.some((item) => item.id === role.id);
                    return (
                      <label key={role.id} className="flex items-center gap-1.5 text-xs text-zinc-600">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => void toggleRole(user, role.id)}
                        />
                        {role.name}
                      </label>
                    );
                  })}
                </div>
                <Button
                  variant="danger"
                  disabled={!user.is_active || user.id === currentUserId}
                  onClick={() => void deactivate(user)}
                >
                  Deactivate
                </Button>
              </div>
            ))}
          </div>
        </Panel>
        <div className="space-y-4">
          <Panel title="Add user">
            <div className="space-y-3">
              <label className="block">
                <span className="mb-1 block text-xs text-zinc-500">Username</span>
                <input
                  className="w-full rounded-md border border-zinc-300 px-3 py-2"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs text-zinc-500">Password</span>
                <input
                  className="w-full rounded-md border border-zinc-300 px-3 py-2"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              <div className="space-y-2">
                <div className="text-xs text-zinc-500">Roles</div>
                {roles.map((role) => (
                  <label key={role.id} className="flex items-center gap-2 text-sm text-zinc-700">
                    <input
                      type="checkbox"
                      checked={roleIds.includes(role.id)}
                      onChange={() =>
                        setRoleIds((current) =>
                          current.includes(role.id)
                            ? current.filter((item) => item !== role.id)
                            : [...current, role.id]
                        )
                      }
                    />
                    {role.name}
                  </label>
                ))}
              </div>
              <Button variant="primary" full disabled={!username || !password} onClick={createUser}>
                Add user
              </Button>
            </div>
          </Panel>
          <Panel title="Change password">
            <div className="space-y-3">
              <input
                className="w-full rounded-md border border-zinc-300 px-3 py-2"
                type="password"
                placeholder="Current password"
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
              />
              <input
                className="w-full rounded-md border border-zinc-300 px-3 py-2"
                type="password"
                placeholder="New password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
              />
              <Button full disabled={!currentPassword || !newPassword} onClick={changePassword}>
                Update password
              </Button>
            </div>
          </Panel>
          {message ? <div className="rounded-md border border-zinc-200 bg-white p-3 text-sm text-zinc-700">{message}</div> : null}
        </div>
      </div>
    </div>
  );
}
