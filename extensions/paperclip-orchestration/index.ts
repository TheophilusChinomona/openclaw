import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { PaperclipApiClient } from "./src/api-client.js";
import { buildTaskContextBlock } from "./src/context-builder.js";
import { getPaperclipConfig } from "./src/config.js";
import { isPaperclipSession, parsePaperclipSessionKey } from "./src/session-key.js";

export default definePluginEntry({
  id: "paperclip-orchestration",
  name: "Paperclip Orchestration",
  description:
    "Connects OpenClaw agents to a Paperclip orchestration layer. Injects task context into agent prompts, reports results back, and bridges inbound channel messages to Paperclip tasks.",

  register(api) {
    // -------------------------------------------------------------------------
    // 1. BEFORE_PROMPT_BUILD — inject Paperclip task context into system prompt
    //    Fires for every agent run. We check if the session key is a Paperclip
    //    session (starts with "paperclip:") and if so fetch + inject the task.
    // -------------------------------------------------------------------------
    api.on("before_prompt_build", async (_event, ctx) => {
      const cfg = getPaperclipConfig(api.config);
      if (!cfg || !cfg.taskContextInjection.enabled) return;
      if (!isPaperclipSession(ctx.sessionKey)) return;

      const sessionInfo = parsePaperclipSessionKey(ctx.sessionKey!);
      if (!sessionInfo || sessionInfo.type !== "issue") return;

      const client = new PaperclipApiClient(cfg.apiEndpoint, cfg.apiKey);
      const issue = await client.getIssue(sessionInfo.issueId);
      if (!issue) return;

      const contextBlock = buildTaskContextBlock(issue, cfg.apiEndpoint);

      return cfg.taskContextInjection.mode === "prepend"
        ? { prependSystemContext: `${contextBlock}\n\n` }
        : { appendSystemContext: `\n\n${contextBlock}` };
    });

    // -------------------------------------------------------------------------
    // 2. AGENT_END — post a summary comment back to the Paperclip issue
    //    Only fires for Paperclip sessions. Uses the agent's own run context
    //    (PAPERCLIP_* env vars) rather than the board API key so the comment
    //    is attributed to the correct agent run.
    // -------------------------------------------------------------------------
    api.on("agent_end", async (event, ctx) => {
      const cfg = getPaperclipConfig(api.config);
      if (!cfg) return;
      if (!isPaperclipSession(ctx.sessionKey)) return;

      const sessionInfo = parsePaperclipSessionKey(ctx.sessionKey!);
      if (!sessionInfo || sessionInfo.type !== "issue") return;

      // Only post if agent produced output and didn't error
      const outcome = (event as { outcome?: string }).outcome;
      if (outcome === "error") return;

      const summary = (event as { summary?: string; text?: string }).summary
        ?? (event as { summary?: string; text?: string }).text;
      if (!summary) return;

      const client = new PaperclipApiClient(cfg.apiEndpoint, cfg.apiKey);
      await client.postComment(
        sessionInfo.issueId,
        `**Agent update** (via OpenClaw)\n\n${summary}`,
      );
    });

    // -------------------------------------------------------------------------
    // 3. MESSAGE_RECEIVED — inbound channel bridge
    //    If enabled, turns inbound WhatsApp/Telegram/Discord messages into
    //    Paperclip tasks. Only fires when inboundBridge.enabled = true.
    // -------------------------------------------------------------------------
    api.on("message_received", async (event, ctx) => {
      const cfg = getPaperclipConfig(api.config);
      if (!cfg || !cfg.inboundBridge.enabled) return;

      // Only bridge configured channels (or all if channels array is empty)
      const { channels, companyId, defaultAssigneeAgentId } = cfg.inboundBridge;
      if (channels && channels.length > 0 && ctx.channelId && !channels.includes(ctx.channelId)) {
        return;
      }

      if (!companyId) return;

      const msgEvent = event as { body?: string; from?: string };
      const body = msgEvent.body?.trim();
      if (!body || body.length < 5) return;

      // Skip if this is already a Paperclip-keyed session (heartbeat-triggered)
      if (isPaperclipSession(ctx.sessionKey)) return;

      const client = new PaperclipApiClient(cfg.apiEndpoint, cfg.apiKey);

      const issue = await client.createIssue({
        companyId,
        title: body.length > 80 ? `${body.slice(0, 77)}...` : body,
        description: [
          `**Inbound message via OpenClaw**`,
          `Channel: ${ctx.channelId ?? "unknown"}`,
          `From: ${msgEvent.from ?? "unknown"}`,
          "",
          body,
        ].join("\n"),
        assigneeAgentId: defaultAssigneeAgentId,
        priority: "normal",
        source: "openclaw_inbound",
      });

      if (issue) {
        api.logger.info(
          `[paperclip-orchestration] Created task ${issue.id} from inbound ${ctx.channelId} message`,
        );
      }
    });

    // -------------------------------------------------------------------------
    // 4. GATEWAY METHODS — additional WebSocket RPC endpoints for Paperclip
    //    These let Paperclip query OpenClaw state and vice-versa beyond the
    //    standard openclaw-gateway adapter protocol.
    // -------------------------------------------------------------------------

    // paperclip/status — health check, lets Paperclip verify the extension is active
    api.registerGatewayMethod("paperclip/status", async (_params, _ctx) => {
      const cfg = getPaperclipConfig(api.config);
      if (!cfg) {
        return { enabled: false, message: "Paperclip integration not configured" };
      }

      const client = new PaperclipApiClient(cfg.apiEndpoint, cfg.apiKey);
      const reachable = await client.ping();

      return {
        enabled: true,
        apiEndpoint: cfg.apiEndpoint,
        reachable,
        taskContextInjection: cfg.taskContextInjection.enabled,
        inboundBridge: cfg.inboundBridge.enabled,
      };
    });

    // paperclip/task-context — fetch task context for a given session key
    // Paperclip can call this to verify what context was injected
    api.registerGatewayMethod(
      "paperclip/task-context",
      async (params: unknown, _ctx) => {
        const { sessionKey } = params as { sessionKey?: string };
        if (!sessionKey) return { error: "sessionKey required" };

        const cfg = getPaperclipConfig(api.config);
        if (!cfg) return { error: "Paperclip integration not configured" };

        const sessionInfo = parsePaperclipSessionKey(sessionKey);
        if (!sessionInfo || sessionInfo.type !== "issue") {
          return { error: "Not a Paperclip issue session key" };
        }

        const client = new PaperclipApiClient(cfg.apiEndpoint, cfg.apiKey);
        const issue = await client.getIssue(sessionInfo.issueId);
        if (!issue) return { error: `Issue ${sessionInfo.issueId} not found` };

        return { issue, contextBlock: buildTaskContextBlock(issue, cfg.apiEndpoint) };
      },
    );

    // paperclip/heartbeat-ack — Paperclip signals a heartbeat was received
    // OpenClaw can use this to log or trigger session pre-warming
    api.registerGatewayMethod(
      "paperclip/heartbeat-ack",
      async (params: unknown, _ctx) => {
        const { runId, agentId, issueId } = params as {
          runId?: string;
          agentId?: string;
          issueId?: string;
        };

        api.logger.info(
          `[paperclip-orchestration] Heartbeat ack — run=${runId} agent=${agentId} issue=${issueId}`,
        );

        return { ok: true };
      },
    );

    api.logger.info("[paperclip-orchestration] Extension registered");
  },
});
