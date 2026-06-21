// Browser API client for the refle API.
// Auth uses an httpOnly session cookie set by the API. The browser never reads or
// stores the JWT in JS; every request sends the cookie via credentials: "include".

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function toError(res: Response): Promise<ApiError> {
  const body = (await res.json().catch(() => null)) as
    | { detail?: string | { msg?: string }[] }
    | null;
  let message = res.statusText;
  if (typeof body?.detail === "string") {
    message = body.detail;
  } else if (Array.isArray(body?.detail)) {
    // FastAPI validation errors come back as a list of {loc, msg, ...}.
    message = body.detail.map((e) => e.msg ?? "invalid input").join("; ");
  }
  return new ApiError(res.status, message);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "content-type": "application/json",
      ...((options.headers as Record<string, string>) ?? {}),
    },
  });
  if (!res.ok) throw await toError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function postForm<T>(path: string, form: FormData): Promise<T> {
  // Let the browser set the multipart boundary; do not set content-type.
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: form,
    credentials: "include",
  });
  if (!res.ok) throw await toError(res);
  return (await res.json()) as T;
}

export type Role = "owner" | "admin" | "member" | "auditor";
export type ControlStatus = "passing" | "failing" | "not_assessed";

export type AuthToken = {
  access_token: string;
  token_type: string;
  organization_id: string;
  role: Role;
};

export type Org = { id: string; name: string; slug: string };
export type Me = {
  id: string;
  email: string;
  full_name: string | null;
  organization_id: string;
  role: Role;
  memberships: { organization: Org; role: Role }[];
};

export type Control = {
  id: string;
  code: string;
  title: string;
  description: string | null;
  category: string | null;
};
export type OrgControl = {
  id: string;
  control: Control;
  status: ControlStatus;
  owner_id: string | null;
};
export type Posture = {
  total: number;
  passing: number;
  failing: number;
  not_assessed: number;
  percent_passing: number;
};

export type Evidence = {
  id: string;
  name: string;
  description: string | null;
  filename: string;
  content_type: string | null;
  size_bytes: number;
  source: string;
  uploaded_by_id: string | null;
  control_codes: string[];
  created_at: string;
};

export type Policy = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  latest_version: number | null;
  accepted_count: number;
  accepted_by_me: boolean;
};

export type PolicyVersion = {
  id: string;
  version: number;
  body: string;
  created_at: string;
  status: "draft" | "published" | "archived";
};

export type PolicyDetail = Policy & {
  versions: PolicyVersion[];
};

export type PolicyTemplate = {
  id: string;
  name: string;
  description: string | null;
  type: "builtin" | "custom";
  organization_id: string | null;
  created_at: string;
};

export type PolicyTemplateDetail = PolicyTemplate & {
  body: string;
};

export type ConnectorInfo = {
  key: string;
  name: string;
  description: string;
  credential_fields: string[];
};
export type Connection = {
  id: string;
  provider: string;
  label: string;
  status: "never_synced" | "connected" | "error";
  last_synced_at: string | null;
  last_error: string | null;
  created_at: string;
};
export type SyncResult = {
  ok: boolean;
  tests_run: number;
  failures: number;
  error: string | null;
};
export type TestResultRow = {
  id: string;
  test_key: string;
  control_code: string;
  passed: boolean;
  detail: string | null;
  created_at: string;
};
export type RemediationTaskRow = {
  id: string;
  title: string;
  control_code: string | null;
  detail: string | null;
  status: string;
  created_at: string;
};

export type Citation = {
  n: number;
  source_type: string;
  source_id: string;
  title: string;
};
export type ChatResponse = {
  answer: string;
  citations: Citation[];
  generated: boolean;
  model: string;
};
export type AIStatus = {
  provider: string;
  model: string;
  agent_model: string;
  sovereign: boolean;
  embedding_provider: string;
  indexed_chunks: number;
};

export type NotificationLevel = "info" | "warning";

export type NotificationOut = {
  id: string;
  type: string;
  title: string;
  body: string;
  level: NotificationLevel;
  read_at: string | null;
  created_at: string;
};

export type NotificationSettingOut = {
  id: string;
  channels: string;
  email_to: string | null;
  slack_webhook_configured: boolean;
};

export const api = {
  register: (d: {
    org_name: string;
    email: string;
    password: string;
    full_name?: string;
  }) =>
    request<AuthToken>("/auth/register", {
      method: "POST",
      body: JSON.stringify(d),
    }),
  login: (d: { email: string; password: string }) =>
    request<AuthToken>("/auth/login", { method: "POST", body: JSON.stringify(d) }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<Me>("/auth/me"),

  controls: () => request<OrgControl[]>("/controls"),
  posture: () => request<Posture>("/controls/posture"),
  updateControl: (id: string, d: { status?: ControlStatus; owner_id?: string }) =>
    request<OrgControl>(`/controls/${id}`, {
      method: "PATCH",
      body: JSON.stringify(d),
    }),

  listEvidence: () => request<Evidence[]>("/evidence"),
  uploadEvidence: (form: FormData) => postForm<Evidence>("/evidence", form),
  evidenceDownloadUrl: (id: string) =>
    request<{ url: string }>(`/evidence/${id}/download`),

  listPolicies: () => request<Policy[]>("/policies"),
  getPolicy: (id: string) => request<PolicyDetail>(`/policies/${id}`),
  createPolicy: (d: { name: string; description?: string; body: string }) =>
    request<PolicyDetail>("/policies", { method: "POST", body: JSON.stringify(d) }),
  acceptPolicy: (id: string) =>
    request<Policy>(`/policies/${id}/accept`, { method: "POST" }),
  updatePolicyVersion: (id: string, version: number, d: { body: string }) =>
    request<PolicyDetail>(`/policies/${id}/versions/${version}`, { method: "PUT", body: JSON.stringify(d) }),
  publishPolicyVersion: (id: string, version: number) =>
    request<PolicyDetail>(`/policies/${id}/versions/${version}/publish`, { method: "POST" }),
  draftPolicy: (d: { name: string; instructions?: string; template_id?: string; evidence_id?: string }) =>
    request<PolicyDetail>("/ai/agents/draft-policy", { method: "POST", body: JSON.stringify(d) }),

  listTemplates: () => request<PolicyTemplate[]>("/templates"),
  createTemplate: (d: { name: string; description?: string; body: string }) =>
    request<PolicyTemplate>("/templates", { method: "POST", body: JSON.stringify(d) }),
  getTemplate: (id: string) => request<PolicyTemplateDetail>(`/templates/${id}`),

  connectors: () => request<ConnectorInfo[]>("/integrations/connectors"),
  connections: () => request<Connection[]>("/connections"),
  createConnection: (d: {
    provider: string;
    label: string;
    credentials: Record<string, string>;
  }) => request<Connection>("/connections", { method: "POST", body: JSON.stringify(d) }),
  syncConnection: (id: string) =>
    request<SyncResult>(`/connections/${id}/sync`, { method: "POST" }),
  remediationTasks: () => request<RemediationTaskRow[]>("/remediation-tasks"),

  aiStatus: () => request<AIStatus>("/ai/status"),
  aiReindex: () => request<{ indexed: number }>("/ai/reindex", { method: "POST" }),
  aiChat: (question: string) =>
    request<ChatResponse>("/ai/chat", {
      method: "POST",
      body: JSON.stringify({ question }),
    }),

  notifications: () => request<NotificationOut[]>("/notifications"),
  markNotificationRead: (id: string) =>
    request<NotificationOut>(`/notifications/${id}/read`, { method: "POST" }),
  notificationSettings: () => request<NotificationSettingOut>("/notifications/settings"),
  updateNotificationSettings: (d: { channels?: string; email_to?: string; slack_webhook_url?: string }) =>
    request<NotificationSettingOut>("/notifications/settings", { method: "PUT", body: JSON.stringify(d) }),
};
