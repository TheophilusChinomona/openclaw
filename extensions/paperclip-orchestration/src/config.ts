export interface PaperclipOrchestrationConfig {
  enabled: boolean;
  apiEndpoint: string;
  apiKey?: string;
  taskContextInjection: {
    enabled: boolean;
    mode: "prepend" | "append";
  };
  inboundBridge: {
    enabled: boolean;
    companyId?: string;
    defaultAssigneeAgentId?: string;
    channels?: string[];
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function getPaperclipConfig(config: any): PaperclipOrchestrationConfig | null {
  const raw = config?.paperclip;
  if (!raw?.enabled) return null;

  // API key and endpoint can come from config OR environment variables.
  // This lets Docker deployments avoid putting secrets in the mounted config file:
  //   PAPERCLIP_BOARD_API_KEY — board API key for server-side calls
  //   PAPERCLIP_API_ENDPOINT  — override endpoint (e.g. for non-default ports)
  const apiKey =
    (raw.apiKey as string | undefined) ??
    process.env.PAPERCLIP_BOARD_API_KEY ??
    undefined;

  const apiEndpoint =
    (raw.apiEndpoint as string | undefined) ??
    process.env.PAPERCLIP_API_ENDPOINT ??
    "http://localhost:3100";

  return {
    enabled: true,
    apiEndpoint,
    apiKey,
    taskContextInjection: {
      enabled: (raw.taskContextInjection?.enabled as boolean | undefined) ?? true,
      mode: (raw.taskContextInjection?.mode as "prepend" | "append" | undefined) ?? "prepend",
    },
    inboundBridge: {
      enabled: (raw.inboundBridge?.enabled as boolean | undefined) ?? false,
      companyId: raw.inboundBridge?.companyId as string | undefined,
      defaultAssigneeAgentId: raw.inboundBridge?.defaultAssigneeAgentId as string | undefined,
      channels: raw.inboundBridge?.channels as string[] | undefined,
    },
  };
}
