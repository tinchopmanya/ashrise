import type {
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
