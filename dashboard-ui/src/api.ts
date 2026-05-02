import type {
  ActivityFeedFilters,
  ActivityFeedResponse,
  AgentRunResponse,
  CandidatePatchInput,
  CandidatePromotionInput,
  CandidatePromotionResponse,
  DashboardNotificationsResponse,
  DecisionCreateInput,
  DecisionRecord,
  DecisionSupersedeInput,
  DashboardRequeueInput,
  IdeaWorkspaceResponse,
  IdeaSummary,
  IdeaTriageInput,
  DashboardProject,
  LangfusePromptsResponse,
  LangfuseSummaryResponse,
  LangfuseTracesFilters,
  LangfuseTracesResponse,
  NotificationEventRecord,
  HandoffSummary,
  IdeasOverviewResponse,
  OverviewResponse,
  ProjectGraphResponse,
  ProjectDetailResponse,
  ResearchQueueItem,
  ResearchOverviewResponse,
  ProjectPatchInput,
  ProjectStateInput,
  TaskCreateInput,
  TaskPatchInput,
  TaskRecord,
  TasksBoardFilters,
  TasksBoardResponse,
  RunDetail,
  RunSummary,
  RadarApplyLog,
  RadarApplyResult,
  RadarCandidate,
  RadarCandidateInput,
  RadarConfigItem,
  RadarEvidence,
  RadarEvidenceInput,
  RadarFileImport,
  RadarPrompt,
  RadarPromptInput,
  RadarPortfolioCompareResponse,
  RadarPortfolioMatrix,
  RadarPortfolioOverview,
  RadarPromotionRequest,
  RadarPromotionResult,
  RadarPromotionPreview,
  RadarCandidateLink,
  RadarRiskDistributionItem,
  RadarSelectionQueueItem,
  RadarPromptRenderInput,
  RadarPromptRenderResult,
  RadarPromptRun,
  RadarPromptRunPatchInput,
  RadarPromptVersion,
  RadarPromptVersionInput,
  SystemHealthResponse,
  SystemIntegrationsResponse,
  SystemJobsResponse,
  TelegramSummaryResponse,
} from "./types";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") || "http://localhost:8080";
const apiToken = (import.meta.env.VITE_API_TOKEN as string | undefined) || "dev-token";

function buildUrl(path: string, params?: Record<string, string>) {
  const url = new URL(`${apiBaseUrl}${path}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value) {
        url.searchParams.set(key, value);
      }
    });
  }
  return url.toString();
}

async function dashboardFetch<T>(path: string, params?: Record<string, string>): Promise<T> {
  const response = await fetch(buildUrl(path, params), {
    headers: {
      Authorization: `Bearer ${apiToken}`,
    },
  });

  if (!response.ok) {
    let detail = "Unexpected dashboard error";
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

async function dashboardWrite<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(buildUrl(path), {
    ...init,
    headers: {
      Authorization: `Bearer ${apiToken}`,
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });

  if (!response.ok) {
    let detail = "Unexpected dashboard error";
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
      }
    } catch {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function getOverview() {
  return dashboardFetch<OverviewResponse>("/dashboard/overview");
}

export function getRadarCandidates() {
  return dashboardFetch<RadarCandidate[]>("/radar/candidates");
}

export function getRadarCandidate(candidateId: string) {
  return dashboardFetch<RadarCandidate>(`/radar/candidates/${candidateId}`);
}

export function createRadarCandidate(payload: RadarCandidateInput & { slug: string; name: string }) {
  return dashboardWrite<RadarCandidate>("/radar/candidates", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateRadarCandidate(candidateId: string, payload: RadarCandidateInput) {
  return dashboardWrite<RadarCandidate>(`/radar/candidates/${candidateId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteRadarCandidate(candidateId: string) {
  return dashboardWrite<void>(`/radar/candidates/${candidateId}`, {
    method: "DELETE",
  });
}

export function getRadarCandidateEvidence(candidateId: string) {
  return dashboardFetch<RadarEvidence[]>(`/radar/candidates/${candidateId}/evidence`);
}

export function createRadarCandidateEvidence(candidateId: string, payload: RadarEvidenceInput) {
  return dashboardWrite<RadarEvidence>(`/radar/candidates/${candidateId}/evidence`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteRadarEvidence(evidenceId: string) {
  return dashboardWrite<void>(`/radar/evidence/${evidenceId}`, {
    method: "DELETE",
  });
}

export function getRadarPrompts() {
  return dashboardFetch<RadarPrompt[]>("/radar/prompts");
}

export function getRadarPrompt(promptId: string) {
  return dashboardFetch<RadarPrompt>(`/radar/prompts/${promptId}`);
}

export function createRadarPrompt(payload: RadarPromptInput & { key: string; title: string; prompt_type: string }) {
  return dashboardWrite<RadarPrompt>("/radar/prompts", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateRadarPrompt(promptId: string, payload: RadarPromptInput) {
  return dashboardWrite<RadarPrompt>(`/radar/prompts/${promptId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteRadarPrompt(promptId: string) {
  return dashboardWrite<void>(`/radar/prompts/${promptId}`, {
    method: "DELETE",
  });
}

export function getRadarPromptVersions(promptId: string) {
  return dashboardFetch<RadarPromptVersion[]>(`/radar/prompts/${promptId}/versions`);
}

export function createRadarPromptVersion(promptId: string, payload: RadarPromptVersionInput) {
  return dashboardWrite<RadarPromptVersion>(`/radar/prompts/${promptId}/versions`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function renderRadarPromptVersion(promptId: string, versionId: string, payload: RadarPromptRenderInput) {
  return dashboardWrite<RadarPromptRenderResult>(`/radar/prompts/${promptId}/versions/${versionId}/render`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getRadarPromptRuns(filters: {
  candidate_id?: string;
  prompt_id?: string;
  status?: string;
  limit?: string;
}) {
  return dashboardFetch<RadarPromptRun[]>("/radar/prompt-runs", filters);
}

export function getRadarPromptRun(promptRunId: string) {
  return dashboardFetch<RadarPromptRun>(`/radar/prompt-runs/${promptRunId}`);
}

export function updateRadarPromptRun(promptRunId: string, payload: RadarPromptRunPatchInput) {
  return dashboardWrite<RadarPromptRun>(`/radar/prompt-runs/${promptRunId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function markRadarPromptRunCopied(promptRunId: string) {
  return dashboardWrite<RadarPromptRun>(`/radar/prompt-runs/${promptRunId}/mark-copied`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function cancelRadarPromptRun(promptRunId: string) {
  return dashboardWrite<RadarPromptRun>(`/radar/prompt-runs/${promptRunId}/cancel`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function getRadarConfig() {
  return dashboardFetch<RadarConfigItem[]>("/radar/config");
}

export function getRadarApplyLogs(filters: {
  candidate_id?: string;
  status?: string;
  limit?: string;
}) {
  return dashboardFetch<RadarApplyLog[]>("/radar/apply-logs", filters);
}

export function getRadarApplyLog(applyLogId: string) {
  return dashboardFetch<RadarApplyLog>(`/radar/apply-logs/${applyLogId}`);
}

export function getRadarFileImports(filters: {
  status?: string;
  file_hash?: string;
  limit?: string;
}) {
  return dashboardFetch<RadarFileImport[]>("/radar/file-imports", filters);
}

export function getRadarFileImport(fileImportId: string) {
  return dashboardFetch<RadarFileImport>(`/radar/file-imports/${fileImportId}`);
}

export function getRadarPortfolioOverview() {
  return dashboardFetch<RadarPortfolioOverview>("/radar/portfolio/overview");
}

export function getRadarPortfolioFocusScopeMatrix() {
  return dashboardFetch<RadarPortfolioMatrix>("/radar/portfolio/matrix/focus-scope");
}

export function getRadarPortfolioMaturityVerdictMatrix() {
  return dashboardFetch<RadarPortfolioMatrix>("/radar/portfolio/matrix/maturity-verdict");
}

export function getRadarPortfolioRiskDistribution() {
  return dashboardFetch<RadarRiskDistributionItem[]>("/radar/portfolio/risk-distribution");
}

export function getRadarPortfolioSelectionQueue() {
  return dashboardFetch<RadarSelectionQueueItem[]>("/radar/portfolio/selection-queue");
}

export function compareRadarPortfolioCandidates(candidateIds: string[]) {
  return dashboardWrite<RadarPortfolioCompareResponse>("/radar/portfolio/compare", {
    method: "POST",
    body: JSON.stringify({ candidate_ids: candidateIds }),
  });
}

export function getRadarCandidateLinks(candidateId: string) {
  return dashboardFetch<RadarCandidateLink[]>(`/radar/candidates/${candidateId}/links`);
}

export function getRadarPromotionPreview(candidateId: string) {
  return dashboardFetch<RadarPromotionPreview>(`/radar/candidates/${candidateId}/promotion/preview`);
}

export function promoteRadarCandidate(candidateId: string, payload: RadarPromotionRequest) {
  return dashboardWrite<RadarPromotionResult>(`/radar/candidates/${candidateId}/promotion`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function applyRadarJson(
  payload: Record<string, unknown>,
  options?: { dryRun?: boolean },
) {
  const path = options?.dryRun ? "/radar/apply-json?dry_run=true" : "/radar/apply-json";
  return dashboardWrite<RadarApplyResult>(path, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getActivityFeed(filters: ActivityFeedFilters) {
  return dashboardFetch<ActivityFeedResponse>("/dashboard/activity-feed", filters);
}

export function getProjects(filters: {
  status?: string;
  kind?: string;
  host_machine?: string;
  q?: string;
}) {
  return dashboardFetch<DashboardProject[]>("/dashboard/projects", filters);
}

export function getProjectDetail(projectId: string) {
  return dashboardFetch<ProjectDetailResponse>(`/dashboard/projects/${projectId}`);
}

export function updateProjectState(projectId: string, payload: ProjectStateInput) {
  return dashboardWrite<ProjectDetailResponse["state"]>(`/state/${projectId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function patchProject(projectId: string, payload: ProjectPatchInput) {
  return dashboardWrite<ProjectDetailResponse["project"]>(`/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function getProjectGraph(projectId: string) {
  return dashboardFetch<ProjectGraphResponse>(`/dashboard/projects/${projectId}/graph`);
}

export function getResearchOverview() {
  return dashboardFetch<ResearchOverviewResponse>("/dashboard/research/overview");
}

export function getRecentRuns(filters: {
  project_id?: string;
  agent?: string;
  status?: string;
  mode?: string;
}) {
  return dashboardFetch<RunSummary[]>("/dashboard/runs/recent", filters);
}

export function getRunDetail(runId: string) {
  return dashboardFetch<RunDetail>(`/dashboard/runs/${runId}`);
}

export function getLangfuseSummary() {
  return dashboardFetch<LangfuseSummaryResponse>("/dashboard/langfuse/summary");
}

export function getLangfusePrompts() {
  return dashboardFetch<LangfusePromptsResponse>("/dashboard/langfuse/prompts");
}

export function getLangfuseTraces(filters: LangfuseTracesFilters) {
  return dashboardFetch<LangfuseTracesResponse>("/dashboard/langfuse/traces", filters);
}

export function getNotifications(filters: {
  channel?: string;
  direction?: string;
  delivery_status?: string;
  project_id?: string;
}) {
  return dashboardFetch<DashboardNotificationsResponse>("/dashboard/notifications", filters);
}

export function getNotificationDetail(notificationId: string) {
  return dashboardFetch<NotificationEventRecord>(`/dashboard/notifications/${notificationId}`);
}

export function getTelegramSummary() {
  return dashboardFetch<TelegramSummaryResponse>("/dashboard/telegram/summary");
}

export function getOpenHandoffs(filters: {
  to_actor?: string;
  project_id?: string;
}) {
  return dashboardFetch<HandoffSummary[]>("/dashboard/handoffs/open", filters);
}

export function getIdeasOverview() {
  return dashboardFetch<IdeasOverviewResponse>("/dashboard/ideas/overview");
}

export function getIdeaWorkspace(ideaId: string) {
  return dashboardFetch<IdeaWorkspaceResponse>(`/dashboard/ideas/${ideaId}/workspace`);
}

export function getTasksBoard(filters?: TasksBoardFilters) {
  return dashboardFetch<TasksBoardResponse>("/dashboard/tasks/board", filters);
}

export function getTasks(filters: {
  idea_id?: string;
  project_id?: string;
  candidate_id?: string;
  status?: string;
}) {
  return dashboardFetch<TaskRecord[]>("/tasks", filters);
}

export function createTask(payload: TaskCreateInput) {
  return dashboardWrite<TaskRecord>("/tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function runDashboardAgent(payload: { target_type: "project" | "candidate"; target_id: string }) {
  return dashboardWrite<AgentRunResponse>("/dashboard/actions/run-agent", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function requeueResearchQueue(payload: DashboardRequeueInput) {
  return dashboardWrite<ResearchQueueItem>("/dashboard/actions/requeue", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function resolveDashboardHandoff(payload: { handoff_id: string; resolution_note?: string | null }) {
  return dashboardWrite<HandoffSummary>("/dashboard/actions/resolve-handoff", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function triageIdea(ideaId: string, payload: IdeaTriageInput) {
  return dashboardWrite<IdeaSummary>(`/ideas/${ideaId}/triage`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function createDecision(payload: DecisionCreateInput) {
  return dashboardWrite<DecisionRecord>("/decisions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function supersedeDecision(decisionId: string, payload: DecisionSupersedeInput) {
  return dashboardWrite<DecisionRecord>(`/decisions/${decisionId}/supersede`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function promoteCandidate(candidateRef: string, payload: CandidatePromotionInput) {
  return dashboardWrite<CandidatePromotionResponse>(`/candidates/${candidateRef}/promote`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCandidate(candidateRef: string, payload: CandidatePatchInput) {
  return dashboardWrite<ResearchOverviewResponse["candidates"][number]>(`/candidates/${candidateRef}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function updateTask(taskId: string, payload: TaskPatchInput) {
  return dashboardWrite<TaskRecord>(`/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteTask(taskId: string) {
  return dashboardWrite<void>(`/tasks/${taskId}`, {
    method: "DELETE",
  });
}

export function getSystemHealth() {
  return dashboardFetch<SystemHealthResponse>("/dashboard/system/health");
}

export function getSystemJobs() {
  return dashboardFetch<SystemJobsResponse>("/dashboard/system/jobs");
}

export function getSystemIntegrations() {
  return dashboardFetch<SystemIntegrationsResponse>("/dashboard/system/integrations");
}
