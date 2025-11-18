"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import type {
  ProjectListResponse,
  ProjectSummary,
} from "@/lib/composer/projectSummary";
import {
  addProjectDerivedFields,
  PROJECTS_PAGE_SIZE,
} from "@/lib/composer/projectUtils";

interface FiltersState {
  search: string;
  status: string;
  strategy: string;
  page: number;
  pageSize: number;
}

const STATUS_FILTERS = [
  { label: "All", value: "all" },
  { label: "Draft", value: "draft" },
  { label: "In Progress", value: "in_progress" },
  { label: "Ready for Review", value: "ready_for_review" },
  { label: "Completed", value: "completed" },
];

const STRATEGY_FILTERS = [
  { label: "All", value: "all" },
  { label: "Variations", value: "variations" },
  { label: "Distinct", value: "distinct" },
];

export default function ComposerDashboardPage() {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const router = useRouter();
  const [sessionChecked, setSessionChecked] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [filters, setFilters] = useState<FiltersState>(
    () => ({
      search: "",
      status: "all",
      strategy: "all",
      page: 1,
      pageSize: PROJECTS_PAGE_SIZE,
    }),
  );
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setModalOpen] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [modalValues, setModalValues] = useState({
    projectName: "",
    clientName: "",
  });

  useEffect(() => {
    supabase.auth.getSession().then((result) => {
      setIsAuthenticated(!!result.data.session);
      setSessionChecked(true);
    });
  }, [supabase]);

  useEffect(() => {
    if (!isAuthenticated) return;

    const controller = new AbortController();
    const params = new URLSearchParams();
    if (filters.search) params.set("search", filters.search);
    if (filters.status !== "all") params.set("status", filters.status);
    if (filters.strategy !== "all") params.set("strategy", filters.strategy);
    params.set("page", String(filters.page));
    params.set("pageSize", String(filters.pageSize));

    setLoading(true);
    setError(null);
    fetch(`/api/composer/projects?${params.toString()}`, {
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.error || "Failed to load projects");
        }
        return res.json() as Promise<ProjectListResponse>;
      })
      .then((data) => {
        setProjects(data.projects);
        setTotal(data.total);
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          setError(err.message);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [filters, isAuthenticated]);

  const updateFilter = useCallback(
    (patch: Partial<FiltersState>) => {
      setFilters((prev) => ({ ...prev, ...patch, page: 1 }));
    },
    [],
  );

  const fetchLatestProjects = useCallback(async (): Promise<ProjectListResponse | null> => {
    try {
      const params = new URLSearchParams({
        page: "1",
        pageSize: String(PROJECTS_PAGE_SIZE),
      });
      const response = await fetch(`/api/composer/projects?${params.toString()}`);
      if (!response.ok) {
        return null;
      }
      const payload = (await response.json()) as ProjectListResponse;
      return payload;
    } catch (err) {
      console.error("Failed to refetch projects", err);
      return null;
    }
  }, []);

  const handleCreateProject = useCallback(async () => {
    if (!modalValues.projectName.trim()) {
      setModalError("Project name is required");
      return;
    }
    setModalLoading(true);
    setModalError(null);
    try {
      const response = await fetch("/api/composer/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          projectName: modalValues.projectName.trim(),
          clientName: modalValues.clientName.trim() || undefined,
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.error || "Failed to create project");
      }
      const project: ProjectSummary = await response.json();
      setModalOpen(false);
      setModalValues({ projectName: "", clientName: "" });
      setProjects((prev) => [project, ...prev]);

      const latestList = await fetchLatestProjects();
      if (latestList && latestList.projects.length) {
        setProjects(latestList.projects);
        setTotal(latestList.total);
      }

      const candidate =
        latestList?.projects.find((item) => {
          if (!item.projectName || !project.projectName) return false;
          if (item.projectName.trim() !== project.projectName.trim()) return false;
          if (project.lastEditedAt && item.lastEditedAt) {
            return Math.abs(
              new Date(item.lastEditedAt).getTime() - new Date(project.lastEditedAt).getTime(),
            ) < 1000;
          }
          return true;
        }) ?? (latestList?.projects ?? []).find((item) => !!item.id);

      if (!candidate?.id) {
        setModalError(
          "Project saved, but we couldn't open it automatically. Please refresh and resume from the list.",
        );
        return;
      }

      router.push(`/composer/${candidate.id}/${candidate.activeStep ?? "product_info"}`);
    } catch (err) {
      setModalError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setModalLoading(false);
    }
  }, [fetchLatestProjects, modalValues, router, setProjects, setTotal]);

  const derivedProjects = projects.map(addProjectDerivedFields);

  if (!sessionChecked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f1f5f9] text-sm text-[#475569]">
        Checking authentication…
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#f1f5f9] px-8 text-center text-[#475569]">
        <h1 className="text-2xl font-semibold text-[#0f172a]">Sign-in required</h1>
        <p className="mt-2 text-sm">You need to be authenticated to view Composer projects.</p>
        <button
          onClick={() => router.push("/")}
          className="mt-6 rounded-full bg-[#0a6fd6] px-5 py-2 text-sm font-semibold text-white shadow"
        >
          Go to login
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#eef2ff] via-[#f8fbff] to-[#ecf4ff] p-6">
      <div className="mx-auto w-full max-w-5xl space-y-6">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.4em] text-[#94a3b8]">
              Composer
            </p>
            <h1 className="text-3xl font-semibold text-[#0f172a]">Projects</h1>
            <p className="text-sm text-[#64748b]">{total} total</p>
          </div>
          <button
            onClick={() => setModalOpen(true)}
            className="rounded-full bg-[#0a6fd6] px-5 py-2 text-sm font-semibold text-white shadow-md transition hover:-translate-y-0.5 hover:bg-[#0959ab]"
          >
            New Project
          </button>
        </header>

        <div className="flex flex-wrap gap-3 rounded-3xl bg-white/90 p-4 shadow">
          <input
            type="text"
            placeholder="Search by client or project…"
            value={filters.search}
            onChange={(e) => updateFilter({ search: e.target.value })}
            className="flex-1 min-w-[220px] rounded-2xl border border-[#cbd5f5] px-4 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none"
          />
          <select
            value={filters.status}
            onChange={(e) => updateFilter({ status: e.target.value })}
            className="rounded-2xl border border-[#cbd5f5] bg-white px-4 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none"
          >
            {STATUS_FILTERS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            value={filters.strategy}
            onChange={(e) => updateFilter({ strategy: e.target.value })}
            className="rounded-2xl border border-[#cbd5f5] bg-white px-4 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none"
          >
            {STRATEGY_FILTERS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {loading ? (
          <div className="rounded-3xl bg-white/90 p-10 text-center text-sm text-[#64748b] shadow">
            Loading projects…
          </div>
        ) : error ? (
          <div className="rounded-3xl border border-[#fecaca] bg-[#fee2e2] p-6 text-sm text-[#b91c1c]">
            {error}
          </div>
        ) : derivedProjects.length === 0 ? (
          <div className="rounded-3xl bg-white/90 p-10 text-center shadow">
            <p className="text-lg font-semibold text-[#0f172a]">No Composer projects yet.</p>
            <p className="mt-2 text-sm text-[#475569]">Kick things off by creating your first project.</p>
            <button
              onClick={() => setModalOpen(true)}
              className="mt-6 rounded-full bg-[#0a6fd6] px-5 py-2 text-sm font-semibold text-white shadow"
            >
              Create Project
            </button>
          </div>
        ) : (
          <div className="overflow-hidden rounded-3xl bg-white/95 shadow">
            <table className="min-w-full divide-y divide-[#e2e8f0]">
              <thead className="bg-[#f8fbff] text-left text-xs font-semibold uppercase tracking-wide text-[#64748b]">
                <tr>
                  <th className="px-6 py-4">Project</th>
                  <th className="px-6 py-4">Marketplaces</th>
                  <th className="px-6 py-4">Strategy</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4">Current Step</th>
                  <th className="px-6 py-4">Last Edited</th>
                  <th className="px-6 py-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f1f5f9]">
                {derivedProjects.map((project) => (
                  <tr key={project.id} className="text-sm text-[#0f172a]">
                    <td className="px-6 py-4">
                      <p className="font-semibold">{project.projectName}</p>
                      <p className="text-xs text-[#64748b]">{project.clientName ?? "No client"}</p>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-wrap gap-1">
                        {project.marketplaces.length === 0 ? (
                          <span className="rounded-full bg-[#e2e8f0] px-2 py-0.5 text-xs text-[#475569]">
                            N/A
                          </span>
                        ) : (
                          project.marketplaces.map((marketplace) => (
                            <span
                              key={marketplace}
                              className="rounded-full bg-[#eef2ff] px-2 py-0.5 text-xs text-[#4338ca]"
                            >
                              {marketplace}
                            </span>
                          ))
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="rounded-full bg-[#f1f5f9] px-3 py-1 text-xs font-medium text-[#0f172a]">
                        {project.strategyType
                          ? project.strategyType === "variations"
                            ? "Variations"
                            : "Distinct"
                          : "Not set"}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="rounded-full bg-[#e0f2fe] px-3 py-1 text-xs font-medium text-[#0369a1]">
                        {project.status ?? "Draft"}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-[#0f172a]">{project.stepLabel}</td>
                    <td className="px-6 py-4 text-sm text-[#64748b]">{project.lastEditedLabel}</td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() =>
                          router.push(
                            `/composer/${project.id}/${project.activeStep ?? "product_info"}`,
                          )
                        }
                        className="rounded-full bg-[#0a6fd6] px-4 py-1.5 text-xs font-semibold text-white shadow"
                      >
                        Resume
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4 py-8">
          <div className="w-full max-w-sm rounded-3xl bg-white p-6 shadow-2xl">
            <h2 className="text-lg font-semibold text-[#0f172a]">New Composer Project</h2>
            <div className="mt-4 space-y-4">
              <div>
                <label className="text-xs uppercase tracking-wide text-[#94a3b8]">
                  Project name
                </label>
                <input
                  type="text"
                  value={modalValues.projectName}
                  onChange={(e) =>
                    setModalValues((prev) => ({ ...prev, projectName: e.target.value }))
                  }
                  className="mt-1 w-full rounded-2xl border border-[#cbd5f5] px-4 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none"
                  placeholder="e.g., Brand A — Spring Refresh"
                />
              </div>
              <div>
                <label className="text-xs uppercase tracking-wide text-[#94a3b8]">
                  Client name (optional)
                </label>
                <input
                  type="text"
                  value={modalValues.clientName}
                  onChange={(e) =>
                    setModalValues((prev) => ({ ...prev, clientName: e.target.value }))
                  }
                  className="mt-1 w-full rounded-2xl border border-[#cbd5f5] px-4 py-2 text-sm focus:border-[#0a6fd6] focus:outline-none"
                  placeholder="Client or Brand"
                />
              </div>
              {modalError && (
                <p className="rounded-2xl border border-[#fecaca] bg-[#fee2e2] px-3 py-2 text-xs text-[#b91c1c]">
                  {modalError}
                </p>
              )}
            </div>
            <div className="mt-6 flex items-center justify-end gap-2">
              <button
                onClick={() => {
                  setModalOpen(false);
                  setModalError(null);
                }}
                className="rounded-full px-4 py-1.5 text-sm font-semibold text-[#475569]"
                disabled={modalLoading}
              >
                Cancel
              </button>
              <button
                onClick={handleCreateProject}
                disabled={modalLoading}
                className="rounded-full bg-[#0a6fd6] px-5 py-1.5 text-sm font-semibold text-white shadow disabled:opacity-70"
              >
                {modalLoading ? "Creating…" : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
