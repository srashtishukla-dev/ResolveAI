export type Source = {
  document: string
  page: number | null
  similarity: number | null
}

export type AnswerResponse = {
  conversation_id: number
  question: string
  answer: string
  sources: Source[]
  has_context: boolean
}

export type ChatMessage = {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export type Conversation = {
  id: number
  title: string
  created_at: string
  updated_at: string
  messages: ChatMessage[]
}

export type KnowledgeDocument = {
  id: number
  title: string
  original_filename: string
  file_type: string
  file_size: number
  status: 'PENDING' | 'PROCESSING' | 'PROCESSED' | 'FAILED'
  uploaded_by: number
  created_at: string
  updated_at: string
}

export type TokenSet = {
  access: string
  refresh: string
}

export type CurrentUser = {
  id: number
  username: string
  is_staff: boolean
}

export type TicketCategory = 'TECHNICAL' | 'BILLING' | 'ACCOUNT' | 'GENERAL'
export type TicketPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT'
export type TicketStatus = 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'CLOSED'

export type Ticket = {
  id: number
  title: string
  description: string
  category: TicketCategory
  priority: TicketPriority
  status: TicketStatus
  created_by: number
  assigned_to: number | null
  created_at: string
  updated_at: string
}

export type TicketCreationPayload = {
  title: string
  description: string
  category: TicketCategory
  priority: TicketPriority
}

export type TicketUpdatePayload = Partial<Pick<
  Ticket,
  'title' | 'description' | 'category' | 'priority' | 'status' | 'assigned_to'
>>

export type TicketListResponse = {
  count: number
  next: string | null
  previous: string | null
  results: Ticket[]
}

type ApiErrorPayload = {
  detail?: string
  [key: string]: unknown
}

export class ApiError extends Error {
  readonly status: number
  readonly details: Record<string, string[]>

  constructor(status: number, message: string, details: Record<string, string[]> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || ''
).replace(/\/$/, '')
const TOKEN_STORAGE_KEY = 'resolveai_tokens'

export function getStoredTokens(): TokenSet | null {
  const stored = localStorage.getItem(TOKEN_STORAGE_KEY)
  if (!stored) {
    return null
  }

  try {
    const tokens = JSON.parse(stored) as Partial<TokenSet>
    if (typeof tokens.access === 'string' && typeof tokens.refresh === 'string') {
      return { access: tokens.access, refresh: tokens.refresh }
    }
  } catch {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
  }
  return null
}

function storeTokens(tokens: TokenSet) {
  localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(tokens))
}

export function clearStoredTokens() {
  localStorage.removeItem(TOKEN_STORAGE_KEY)
}

async function readErrorMessage(response: Response): Promise<{ message: string; details: Record<string, string[]> }> {
  try {
    const payload = (await response.json()) as ApiErrorPayload
    const details: Record<string, string[]> = {}
    for (const [field, value] of Object.entries(payload)) {
      if (field === 'detail' || value === undefined) {
        continue
      }
      const messages = Array.isArray(value) ? value : [value]
      details[field] = messages.flatMap((item) => (
        typeof item === 'string'
          ? [item]
          : item && typeof item === 'object'
            ? Object.values(item).flatMap((nested) => (
              Array.isArray(nested)
                ? nested.filter((message): message is string => typeof message === 'string')
                : typeof nested === 'string' ? [nested] : []
            ))
            : []
      ))
    }
    const firstFieldError = Object.values(details)[0]?.[0]
    return {
      message: typeof payload.detail === 'string'
        ? payload.detail
        : firstFieldError ?? 'The request could not be completed.',
      details,
    }
  } catch {
    return { message: 'The request could not be completed.', details: {} }
  }
}

async function refreshAccessToken(refresh: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/token/refresh/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  })

  if (!response.ok) {
    clearStoredTokens()
    throw new ApiError(401, 'Your session has expired. Please sign in again.')
  }

  const payload = (await response.json()) as { access?: string }
  if (!payload.access) {
    clearStoredTokens()
    throw new ApiError(401, 'Your session has expired. Please sign in again.')
  }

  const tokens = getStoredTokens()
  if (tokens) {
    storeTokens({ ...tokens, access: payload.access })
  }
  return payload.access
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  retryOnUnauthorized = true,
): Promise<T> {
  const tokens = getStoredTokens()
  const headers = new Headers(init.headers)
  if (!(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (tokens?.access) {
    headers.set('Authorization', `Bearer ${tokens.access}`)
  }

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers })
  } catch {
    throw new ApiError(
      0,
      `Unable to connect to the ResolveAI backend at ${API_BASE_URL}. `
        + 'Confirm the Django server is running and CORS allows this frontend origin.',
    )
  }

  if (response.status === 401 && tokens && retryOnUnauthorized) {
    const access = await refreshAccessToken(tokens.refresh)
    return request<T>(
      path,
      {
        ...init,
        headers: { ...Object.fromEntries(headers), Authorization: `Bearer ${access}` },
      },
      false,
    )
  }

  if (!response.ok) {
    const error = await readErrorMessage(response)
    const statusMessage = {
      400: 'The submitted information is invalid.',
      401: 'Your session is invalid or has expired. Please sign in again.',
      403: 'You do not have permission to perform this action.',
      404: 'The requested ResolveAI endpoint was not found.',
      500: 'ResolveAI encountered a server error. Please try again later.',
    }[response.status]
    throw new ApiError(
      response.status,
      error.message === 'The request could not be completed.'
        ? statusMessage ?? error.message
        : error.message,
      error.details,
    )
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export async function login(username: string, password: string): Promise<TokenSet> {
  const tokens = await request<TokenSet>('/api/token/', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  }, false)
  storeTokens(tokens)
  return tokens
}

export function getCurrentUser() {
  return request<CurrentUser>('/api/auth/me/')
}

export type RegistrationPayload = {
  name: string
  email: string
  username: string
  password: string
  password_confirmation: string
}

export async function registerCustomer(payload: RegistrationPayload) {
  return request<{ detail: string; username: string }>('/api/auth/register/', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, false)
}

export function listConversations() {
  return request<Conversation[]>('/api/ai/conversations/')
}

export function getConversation(conversationId: number) {
  return request<Conversation>(`/api/ai/conversations/${conversationId}/`)
}

export function createConversation(title?: string) {
  return request<Conversation>('/api/ai/conversations/', {
    method: 'POST',
    body: JSON.stringify(title ? { title } : {}),
  })
}

export function deleteConversation(conversationId: number) {
  return request<void>(`/api/ai/conversations/${conversationId}/`, {
    method: 'DELETE',
  })
}

export function listKnowledgeDocuments() {
  return request<KnowledgeDocument[]>('/api/knowledge-base/documents/')
}

export function uploadKnowledgeDocument(title: string, file: File) {
  const body = new FormData()
  body.append('title', title)
  body.append('file', file)
  return request<KnowledgeDocument>('/api/knowledge-base/documents/', {
    method: 'POST',
    body,
  })
}

export function deleteKnowledgeDocument(documentId: number) {
  return request<void>(`/api/knowledge-base/documents/${documentId}/`, {
    method: 'DELETE',
  })
}

export type TicketFilters = {
  status?: TicketStatus
  priority?: TicketPriority
  category?: TicketCategory
}

export async function listTickets(filters: TicketFilters = {}) {
  const searchParams = new URLSearchParams()
  for (const [field, value] of Object.entries(filters)) {
    if (value) {
      searchParams.set(field, value)
    }
  }
  const query = searchParams.toString()
  const response = await request<TicketListResponse | Ticket[]>(`/api/tickets/${query ? `?${query}` : ''}`)
  return Array.isArray(response) ? response : response.results
}

export function createTicket(payload: TicketCreationPayload) {
  return request<Ticket>('/api/tickets/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateTicket(ticketId: number, payload: TicketUpdatePayload) {
  return request<Ticket>(`/api/tickets/${ticketId}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteTicket(ticketId: number) {
  return request<void>(`/api/tickets/${ticketId}/`, {
    method: 'DELETE',
  })
}

export function askAssistant(question: string, conversationId?: number) {
  const body: { question: string; conversation_id?: number } = { question }
  if (conversationId !== undefined) {
    body.conversation_id = conversationId
  }
  

  return request<AnswerResponse>('/api/ai/answer/', {
    method: 'POST',
    body: JSON.stringify(body),
  })
  
}
