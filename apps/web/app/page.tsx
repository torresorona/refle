"use client";

import { useEffect, useState } from "react";

import { AuthCard } from "@/components/auth-card";
import { Dashboard } from "@/components/dashboard";
import { api } from "@/lib/api";

export default function Home() {
  // null = not yet determined (we probe the session cookie via /auth/me)
  const [authed, setAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    api
      .me()
      .then(() => setAuthed(true))
      .catch(() => setAuthed(false));
  }, []);

  if (authed === null) return null;

  return authed ? (
    <Dashboard onSignOut={() => setAuthed(false)} />
  ) : (
    <AuthCard onAuthed={() => setAuthed(true)} />
  );
}
