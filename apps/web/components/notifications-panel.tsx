"use client";

import { useCallback, useEffect, useState } from "react";
import { type NotificationOut, type NotificationSettingOut, api } from "@/lib/api";

export function NotificationsPanel({ canAdmin }: { canAdmin: boolean }) {
  const [notifications, setNotifications] = useState<NotificationOut[]>([]);
  const [settings, setSettings] = useState<NotificationSettingOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Settings form
  const [channels, setChannels] = useState("");
  const [emailTo, setEmailTo] = useState("");
  const [slackUrl, setSlackUrl] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [notifs, sets] = await Promise.all([
        api.notifications(),
        canAdmin ? api.notificationSettings() : Promise.resolve(null),
      ]);
      setNotifications(notifs);
      setSettings(sets);
      setChannels(sets?.channels ?? "");
      setEmailTo(sets?.email_to || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load notifications");
    } finally {
      setLoading(false);
    }
  }, [canAdmin]);

  useEffect(() => {
    void load();
  }, [load]);

  async function markRead(id: string) {
    try {
      const updated = await api.markNotificationRead(id);
      setNotifications((prev) => prev.map((n) => (n.id === id ? updated : n)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to mark notification read");
    }
  }

  async function saveSettings(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await api.updateNotificationSettings({
        channels,
        email_to: emailTo || undefined,
        slack_webhook_url: slackUrl || undefined,
      });
      setSettings(updated);
      setSlackUrl(""); // Clear the webhook URL input after saving
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="text-sm text-neutral-500">Loading notifications...</p>;

  return (
    <div className="grid gap-8 md:grid-cols-3">
      <div className="md:col-span-2">
        <h2 className="mb-4 text-lg font-medium">Notifications</h2>
        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}
        {notifications.length === 0 ? (
          <p className="text-sm text-neutral-500">No notifications yet.</p>
        ) : (
          <ul className="space-y-3">
            {notifications.map((n) => (
              <li
                key={n.id}
                className={`rounded-lg border p-4 ${
                  n.level === "warning"
                    ? "border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/20"
                    : "border-neutral-200 dark:border-neutral-800"
                } ${n.read_at ? "opacity-60" : ""}`}
              >
                <div className="mb-1 flex items-center justify-between gap-2">
                  <h3 className="font-medium">{n.title}</h3>
                  <span className="shrink-0 text-xs text-neutral-400">
                    {new Date(n.created_at).toLocaleString()}
                  </span>
                </div>
                <p className="text-sm text-neutral-600 dark:text-neutral-300">{n.body}</p>
                {!n.read_at && (
                  <button
                    type="button"
                    onClick={() => markRead(n.id)}
                    className="mt-2 text-xs font-medium text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-200"
                  >
                    Mark as read
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {canAdmin && settings && (
        <div>
          <h2 className="mb-4 text-lg font-medium">Settings</h2>
          <form
            onSubmit={saveSettings}
            className="rounded-xl border border-neutral-200 p-4 dark:border-neutral-800"
          >
            <div className="mb-4">
              <label className="mb-1 block text-sm font-medium">Channels</label>
              <input
                value={channels}
                onChange={(e) => setChannels(e.target.value)}
                placeholder="email,slack"
                className="w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
              />
              <p className="mt-1 text-xs text-neutral-500">Comma-separated list (e.g. email,slack)</p>
            </div>

            <div className="mb-4">
              <label className="mb-1 block text-sm font-medium">Email To</label>
              <input
                type="email"
                value={emailTo}
                onChange={(e) => setEmailTo(e.target.value)}
                placeholder="compliance@example.com"
                className="w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
              />
            </div>

            <div className="mb-4">
              <label className="mb-1 block text-sm font-medium">Slack Webhook URL</label>
              <input
                type="password"
                value={slackUrl}
                onChange={(e) => setSlackUrl(e.target.value)}
                placeholder={settings.slack_webhook_configured ? "••••••••" : "https://hooks.slack.com/..."}
                className="w-full rounded-lg border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none dark:border-neutral-700"
              />
            </div>

            <button
              type="submit"
              disabled={saving}
              className="w-full rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-neutral-900"
            >
              {saving ? "Saving..." : "Save Settings"}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
