import type { ISODateString, ProjectId, StrategyType } from "@agency/lib/composer/types";

export interface ProjectSummary {
  id: ProjectId;
  projectName: string;
  clientName: string | null;
  marketplaces: string[];
  strategyType: StrategyType | null;
  status: string | null;
  activeStep: string | null;
  createdAt: ISODateString;
  lastEditedAt: ISODateString | null;
}

export interface ProjectListResponse {
  projects: ProjectSummary[];
  page: number;
  pageSize: number;
  total: number;
}

export interface ProjectListQuery {
  search?: string;
  status?: string;
  strategy?: string;
  page?: number;
  pageSize?: number;
}

export interface CreateProjectPayload {
  projectName: string;
  clientName?: string;
  marketplaces?: string[];
}
