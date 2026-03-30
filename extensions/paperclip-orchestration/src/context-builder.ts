import type { PaperclipIssue } from "./api-client.js";

/**
 * Builds the Paperclip task context block injected into the agent's system prompt.
 * Matches the format Paperclip's openclaw-gateway wake text already uses,
 * so agents trained on either path see consistent instructions.
 */
export function buildTaskContextBlock(
  issue: PaperclipIssue,
  apiEndpoint: string,
): string {
  const lines: string[] = [
    "## Paperclip Task Context",
    "",
    "You are an agent in a Paperclip-orchestrated company. You have been assigned a task.",
    "",
    `**Task ID:** ${issue.id}`,
    `**Title:** ${issue.title}`,
  ];

  if (issue.description) {
    lines.push(`**Description:**`);
    lines.push(issue.description.trim());
  }

  lines.push(
    `**Status:** ${issue.status}`,
    `**Priority:** ${issue.priority ?? "normal"}`,
    "",
    "### How to report your work",
    "",
    `API base: \`${apiEndpoint}\``,
    "Auth: `Authorization: Bearer $PAPERCLIP_API_KEY` (injected by Paperclip)",
    "Run ID header: `X-Paperclip-Run-Id: $PAPERCLIP_RUN_ID` (required on all mutations)",
    "",
    "**Checkout the task before starting:**",
    "```",
    `POST ${apiEndpoint}/api/issues/${issue.id}/checkout`,
    `{ "agentId": "$PAPERCLIP_AGENT_ID", "expectedStatuses": ["todo", "backlog", "in_progress"] }`,
    "```",
    "",
    "**Post a comment when you have an update:**",
    "```",
    `POST ${apiEndpoint}/api/issues/${issue.id}/comments`,
    `{ "body": "Your update here" }`,
    "```",
    "",
    "**Mark the task done when complete:**",
    "```",
    `PATCH ${apiEndpoint}/api/issues/${issue.id}`,
    `{ "status": "done" }`,
    "```",
  );

  return lines.join("\n");
}
