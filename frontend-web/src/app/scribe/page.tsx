"use client";

import { useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import type { Session } from "@supabase/supabase-js";

type ScribeProjectStatus = "draft" | "topics_generated" | "copy_generated" | "approved" | "archived";

interface ScribeProjectSummary {
  id: string;
  name: string;
  marketplaces: string[];
  category: string | null;
  subCategory: string | null;
  status: ScribeProjectStatus | null;
  createdAt: string;
  updatedAt: string;
}

interface ProjectListResponse {
  projects: ScribeProjectSummary[];
  page: number;
  pageSize: number;
  total: number;
}

const STATUS_LABELS: Record<ScribeProjectStatus, string> = {
  draft: "Draft",
  topics_generated: "Topics Ready",
  copy_generated: "Copy Ready",
  approved: "Approved",
  archived: "Archived",
};

const formatDate = (value: string | null | undefined) => {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
};

export default function ScribeDashboardPage() {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [sessionChecked, setSessionChecked] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [projects, setProjects] = useState<ScribeProjectSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", marketplaces: "" });
  const [formError, setFormError] = useState<string | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }: { data: { session: Session | null } }) => {
      setIsAuthenticated(!!data.session);
      setSessionChecked(true);
    });
  }, [supabase]);

  useEffect(() => {
    if (!isAuthenticated) return;
    const controller = new AbortController();
    const params = new URLSearchParams({
      page: String(page),
      pageSize: String(pageSize),
    });
    setLoading(true);
    setError(null);
    fetch(`/api/scribe/projects?${params.toString()}`, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          const message = body?.error?.message ?? "Failed to load projects";
          throw new Error(message);
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
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [isAuthenticated, page, refreshTick]);

  const handleCreate = async () => {
    const name = form.name.trim();
    if (!name) {
      setFormError("Name is required");
      return;
    }
    setFormLoading(true);
    setFormError(null);
    try {
      const marketplaces =
        form.marketplaces
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean) ?? [];
      const res = await fetch("/api/scribe/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, marketplaces }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error?.message ?? "Failed to create project");
      }
      await res.json();
      setForm({ name: "", marketplaces: "" });
      setPage(1);
      setRefreshTick((t) => t + 1);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setFormLoading(false);
    }
  };

  const mutateProject = async (projectId: string, action: "archive" | "restore") => {
    const res = await fetch(`/api/scribe/projects/${projectId}/${action}`, { method: "POST" });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body?.error?.message ?? `Failed to ${action} project`);
    }
    await res.json();
    setPage(1); // refresh list
    setRefreshTick((t) => t + 1);
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (!sessionChecked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-600">
        Checking authentication…
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-600">
        Please sign in to use Scribe.
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold text-slate-900">Scribe Projects</h1>
        <p className="text-sm text-slate-600">
          Create and manage Scribe projects. Archived projects are read-only.
        </p>
      </header>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-lg font-medium text-slate-900">Create Project</h2>
        <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex flex-1 flex-col gap-1">
            <label className="text-xs font-medium text-slate-600">Name *</label>
            <input
              className="rounded border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none"
              placeholder="Project name"
              value={form.name}
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
            />
          </div>
          <div className="flex flex-1 flex-col gap-1">
            <label className="text-xs font-medium text-slate-600">Marketplaces (comma-separated)</label>
            <input
              className="rounded border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none"
              placeholder="US, CA, MX"
              value={form.marketplaces}
              onChange={(e) => setForm((prev) => ({ ...prev, marketplaces: e.target.value }))}
            />
          </div>
          <button
            className="w-full rounded-2xl bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
            onClick={handleCreate}
            disabled={formLoading}
          >
            {formLoading ? "Creating…" : "Create"}
          </button>
        </div>
        {formError ? <p className="mt-2 text-xs text-red-600">{formError}</p> : null}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-medium text-slate-900">Projects</h2>
          <div className="text-xs text-slate-500">
            Page {page} of {totalPages} — {total} total
          </div>
        </div>
        {error ? <p className="mb-3 text-sm text-red-600">{error}</p> : null}
        {loading ? (
          <p className="text-sm text-slate-600">Loading…</p>
        ) : projects.length === 0 ? (
          <p className="text-sm text-slate-600">No projects yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm text-slate-800">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2 pr-4">Name</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Marketplaces</th>
                  <th className="py-2 pr-4">Updated</th>
                  <th className="py-2 pr-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((project) => (
                  <tr key={project.id} className="border-b border-slate-100">
                    <td className="py-2 pr-4 font-medium text-slate-900">
                      <a
                        href={`/scribe/${project.id}`}
                        className="text-[#0a6fd6] underline-offset-2 hover:underline"
                      >
                        {project.name}
                      </a>
                    </td>
                    <td className="py-2 pr-4 text-slate-700">
                      {project.status ? STATUS_LABELS[project.status] : "—"}
                    </td>
                    <td className="py-2 pr-4 text-slate-700">
                      {project.marketplaces?.length ? project.marketplaces.join(", ") : "—"}
                    </td>
                    <td className="py-2 pr-4 text-slate-600">{formatDate(project.updatedAt)}</td>
                    <td className="py-2 pr-4">
                      {project.status === "archived" ? (
                        <button
                          className="rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-800 hover:bg-slate-50"
                          onClick={() => mutateProject(project.id, "restore").catch((err) => setError(err.message))}
                        >
                          Restore
                        </button>
                      ) : (
                        <button
                          className="rounded border border-red-200 bg-red-50 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-100"
                          onClick={() => mutateProject(project.id, "archive").catch((err) => setError(err.message))}
                        >
                          Archive
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-4 flex items-center gap-3 text-sm text-slate-700">
          <button
            className="rounded border border-slate-300 px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
          >
            Prev
          </button>
          <span>
            Page {page} / {totalPages}
          </span>
          <button
            className="rounded border border-slate-300 px-3 py-1 text-xs disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
          >
            Next
          </button>
        </div>
      </section>
    </div>
  );
}
