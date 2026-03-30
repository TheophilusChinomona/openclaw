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

  return {
    enabled: true,
    apiEndpoint: (raw.apiEndpoint as string | undefined) ?? "http://localhost:3100",
    apiKey: raw.apiKey as string | undefined,
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
