export interface PaperclipIssue {
  id: string;
  title: string;
  description?: string;
  status: string;
  priority?: string;
  assigneeAgentId?: string;
  projectId?: string;
  companyId: string;
  createdAt: string;
}

export interface PaperclipAgent {
  id: string;
  name: string;
  role?: string;
  companyId: string;
}

export interface CreateIssueParams {
  companyId: string;
  title: string;
  description?: string;
  assigneeAgentId?: string;
  priority?: "low" | "normal" | "high" | "urgent";
  source?: string;
}

export class PaperclipApiClient {
  private readonly endpoint: string;
  private readonly apiKey: string | undefined;

  constructor(endpoint: string, apiKey?: string) {
    this.endpoint = endpoint.replace(/\/$/, "");
    this.apiKey = apiKey;
  }

  private headers(): Record<string, string> {
    const h: Record<string, string> = { "Content-Type": "application/json" };
    if (this.apiKey) h["Authorization"] = `Bearer ${this.apiKey}`;
    return h;
  }

  async getIssue(issueId: string): Promise<PaperclipIssue | null> {
    try {
      const res = await fetch(`${this.endpoint}/api/issues/${issueId}`, {
        headers: this.headers(),
      });
      if (!res.ok) return null;
      return (await res.json()) as PaperclipIssue;
    } catch {
      return null;
    }
  }

  async createIssue(params: CreateIssueParams): Promise<PaperclipIssue | null> {
    try {
      const res = await fetch(`${this.endpoint}/api/issues`, {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify(params),
      });
      if (!res.ok) return null;
      return (await res.json()) as PaperclipIssue;
    } catch {
      return null;
    }
  }

  async postComment(issueId: string, body: string): Promise<boolean> {
    try {
      const res = await fetch(`${this.endpoint}/api/issues/${issueId}/comments`, {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify({ body }),
      });
      return res.ok;
    } catch {
      return false;
    }
  }

  async getCeoAgent(companyId: string): Promise<PaperclipAgent | null> {
    try {
      const res = await fetch(
        `${this.endpoint}/api/agents?companyId=${companyId}&role=ceo&limit=1`,
        { headers: this.headers() },
      );
      if (!res.ok) return null;
      const data = (await res.json()) as { agents?: PaperclipAgent[] };
      return data.agents?.[0] ?? null;
    } catch {
      return null;
    }
  }

  async ping(): Promise<boolean> {
    try {
      const res = await fetch(`${this.endpoint}/api/health`, {
        headers: this.headers(),
        signal: AbortSignal.timeout(3000),
      });
      return res.ok;
    } catch {
      return false;
    }
  }
}
