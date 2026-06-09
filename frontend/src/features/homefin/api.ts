import axios from "axios"

import type { UserPublic } from "@/client"
import { OpenAPI } from "@/client"

export type Category = {
  id: string
  name: string
  parent_id: string | null
  color: string
  owner_id: string
  created_at: string | null
}

export type BudgetPeriod = 1 | 2 | 3

export type Budget = {
  id: string
  name: string
  year: number
  period: BudgetPeriod
  amount: number
  used_amount: number
  owner_id: string
  created_at: string | null
}

export type TransactionType = 1 | 2
export type EntryStatus = 1 | 2 | 3

export type TransactionDetailItem = {
  name: string
  remark?: string
  [key: string]: unknown
}

export type TransactionDetail = {
  note?: string
  items?: TransactionDetailItem[]
  extra?: Record<string, unknown>
  [key: string]: unknown
}

export type Transaction = {
  id: string
  category_id: string
  transaction_type: TransactionType
  budget_id: string | null
  summary: string | null
  description: string | null
  detail: TransactionDetail | null
  entry_status: EntryStatus
  handler_user_id: string | null
  handler_display_name: string | null
  transaction_date: string
  amount: number
  owner_id: string
  created_at: string | null
}

export type HandlerUserOption = {
  id: string
  full_name: string | null
  login_name: string
  display_name: string
}

export type DashboardSummary = {
  income: number
  expense: number
  balance: number
}

export type DashboardTrendPoint = {
  month: string
  income: number
  expense: number
}

export type DashboardCategoryShare = {
  category_id: string
  category_name: string
  amount: number
}

export type DashboardBudgetUsage = {
  budget_id: string
  budget_name: string
  amount: number
  used_amount: number
}

export type DashboardData = {
  summary: DashboardSummary
  trends: DashboardTrendPoint[]
  category_shares: DashboardCategoryShare[]
  budget_usage: DashboardBudgetUsage[]
}

export type ApiTokenRecord = {
  id: string
  name: string
  expires_at: string | null
  token_prefix: string
  is_active: boolean
  created_by: string
  last_used_at: string | null
  created_at: string | null
}

export type ApiTokenSecret = {
  token: string
  secret: string | null
  token_prefix: string
}

export type MfaSetupPayload = {
  secret: string
  otpauth_uri: string
}

export type DataJobType = "EXPORT" | "IMPORT"
export type DataJobStatus =
  | "PENDING"
  | "PROCESSING"
  | "SUCCEEDED"
  | "PARTIAL_SUCCESS"
  | "FAILED"
  | "CANCELLED"

export type DataJobRecord = {
  id: string
  job_type: DataJobType
  status: DataJobStatus
  template_version: string
  created_by: string
  total_rows: number
  success_rows: number
  failed_rows: number
  skipped_rows: number
  progress_percent: number
  failure_reason: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string | null
  has_result_file: boolean
  has_error_file: boolean
}

type PagedResponse<T> = {
  data: T[]
  count: number
}

export type PaginationParams = {
  page?: number
  page_size?: number
}

type MessageResponse = {
  message: string
}

const authHeaders = () => {
  const token = localStorage.getItem("access_token")
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function apiRequest<T>(config: {
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  url: string
  params?: Record<string, unknown>
  data?: unknown
}): Promise<T> {
  const response = await axios.request<T>({
    baseURL: OpenAPI.BASE,
    headers: authHeaders(),
    method: config.method,
    url: config.url,
    params: config.params,
    data: config.data,
  })
  return response.data
}

async function downloadRequest(config: {
  method: "GET" | "POST"
  url: string
  data?: unknown
}): Promise<Blob> {
  const response = await axios.request<Blob>({
    baseURL: OpenAPI.BASE,
    headers: authHeaders(),
    method: config.method,
    url: config.url,
    data: config.data,
    responseType: "blob",
  })
  return response.data
}

export const homefinApi = {
  readDashboard: () =>
    apiRequest<DashboardData>({
      method: "GET",
      url: "/api/v1/dashboard/",
    }),

  readCategories: (params?: PaginationParams) =>
    apiRequest<PagedResponse<Category>>({
      method: "GET",
      url: "/api/v1/categories/",
      params: { page: 1, page_size: 10, ...params },
    }),

  createCategory: (data: {
    name: string
    color: string
    parent_id?: string | null
  }) =>
    apiRequest<Category>({
      method: "POST",
      url: "/api/v1/categories/",
      data,
    }),

  updateCategory: (
    categoryId: string,
    data: {
      name?: string
      color?: string
      parent_id?: string | null
    },
  ) =>
    apiRequest<Category>({
      method: "PUT",
      url: `/api/v1/categories/${categoryId}`,
      data,
    }),

  deleteCategory: (categoryId: string) =>
    apiRequest<MessageResponse>({
      method: "DELETE",
      url: `/api/v1/categories/${categoryId}`,
    }),

  readBudgets: (params?: PaginationParams) =>
    apiRequest<PagedResponse<Budget>>({
      method: "GET",
      url: "/api/v1/budgets/",
      params: { page: 1, page_size: 10, ...params },
    }),

  readUsers: (params?: PaginationParams) =>
    apiRequest<PagedResponse<UserPublic>>({
      method: "GET",
      url: "/api/v1/users/",
      params: { page: 1, page_size: 10, ...params },
    }),

  readHandlerUsers: (params?: PaginationParams) =>
    apiRequest<PagedResponse<HandlerUserOption>>({
      method: "GET",
      url: "/api/v1/users/handler-options",
      params: { page: 1, page_size: 200, ...params },
    }),

  createBudget: (data: {
    name: string
    year: number
    period: BudgetPeriod
    amount: number
  }) =>
    apiRequest<Budget>({
      method: "POST",
      url: "/api/v1/budgets/",
      data,
    }),

  updateBudget: (
    budgetId: string,
    data: {
      name?: string
      year?: number
      period?: BudgetPeriod
      amount?: number
    },
  ) =>
    apiRequest<Budget>({
      method: "PUT",
      url: `/api/v1/budgets/${budgetId}`,
      data,
    }),

  deleteBudget: (budgetId: string) =>
    apiRequest<MessageResponse>({
      method: "DELETE",
      url: `/api/v1/budgets/${budgetId}`,
    }),

  readTransactions: (params?: {
    page?: number
    page_size?: number
    start_date?: string
    end_date?: string
    transaction_type?: TransactionType
    category_id?: string
    entry_status?: EntryStatus
    handler_user_id?: string
  }) =>
    apiRequest<PagedResponse<Transaction>>({
      method: "GET",
      url: "/api/v1/transactions/",
      params: { page: 1, page_size: 10, ...params },
    }),

  createTransaction: (data: {
    category_id: string
    transaction_type: TransactionType
    budget_id?: string | null
    summary?: string | null
    detail?: TransactionDetail | null
    entry_status: EntryStatus
    handler_user_id?: string | null
    transaction_date: string
    amount: number
  }) =>
    apiRequest<Transaction>({
      method: "POST",
      url: "/api/v1/transactions/",
      data,
    }),

  updateTransaction: (
    transactionId: string,
    data: {
      category_id?: string
      transaction_type?: TransactionType
      budget_id?: string | null
      summary?: string | null
      detail?: TransactionDetail | null
      entry_status?: EntryStatus
      handler_user_id?: string | null
      transaction_date?: string
      amount?: number
    },
  ) =>
    apiRequest<Transaction>({
      method: "PUT",
      url: `/api/v1/transactions/${transactionId}`,
      data,
    }),

  deleteTransaction: (transactionId: string) =>
    apiRequest<MessageResponse>({
      method: "DELETE",
      url: `/api/v1/transactions/${transactionId}`,
    }),

  batchEnterTransactions: (ids: string[]) =>
    apiRequest<{ updated_ids: string[] }>({
      method: "POST",
      url: "/api/v1/transactions/batch-enter",
      data: { ids },
    }),

  readApiTokens: (params?: PaginationParams) =>
    apiRequest<PagedResponse<ApiTokenRecord>>({
      method: "GET",
      url: "/api/v1/system/api-tokens/",
      params: { page: 1, page_size: 10, ...params },
    }),

  createApiToken: (data: {
    name: string
    expires_at?: string | null
    generate_secret: boolean
  }) =>
    apiRequest<ApiTokenSecret>({
      method: "POST",
      url: "/api/v1/system/api-tokens/",
      data,
    }),

  disableApiToken: (tokenId: string) =>
    apiRequest<MessageResponse>({
      method: "POST",
      url: `/api/v1/system/api-tokens/${tokenId}/disable`,
    }),

  deleteApiToken: (tokenId: string) =>
    apiRequest<MessageResponse>({
      method: "DELETE",
      url: `/api/v1/system/api-tokens/${tokenId}`,
    }),

  setupMyMfa: () =>
    apiRequest<MfaSetupPayload>({
      method: "POST",
      url: "/api/v1/users/me/mfa/setup",
    }),

  enableMyMfa: (data: { secret: string; code: string }) =>
    apiRequest<MessageResponse>({
      method: "POST",
      url: "/api/v1/users/me/mfa/enable",
      data,
    }),

  resetMyMfa: () =>
    apiRequest<MessageResponse>({
      method: "POST",
      url: "/api/v1/users/me/mfa/reset",
    }),

  disableMyMfa: () =>
    apiRequest<MessageResponse>({
      method: "POST",
      url: "/api/v1/users/me/mfa/disable",
    }),

  resetUserMfa: (userId: string) =>
    apiRequest<MessageResponse>({
      method: "POST",
      url: `/api/v1/users/${userId}/reset-mfa`,
    }),

  readDataJobs: (params?: PaginationParams) =>
    apiRequest<PagedResponse<DataJobRecord>>({
      method: "GET",
      url: "/api/v1/system/data-jobs/",
      params: { page: 1, page_size: 10, ...params },
    }),

  createExportJob: () =>
    apiRequest<DataJobRecord>({
      method: "POST",
      url: "/api/v1/system/data-jobs/export",
    }),

  createImportJob: async (file: File) => {
    const formData = new FormData()
    formData.append("file", file)
    return apiRequest<DataJobRecord>({
      method: "POST",
      url: "/api/v1/system/data-jobs/import",
      data: formData,
    })
  },

  downloadDataJobTemplate: () =>
    downloadRequest({
      method: "GET",
      url: "/api/v1/system/data-jobs/template",
    }),

  downloadDataJobResult: (jobId: string) =>
    downloadRequest({
      method: "GET",
      url: `/api/v1/system/data-jobs/${jobId}/result`,
    }),

  downloadDataJobErrors: (jobId: string) =>
    downloadRequest({
      method: "GET",
      url: `/api/v1/system/data-jobs/${jobId}/errors`,
    }),
}
