import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import {
  ApiError,
  askAssistant,
  clearStoredTokens,
  createTicket,
  deleteConversation as deleteConversationRequest,
  renameConversation,
  deleteTicket,
  getConversation,
  getCurrentUser,
  getStoredTokens,
  login,
  listTickets,
  listKnowledgeDocuments,
  listConversations,
  registerCustomer,
  updateTicket,
  uploadKnowledgeDocument,
} from './api'
import type {
  AnswerResponse,
  Conversation,
  CurrentUser,
  KnowledgeDocument,
  RegistrationPayload,
  Source,
  Ticket,
  TicketCategory,
  TicketPriority,
  TicketStatus,
  TokenSet,
} from './api'

type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  createdAt?: string
  response?: AnswerResponse
}

type StaffPage = 'assistant' | 'knowledge-base' | 'tickets'

const ticketCategories: { value: TicketCategory; label: string }[] = [
  { value: 'TECHNICAL', label: 'Technical' },
  { value: 'BILLING', label: 'Billing' },
  { value: 'ACCOUNT', label: 'Account' },
  { value: 'GENERAL', label: 'General' },
]

const ticketPriorities: { value: TicketPriority; label: string }[] = [
  { value: 'LOW', label: 'Low' },
  { value: 'MEDIUM', label: 'Medium' },
  { value: 'HIGH', label: 'High' },
  { value: 'URGENT', label: 'Urgent' },
]

const ticketStatuses: { value: TicketStatus; label: string }[] = [
  { value: 'OPEN', label: 'Open' },
  { value: 'IN_PROGRESS', label: 'In progress' },
  { value: 'RESOLVED', label: 'Resolved' },
  { value: 'CLOSED', label: 'Closed' },
]

function formatTicketDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function ticketStatusClass(status: TicketStatus) {
  return {
    OPEN: 'bg-blue-50 text-blue-700',
    IN_PROGRESS: 'bg-amber-50 text-amber-700',
    RESOLVED: 'bg-emerald-50 text-emerald-700',
    CLOSED: 'bg-slate-100 text-slate-600',
  }[status]
}

function ticketPriorityClass(priority: TicketPriority) {
  return {
    LOW: 'text-slate-500',
    MEDIUM: 'text-blue-600',
    HIGH: 'text-orange-600',
    URGENT: 'text-red-600',
  }[priority]
}

const exampleQuestions = [
  'How do I reset my password?',
  'What is the refund policy?',
  'How can I update my billing details?',
]

function Icon({
  name,
  size = 20,
}: {
  name: 'sparkles' | 'message' | 'book' | 'ticket' | 'plus' | 'send' | 'logout' | 'search'
  size?: number
}) {
  const paths = {
    sparkles: (
      <>
        <path d="m12 3-1.2 4.8L6 9l4.8 1.2L12 15l1.2-4.8L18 9l-4.8-1.2L12 3Z" />
        <path d="m19 15-.6 2.4L16 18l2.4.6L19 21l.6-2.4L22 18l-2.4-.6L19 15ZM5 3l.5 2L7 5.5 5.5 6 5 8l-.5-2L3 5.5 4.5 5 5 3Z" />
      </>
    ),
    message: <path d="M20 11.5a7.5 7.5 0 0 1-8 7.5 8.3 8.3 0 0 1-3-.6L4 20l1.6-4A7.2 7.2 0 0 1 4.5 12 7.5 7.5 0 0 1 12 4.5a7.5 7.5 0 0 1 8 7Z" />,
    book: <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5v-15ZM4 20.5A2.5 2.5 0 0 1 6.5 18H20M8 7h8M8 10h6" />,
    ticket: <path d="M20 13a2 2 0 0 0 0-4V6H4v3a2 2 0 0 0 0 4v3h16v-3ZM12 6v2M12 16v2M12 10v2" />,
    plus: <path d="M12 5v14M5 12h14" />,
    send: <path d="m21 3-7.5 18-3.5-7-7-3.5L21 3ZM10 14l5-5" />,
    logout: <path d="M10 17l5-5-5-5M15 12H3M21 19V5a2 2 0 0 0-2-2h-4" />,
    search: <path d="m20 20-4.2-4.2M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0Z" />,
  }

  return (
    <svg
      aria-hidden="true"
      fill="none"
      height={size}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
      width={size}
    >
      {paths[name]}
    </svg>
  )
}

function Logo() {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-lg shadow-indigo-200">
        <Icon name="sparkles" size={19} />
      </div>
      <span className="text-lg font-bold tracking-tight text-slate-900">ResolveAI</span>
    </div>
  )
}

function LoginScreen({
  onCreateAccount,
  onLogin,
  successMessage,
}: {
  onCreateAccount: () => void
  onLogin: (tokens: TokenSet) => void
  successMessage: string
}) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setIsLoading(true)
    try {
      const tokens = await login(username.trim(), password)
      onLogin(tokens)
    } catch (caughtError) {
      if (caughtError instanceof ApiError && (caughtError.status === 400 || caughtError.status === 401)) {
        setError('Enter a valid username and password.')
      } else {
        setError(caughtError instanceof ApiError ? caughtError.message : 'Sign in failed. Please try again.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-5 py-10">
      <div className="w-full max-w-md">
        <div className="mb-10 flex justify-center">
          <Logo />
        </div>
        <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-xl shadow-slate-200/60 sm:p-10">
          <div className="mb-8">
            <p className="mb-2 text-sm font-semibold text-indigo-600">Welcome back</p>
            <h1 className="text-2xl font-bold tracking-tight text-slate-950">Sign in to your workspace</h1>
            <p className="mt-2 text-sm leading-6 text-slate-500">Access your AI support assistant and knowledge base.</p>
          </div>
          {successMessage && <p className="mb-5 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{successMessage}</p>}
          <form className="space-y-5" onSubmit={handleSubmit}>
            <label className="block text-sm font-medium text-slate-700">
              Username
              <input
                autoComplete="username"
                className="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-100"
                onChange={(event) => setUsername(event.target.value)}
                required
                value={username}
              />
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Password
              <input
                autoComplete="current-password"
                className="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-100"
                onChange={(event) => setPassword(event.target.value)}
                required
                type="password"
                value={password}
              />
            </label>
            {error && <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
            <button
              className="flex w-full items-center justify-center rounded-xl bg-indigo-600 px-4 py-3.5 font-semibold text-white shadow-lg shadow-indigo-200 transition hover:bg-indigo-700 focus:outline-none focus:ring-4 focus:ring-indigo-200 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isLoading}
              type="submit"
            >
              {isLoading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
          <div className="mt-6 space-y-3 text-center text-xs leading-5">
            <p className="text-slate-400">Sign in with your ResolveAI account.</p>
            <button className="font-semibold text-indigo-600 hover:text-indigo-700 hover:underline" onClick={onCreateAccount} type="button">
              Create a customer account
            </button>
          </div>
        </section>
      </div>
    </main>
  )
}

function RegistrationScreen({ onBackToLogin }: { onBackToLogin: (registrationCompleted?: boolean) => void }) {
  const [form, setForm] = useState<RegistrationPayload>({
    name: '',
    email: '',
    username: '',
    password: '',
    password_confirmation: '',
  })
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [generalError, setGeneralError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isComplete, setIsComplete] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmation, setShowConfirmation] = useState(false)

  function updateField(field: keyof RegistrationPayload, value: string) {
    setForm((current) => ({ ...current, [field]: value }))
    setFieldErrors((current) => ({ ...current, [field]: '' }))
    setGeneralError('')
  }

  function validateForm() {
    const errors: Record<string, string> = {}
    if (!form.name.trim()) errors.name = 'Enter your name.'
    if (!form.email.trim()) errors.email = 'Enter your email address.'
    if (!form.username.trim()) errors.username = 'Choose a username.'
    if (form.password.length < 8) errors.password = 'Password must be at least 8 characters.'
    if (form.password !== form.password_confirmation) errors.password_confirmation = 'Passwords do not match.'
    setFieldErrors(errors)
    return Object.keys(errors).length === 0
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!validateForm()) return

    setIsLoading(true)
    setGeneralError('')
    try {
      await registerCustomer({
        name: form.name.trim(),
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
        password_confirmation: form.password_confirmation,
      })
      setIsComplete(true)
    } catch (caughtError) {
      if (caughtError instanceof ApiError) {
        const backendErrors = Object.fromEntries(
          Object.entries(caughtError.details).map(([field, messages]) => [field, messages[0]]),
        )
        setFieldErrors(backendErrors)
        setGeneralError(caughtError.details.detail?.[0] ?? (Object.keys(backendErrors).length ? '' : caughtError.message))
      } else {
        setGeneralError('Unable to create your account. Please try again.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  if (isComplete) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-5 py-10">
        <section className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-xl shadow-slate-200/60 sm:p-10">
          <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">✓</div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-950">Account created</h1>
          <p className="mt-3 text-sm leading-6 text-slate-500">Your customer account is ready. Sign in to continue to ResolveAI.</p>
          <button className="mt-8 w-full rounded-xl bg-indigo-600 px-4 py-3.5 font-semibold text-white shadow-lg shadow-indigo-200 transition hover:bg-indigo-700 focus:outline-none focus:ring-4 focus:ring-indigo-200" onClick={() => onBackToLogin(true)} type="button">
            Go to sign in
          </button>
        </section>
      </main>
    )
  }

  const inputClass = (field: string) => `mt-2 w-full rounded-xl border bg-slate-50 px-4 py-3 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-100 ${fieldErrors[field] ? 'border-red-300' : 'border-slate-200'}`

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-5 py-10">
      <div className="w-full max-w-md">
        <div className="mb-10 flex justify-center"><Logo /></div>
        <section className="rounded-3xl border border-slate-200 bg-white p-8 shadow-xl shadow-slate-200/60 sm:p-10">
          <div className="mb-8">
            <p className="mb-2 text-sm font-semibold text-indigo-600">Get started</p>
            <h1 className="text-2xl font-bold tracking-tight text-slate-950">Create your account</h1>
            <p className="mt-2 text-sm leading-6 text-slate-500">Create a customer account to access ResolveAI support.</p>
          </div>
          <form className="space-y-4" onSubmit={(event) => void handleSubmit(event)}>
            <label className="block text-sm font-medium text-slate-700">
              Name
              <input autoComplete="name" className={inputClass('name')} onChange={(event) => updateField('name', event.target.value)} value={form.name} />
              {fieldErrors.name && <span className="mt-1 block text-xs text-red-600">{fieldErrors.name}</span>}
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Email
              <input autoComplete="email" className={inputClass('email')} onChange={(event) => updateField('email', event.target.value)} type="email" value={form.email} />
              {fieldErrors.email && <span className="mt-1 block text-xs text-red-600">{fieldErrors.email}</span>}
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Username
              <input autoComplete="username" className={inputClass('username')} onChange={(event) => updateField('username', event.target.value)} value={form.username} />
              {fieldErrors.username && <span className="mt-1 block text-xs text-red-600">{fieldErrors.username}</span>}
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Password
              <div className="relative">
                <input autoComplete="new-password" className={`${inputClass('password')} pr-16`} onChange={(event) => updateField('password', event.target.value)} type={showPassword ? 'text' : 'password'} value={form.password} />
                <button aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword} className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-slate-500 hover:text-indigo-600" onClick={() => setShowPassword((current) => !current)} type="button">
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
              {fieldErrors.password && <span className="mt-1 block text-xs text-red-600">{fieldErrors.password}</span>}
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Confirm password
              <div className="relative">
                <input autoComplete="new-password" className={`${inputClass('password_confirmation')} pr-16`} onChange={(event) => updateField('password_confirmation', event.target.value)} type={showConfirmation ? 'text' : 'password'} value={form.password_confirmation} />
                <button aria-label={showConfirmation ? 'Hide password confirmation' : 'Show password confirmation'} aria-pressed={showConfirmation} className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-slate-500 hover:text-indigo-600" onClick={() => setShowConfirmation((current) => !current)} type="button">
                  {showConfirmation ? 'Hide' : 'Show'}
                </button>
              </div>
              {fieldErrors.password_confirmation && <span className="mt-1 block text-xs text-red-600">{fieldErrors.password_confirmation}</span>}
            </label>
            {generalError && <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{generalError}</p>}
            <button className="flex w-full items-center justify-center rounded-xl bg-indigo-600 px-4 py-3.5 font-semibold text-white shadow-lg shadow-indigo-200 transition hover:bg-indigo-700 focus:outline-none focus:ring-4 focus:ring-indigo-200 disabled:cursor-not-allowed disabled:opacity-60" disabled={isLoading} type="submit">
              {isLoading ? 'Creating account…' : 'Create account'}
            </button>
          </form>
          <p className="mt-6 text-center text-sm text-slate-500">
            Already have an account?{' '}
            <button className="font-semibold text-indigo-600 hover:text-indigo-700 hover:underline" onClick={() => onBackToLogin()} type="button">Sign in</button>
          </p>
        </section>
      </div>
    </main>
  )
}

function SourceList({ sources }: { sources: Source[] }) {
  if (sources.length === 0) {
    return null
  }

  return (
    <div className="mt-5 border-t border-slate-100 pt-4">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Sources</p>
      <div className="flex flex-wrap gap-2">
        {sources.map((source, index) => (
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600" key={`${source.document}-${source.page}-${index}`}>
            <Icon name="book" size={14} />
            <span className="max-w-48 truncate font-medium">{source.document}</span>
            {source.page !== null && <span className="text-slate-400">p. {source.page}</span>}
            {source.similarity !== null && <span className="text-indigo-500">{Math.round(source.similarity * 100)}%</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

function CustomerDashboard({
  onLogout,
  user,
}: {
  onLogout: () => void
  user: CurrentUser
}) {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [form, setForm] = useState({
    title: '',
    description: '',
    category: 'GENERAL' as TicketCategory,
    priority: 'MEDIUM' as TicketPriority,
  })
  const isMountedRef = useRef(true)
  const ticketRequestRef = useRef(0)

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  const loadTickets = useCallback(async () => {
    const requestId = ticketRequestRef.current + 1
    ticketRequestRef.current = requestId
    try {
      const loadedTickets = await listTickets()
      if (!isMountedRef.current || requestId !== ticketRequestRef.current) return
      setTickets(loadedTickets)
    } catch (caughtError) {
      if (!isMountedRef.current || requestId !== ticketRequestRef.current) return
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        onLogout()
        return
      }
      setError(caughtError instanceof ApiError ? caughtError.message : 'Unable to load your tickets.')
    } finally {
      if (isMountedRef.current && requestId === ticketRequestRef.current) {
        setIsLoading(false)
      }
    }
  }, [onLogout])

  useEffect(() => {
    let cancelled = false
    const requestId = ticketRequestRef.current + 1
    ticketRequestRef.current = requestId

    listTickets()
      .then((loadedTickets) => {
        if (!cancelled && isMountedRef.current && requestId === ticketRequestRef.current) {
          setTickets(loadedTickets)
        }
      })
      .catch((caughtError: unknown) => {
        if (cancelled || !isMountedRef.current || requestId !== ticketRequestRef.current) return
        if (caughtError instanceof ApiError && caughtError.status === 401) {
          onLogout()
          return
        }
        setError(caughtError instanceof ApiError ? caughtError.message : 'Unable to load your tickets.')
      })
      .finally(() => {
        if (!cancelled && isMountedRef.current && requestId === ticketRequestRef.current) {
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [onLogout])

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!form.title.trim() || !form.description.trim() || isCreating) return

    setIsCreating(true)
    setError('')
    setSuccess('')
    try {
      const ticket = await createTicket({
        ...form,
        title: form.title.trim(),
        description: form.description.trim(),
      })
      setTickets((current) => [ticket, ...current])
      setForm({ title: '', description: '', category: 'GENERAL', priority: 'MEDIUM' })
      setSuccess('Your ticket was created successfully.')
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        onLogout()
        return
      }
      setError(caughtError instanceof ApiError ? caughtError.message : 'Unable to create your ticket.')
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-4 sm:px-8">
        <Logo />
        <button
          className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-slate-500 transition hover:bg-slate-50 hover:text-slate-900"
          onClick={onLogout}
          type="button"
        >
          <Icon name="logout" size={18} /> Sign out
        </button>
      </header>
      <section className="mx-auto max-w-6xl space-y-6 px-5 py-8 sm:px-8">
        <div>
          <p className="text-sm font-semibold text-indigo-600">Customer workspace</p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight text-slate-950">Welcome, {user.username}</h1>
          <p className="mt-2 text-sm text-slate-500">Create a support request and follow its progress here.</p>
        </div>
        {error && <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
        {success && <p className="rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{success}</p>}
        <form className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6" onSubmit={(event) => void handleCreate(event)}>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-100 text-indigo-600"><Icon name="plus" size={20} /></div>
            <div><h2 className="font-semibold text-slate-950">Create a ticket</h2><p className="text-xs text-slate-500">Tell us how we can help.</p></div>
          </div>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-medium text-slate-700 sm:col-span-2">Title
              <input className="mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100" onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} required value={form.title} />
            </label>
            <label className="text-sm font-medium text-slate-700 sm:col-span-2">Description
              <textarea className="mt-1.5 w-full resize-y rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100" onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} required rows={4} value={form.description} />
            </label>
            <label className="text-sm font-medium text-slate-700">Category
              <select className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100" onChange={(event) => setForm((current) => ({ ...current, category: event.target.value as TicketCategory }))} value={form.category}>
                {ticketCategories.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <label className="text-sm font-medium text-slate-700">Priority
              <select className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100" onChange={(event) => setForm((current) => ({ ...current, priority: event.target.value as TicketPriority }))} value={form.priority}>
                {ticketPriorities.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
          </div>
          <button className="mt-5 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60" disabled={isCreating} type="submit">{isCreating ? 'Creating…' : 'Submit ticket'}</button>
        </form>
        <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <div><h2 className="font-semibold text-slate-950">Your tickets</h2><p className="mt-1 text-xs text-slate-500">Only tickets created by your account are shown.</p></div>
            <button className="rounded-lg px-3 py-2 text-sm font-semibold text-indigo-600 hover:bg-indigo-50 disabled:opacity-50" disabled={isLoading} onClick={() => { setIsLoading(true); setError(''); void loadTickets() }} type="button">Refresh</button>
          </div>
          {isLoading ? <p className="px-5 py-8 text-sm text-slate-400">Loading your tickets…</p> : tickets.length === 0 ? (
            <div className="px-5 py-10 text-center"><Icon name="ticket" size={28} /><p className="mt-3 text-sm font-medium text-slate-700">No tickets yet</p><p className="mt-1 text-sm text-slate-500">Create a ticket above when you need support.</p></div>
          ) : (
            <div className="divide-y divide-slate-100">{tickets.map((ticket) => (
              <article className="px-5 py-5" key={ticket.id}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div><h3 className="font-semibold text-slate-900">{ticket.title}</h3><p className="mt-1 text-sm leading-6 text-slate-600">{ticket.description}</p></div>
                  <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${ticketStatusClass(ticket.status)}`}>{ticketStatuses.find((status) => status.value === ticket.status)?.label}</span>
                </div>
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500"><span>{ticketCategories.find((category) => category.value === ticket.category)?.label}</span><span className={`font-semibold ${ticketPriorityClass(ticket.priority)}`}>{ticketPriorities.find((priority) => priority.value === ticket.priority)?.label} priority</span><span>Created {formatTicketDate(ticket.created_at)}</span></div>
              </article>
            ))}</div>
          )}
        </section>
      </section>
    </main>
  )
}

function KnowledgeBasePage({
  onLogout,
  onNavigate,
}: {
  onLogout: () => void
  onNavigate: (page: StaffPage) => void
}) {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [title, setTitle] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)

  useEffect(() => {
    let cancelled = false
    listKnowledgeDocuments()
      .then((loadedDocuments) => {
        if (!cancelled) {
          setDocuments(loadedDocuments)
          setError('')
        }
      })
      .catch((caughtError: unknown) => {
        if (cancelled) {
          return
        }
        if (caughtError instanceof ApiError && caughtError.status === 401) {
          onLogout()
          return
        }
        setError(
          caughtError instanceof ApiError
            ? caughtError.message
            : 'Unable to load knowledge-base documents.',
        )
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [onLogout])

async function handleUpload(event: FormEvent<HTMLFormElement>) {
  event.preventDefault()
  const form = event.currentTarget

  if (!title.trim() || !file || isUploading) {
    return
  }

  setIsUploading(true)
  setError('')

  try {
    const document = await uploadKnowledgeDocument(title.trim(), file)

    setDocuments((current) => [document, ...current])
    setTitle('')
    setFile(null)
    form.reset()
  } catch (caughtError) {
    if (caughtError instanceof ApiError && caughtError.status === 401) {
      onLogout()
      return
    }

    setError(
      caughtError instanceof ApiError
        ? caughtError.message
        : caughtError instanceof Error
          ? caughtError.message
          : 'Unable to upload this document.',
    )
  } finally {
    setIsUploading(false)
  }
}

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="p-6"><Logo /></div>
        <nav aria-label="Main navigation" className="space-y-1 px-3">
          <a
            className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-500 transition hover:bg-slate-50 hover:text-slate-900"
            href="#assistant"
            onClick={(event) => {
              event.preventDefault()
              onNavigate('assistant')
            }}
          >
            <Icon name="message" size={18} /> AI Assistant
          </a>
          <a className="flex items-center gap-3 rounded-xl bg-indigo-50 px-3 py-2.5 text-sm font-semibold text-indigo-700" href="#knowledge-base">
            <Icon name="book" size={18} /> Knowledge base
          </a>
          <a
            className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-500 transition hover:bg-slate-50 hover:text-slate-900"
            href="#tickets"
            onClick={(event) => {
              event.preventDefault()
              onNavigate('tickets')
            }}
          >
            <Icon name="ticket" size={18} /> Tickets
          </a>
        </nav>
        <div className="mt-auto border-t border-slate-100 p-4">
          <button className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-500 transition hover:bg-slate-50 hover:text-slate-900" onClick={onLogout} type="button">
            <Icon name="logout" size={18} /> Sign out
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-4 sm:px-8">
          <div>
            <div className="md:hidden"><Logo /></div>
            <h1 className="hidden text-lg font-bold text-slate-950 md:block">Knowledge base</h1>
            <p className="hidden text-xs text-slate-500 md:block">Manage documents used by the AI Assistant</p>
          </div>
          <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" onClick={onLogout} type="button">
            <Icon name="logout" size={18} />
          </button>
        </header>
        <section className="mx-auto max-w-5xl space-y-6 px-5 py-8 sm:px-8">
          <form className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" onSubmit={(event) => void handleUpload(event)}>
            <h2 className="font-semibold text-slate-950">Upload a document</h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
              <label className="text-sm text-slate-600">
                Title
                <input className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100" onChange={(event) => setTitle(event.target.value)} required value={title} />
              </label>
              <label className="text-sm text-slate-600">
                File
                <input accept=".pdf,.txt" className="mt-1 block w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" onChange={(event) => setFile(event.target.files?.[0] ?? null)} required type="file" />
              </label>
              <button className="self-end rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60" disabled={isUploading || !file} type="submit">
                {isUploading ? 'Uploading…' : 'Upload'}
              </button>
            </div>
          </form>
          {error && <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-5 py-4">
              <h2 className="font-semibold text-slate-950">Documents</h2>
            </div>
            {isLoading ? (
              <p className="px-5 py-8 text-sm text-slate-400">Loading documents…</p>
            ) : documents.length === 0 ? (
              <p className="px-5 py-8 text-sm text-slate-500">No documents have been uploaded yet.</p>
            ) : (
              <div className="divide-y divide-slate-100">
                {documents.map((document) => (
                  <div className="flex items-center justify-between gap-4 px-5 py-4" key={document.id}>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-800">{document.title}</p>
                      <p className="mt-1 truncate text-xs text-slate-400">{document.original_filename}</p>
                    </div>
                    <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${document.status === 'PROCESSED' ? 'bg-emerald-50 text-emerald-700' : document.status === 'FAILED' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700'}`}>
                      {document.status.toLowerCase()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  )
}

function TicketsPage({
  onLogout,
  onNavigate,
  user,
}: {
  onLogout: () => void
  onNavigate: (page: StaffPage) => void
  user: CurrentUser
}) {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [statusFilter, setStatusFilter] = useState<TicketStatus | ''>('')
  const [priorityFilter, setPriorityFilter] = useState<TicketPriority | ''>('')
  const [categoryFilter, setCategoryFilter] = useState<TicketCategory | ''>('')
  const [isLoading, setIsLoading] = useState(true)
  const [actionId, setActionId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const isMountedRef = useRef(true)
  const ticketRequestRef = useRef(0)

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  const loadTickets = useCallback(async () => {
    const requestId = ticketRequestRef.current + 1
    ticketRequestRef.current = requestId
    try {
      const loadedTickets = await listTickets({
        status: statusFilter || undefined,
        priority: priorityFilter || undefined,
        category: categoryFilter || undefined,
      })
      if (!isMountedRef.current || requestId !== ticketRequestRef.current) return
      setTickets(loadedTickets)
    } catch (caughtError) {
      if (!isMountedRef.current || requestId !== ticketRequestRef.current) return
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        onLogout()
        return
      }
      setError(caughtError instanceof ApiError ? caughtError.message : 'Unable to load tickets.')
    } finally {
      if (isMountedRef.current && requestId === ticketRequestRef.current) {
        setIsLoading(false)
      }
    }
  }, [categoryFilter, onLogout, priorityFilter, statusFilter])

  useEffect(() => {
    let cancelled = false
    const requestId = ticketRequestRef.current + 1
    ticketRequestRef.current = requestId

    listTickets({
      status: statusFilter || undefined,
      priority: priorityFilter || undefined,
      category: categoryFilter || undefined,
    })
      .then((loadedTickets) => {
        if (!cancelled && isMountedRef.current && requestId === ticketRequestRef.current) {
          setTickets(loadedTickets)
        }
      })
      .catch((caughtError: unknown) => {
        if (cancelled || !isMountedRef.current || requestId !== ticketRequestRef.current) return
        if (caughtError instanceof ApiError && caughtError.status === 401) {
          onLogout()
          return
        }
        setError(caughtError instanceof ApiError ? caughtError.message : 'Unable to load tickets.')
      })
      .finally(() => {
        if (!cancelled && isMountedRef.current && requestId === ticketRequestRef.current) {
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [categoryFilter, onLogout, priorityFilter, statusFilter])

  async function changeTicket(ticketId: number, payload: Parameters<typeof updateTicket>[1]) {
    setActionId(ticketId)
    setError('')
    try {
      const updatedTicket = await updateTicket(ticketId, payload)
      setTickets((current) => current.map((ticket) => ticket.id === ticketId ? updatedTicket : ticket))
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        onLogout()
        return
      }
      setError(caughtError instanceof ApiError ? caughtError.message : 'Unable to update this ticket.')
    } finally {
      setActionId(null)
    }
  }

  async function removeTicket(ticket: Ticket) {
    if (!window.confirm(`Delete "${ticket.title}"?`)) return

    setActionId(ticket.id)
    setError('')
    try {
      await deleteTicket(ticket.id)
      setTickets((current) => current.filter((item) => item.id !== ticket.id))
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        onLogout()
        return
      }
      setError(caughtError instanceof ApiError ? caughtError.message : 'Unable to delete this ticket.')
    } finally {
      setActionId(null)
    }
  }

  const selectClass = 'rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100'

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="p-6"><Logo /></div>
        <nav aria-label="Main navigation" className="space-y-1 px-3">
          <a className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-500 transition hover:bg-slate-50 hover:text-slate-900" href="#assistant" onClick={(event) => { event.preventDefault(); onNavigate('assistant') }}><Icon name="message" size={18} /> AI Assistant</a>
          <a className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-500 transition hover:bg-slate-50 hover:text-slate-900" href="#knowledge-base" onClick={(event) => { event.preventDefault(); onNavigate('knowledge-base') }}><Icon name="book" size={18} /> Knowledge base</a>
          <a className="flex items-center gap-3 rounded-xl bg-indigo-50 px-3 py-2.5 text-sm font-semibold text-indigo-700" href="#tickets"><Icon name="ticket" size={18} /> Tickets</a>
        </nav>
        <div className="mt-auto border-t border-slate-100 p-4"><button className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-500 transition hover:bg-slate-50 hover:text-slate-900" onClick={onLogout} type="button"><Icon name="logout" size={18} /> Sign out</button></div>
      </aside>
      <main className="min-w-0 flex-1">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-4 sm:px-8">
          <div><div className="md:hidden"><Logo /></div><h1 className="hidden text-lg font-bold text-slate-950 md:block">Tickets</h1><p className="hidden text-xs text-slate-500 md:block">Manage customer support requests</p></div>
          <button aria-label="Sign out" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" onClick={onLogout} type="button"><Icon name="logout" size={18} /></button>
        </header>
        <section className="mx-auto max-w-6xl space-y-6 px-5 py-8 sm:px-8">
          <div><p className="text-sm font-semibold text-indigo-600">Support workspace</p><h2 className="mt-1 text-3xl font-bold tracking-tight text-slate-950">All tickets</h2><p className="mt-2 text-sm text-slate-500">Review, assign, and update customer requests.</p></div>
          {error && <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}
          <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:grid-cols-4">
            <label className="text-xs font-semibold text-slate-500">Status<select className={`${selectClass} mt-1 block w-full`} onChange={(event) => { setIsLoading(true); setError(''); setStatusFilter(event.target.value as TicketStatus | '') }} value={statusFilter}><option value="">All statuses</option>{ticketStatuses.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
            <label className="text-xs font-semibold text-slate-500">Priority<select className={`${selectClass} mt-1 block w-full`} onChange={(event) => { setIsLoading(true); setError(''); setPriorityFilter(event.target.value as TicketPriority | '') }} value={priorityFilter}><option value="">All priorities</option>{ticketPriorities.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
            <label className="text-xs font-semibold text-slate-500">Category<select className={`${selectClass} mt-1 block w-full`} onChange={(event) => { setIsLoading(true); setError(''); setCategoryFilter(event.target.value as TicketCategory | '') }} value={categoryFilter}><option value="">All categories</option>{ticketCategories.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
            <button className="self-end rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-semibold text-indigo-600 hover:bg-indigo-50 disabled:opacity-50" disabled={isLoading} onClick={() => { setIsLoading(true); setError(''); void loadTickets() }} type="button">Refresh tickets</button>
          </div>
          <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
            {isLoading ? <p className="px-5 py-10 text-sm text-slate-400">Loading tickets…</p> : tickets.length === 0 ? <p className="px-5 py-10 text-center text-sm text-slate-500">No tickets match the selected filters.</p> : (
              <div className="divide-y divide-slate-100">{tickets.map((ticket) => {
                const isBusy = actionId === ticket.id
                return <article className="p-5" key={ticket.id}>
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold text-slate-900">{ticket.title}</h3><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${ticketStatusClass(ticket.status)}`}>{ticketStatuses.find((status) => status.value === ticket.status)?.label}</span></div><p className="mt-2 text-sm leading-6 text-slate-600">{ticket.description}</p><p className="mt-3 text-xs text-slate-500">Ticket #{ticket.id} · {ticketCategories.find((category) => category.value === ticket.category)?.label} · Created {formatTicketDate(ticket.created_at)}{ticket.assigned_to ? ` · Assigned to user #${ticket.assigned_to}` : ' · Unassigned'}</p></div>
                    <div className="flex w-full flex-wrap gap-2 sm:w-auto sm:justify-end">
                      <select aria-label={`Update status for ${ticket.title}`} className={selectClass} disabled={isBusy} onChange={(event) => void changeTicket(ticket.id, { status: event.target.value as TicketStatus })} value={ticket.status}>{ticketStatuses.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
                      <select aria-label={`Update priority for ${ticket.title}`} className={`${selectClass} ${ticketPriorityClass(ticket.priority)}`} disabled={isBusy} onChange={(event) => void changeTicket(ticket.id, { priority: event.target.value as TicketPriority })} value={ticket.priority}>{ticketPriorities.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
                      <button className="rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-semibold text-indigo-600 hover:bg-indigo-50 disabled:opacity-50" disabled={isBusy} onClick={() => void changeTicket(ticket.id, { assigned_to: ticket.assigned_to === user.id ? null : user.id })} type="button">{ticket.assigned_to === user.id ? 'Unassign me' : 'Assign to me'}</button>
                      <button aria-label={`Delete ${ticket.title}`} className="rounded-xl border border-red-100 px-3 py-2.5 text-sm font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50" disabled={isBusy} onClick={() => void removeTicket(ticket)} type="button">Delete</button>
                    </div>
                  </div>
                </article>
              })}</div>
            )}
          </section>
        </section>
      </main>
    </div>
  )
}

function Sidebar({
  activeConversationId,
  conversations,
  conversationError,
  isLoadingConversations,
  isDeletingConversationId,
  onDeleteConversation,
  onRenameConversation,
  onNewChat,
  onSelectConversation,
  onNavigate,
  onLogout,
}: {
  activeConversationId: number | null
  conversations: Conversation[]
  conversationError: string
  isLoadingConversations: boolean
  isDeletingConversationId: number | null
  onDeleteConversation: (conversationId: number) => void
  onRenameConversation: (conversationId: number) => void
  onNewChat: () => void
  onSelectConversation: (conversationId: number) => void
  onNavigate: (page: StaffPage) => void
  onLogout: () => void
}) {
  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
      <div className="p-6">
        <Logo />
      </div>
      <div className="px-4">
        <button
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white shadow-md shadow-indigo-100 transition hover:bg-indigo-700 focus:outline-none focus:ring-4 focus:ring-indigo-100"
          onClick={onNewChat}
          type="button"
        >
          <Icon name="plus" size={17} /> New chat
        </button>
      </div>
      <nav aria-label="Main navigation" className="mt-8 space-y-1 px-3">
        <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">Workspace</p>
        <a
          className="flex items-center gap-3 rounded-xl bg-indigo-50 px-3 py-2.5 text-sm font-semibold text-indigo-700"
          href="#assistant"
          onClick={(event) => {
            event.preventDefault()
            onNavigate('assistant')
          }}
        >
          <Icon name="message" size={18} /> AI Assistant
        </a>
        <a
          className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-500 transition hover:bg-slate-50 hover:text-slate-900"
          href="#knowledge-base"
          onClick={(event) => {
            event.preventDefault()
            onNavigate('knowledge-base')
          }}
        >
          <Icon name="book" size={18} /> Knowledge base
        </a>
        <a
          className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-500 transition hover:bg-slate-50 hover:text-slate-900"
          href="#tickets"
          onClick={(event) => {
            event.preventDefault()
            onNavigate('tickets')
          }}
        >
          <Icon name="ticket" size={18} /> Tickets
        </a>
      </nav>
      <div className="mt-8 min-h-0 px-3">
        <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">Recent chats</p>
        <div className="max-h-64 space-y-1 overflow-y-auto">
          {isLoadingConversations && (
            <p className="px-3 py-2 text-xs text-slate-400">Loading conversations…</p>
          )}
          {!isLoadingConversations && conversationError && (
            <p className="px-3 py-2 text-xs leading-5 text-red-600">{conversationError}</p>
          )}
          {!isLoadingConversations && !conversationError && conversations.length === 0 && (
            <p className="px-3 py-2 text-xs leading-5 text-slate-400">No saved conversations yet.</p>
          )}
          {!isLoadingConversations && !conversationError && conversations.map((conversation) => (
            <div className={`group flex items-center gap-1 rounded-xl ${activeConversationId === conversation.id ? 'bg-indigo-50' : 'hover:bg-slate-50'}`} key={conversation.id}>
              <button
                className={`min-w-0 flex-1 truncate px-3 py-2 text-left text-xs font-medium ${activeConversationId === conversation.id ? 'text-indigo-700' : 'text-slate-600 hover:text-slate-900'}`}
                onClick={() => onSelectConversation(conversation.id)}
                type="button"
              >
                {conversation.title}
              </button>
              <button
                aria-label={`Rename ${conversation.title}`}
                className="rounded-lg px-2 py-1 text-slate-400 opacity-0 transition hover:bg-indigo-50 hover:text-indigo-600 group-hover:opacity-100 focus:opacity-100"
                onClick={() => onRenameConversation(conversation.id)}
                type="button"
              >
                ?
              </button>
              <button
                aria-label={`Delete ${conversation.title}`}
                className="mr-1 rounded-lg px-2 py-1 text-slate-400 opacity-0 transition hover:bg-red-50 hover:text-red-600 group-hover:opacity-100 focus:opacity-100 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={isDeletingConversationId === conversation.id}
                onClick={() => onDeleteConversation(conversation.id)}
                type="button"
              >
                {isDeletingConversationId === conversation.id ? '…' : '×'}
              </button>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-auto border-t border-slate-100 p-4">
        <button className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-500 transition hover:bg-slate-50 hover:text-slate-900" onClick={onLogout} type="button">
          <Icon name="logout" size={18} /> Sign out
        </button>
      </div>
    </aside>
  )
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-100 text-indigo-600">
          <Icon name="sparkles" size={16} />
        </div>
      )}
      <div className={`max-w-[min(680px,85%)] ${isUser ? 'items-end' : 'items-start'}`}>
        <div className={`rounded-2xl px-4 py-3 text-sm leading-7 ${isUser ? 'rounded-br-md bg-indigo-600 text-white' : 'rounded-bl-md border border-slate-200 bg-white text-slate-700 shadow-sm'}`}>
          <p className="whitespace-pre-wrap">{message.content}</p>
          {message.response && !message.response.has_context && (
            <p className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-400">No matching knowledge-base context was found.</p>
          )}
          {message.response && <SourceList sources={message.response.sources} />}
        </div>
        <p className={`mt-1.5 text-[11px] text-slate-400 ${isUser ? 'text-right' : ''}`}>{isUser ? 'You' : 'ResolveAI Assistant'}</p>
      </div>
    </div>
  )
}

function restoreConversationMessages(conversation: Conversation): Message[] {
  return [...conversation.messages]
    .sort((left, right) => {
      const createdAtDifference = Date.parse(left.created_at) - Date.parse(right.created_at)
      return createdAtDifference || left.id - right.id
    })
    .map((message) => ({
      id: String(message.id),
      role: message.role,
      content: message.content,
      createdAt: message.created_at,
    }))
}

function AssistantPage({
  onLogout,
  onNavigate,
}: {
  onLogout: () => void
  onNavigate: (page: StaffPage) => void
}) {
  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState('')
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null)
  const [isLoadingConversations, setIsLoadingConversations] = useState(true)
  const [isLoadingConversation, setIsLoadingConversation] = useState(false)
  const [conversationError, setConversationError] = useState('')
  const [isDeletingConversationId, setIsDeletingConversationId] = useState<number | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const conversationRequestRef = useRef(0)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isSending])

  useEffect(() => {
    let cancelled = false
    listConversations()
      .then((loadedConversations) => {
        if (!cancelled) {
          setConversations(loadedConversations)
          setConversationError('')
        }
      })
      .catch((caughtError: unknown) => {
        if (cancelled) {
          return
        }
        if (caughtError instanceof ApiError && caughtError.status === 401) {
          onLogout()
          return
        }
        setConversationError(
          caughtError instanceof ApiError
            ? caughtError.message
            : 'Unable to load saved conversations.',
        )
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingConversations(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [onLogout])

  async function refreshConversations() {
    try {
      const loadedConversations = await listConversations()
      setConversations(loadedConversations)
      setConversationError('')
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        onLogout()
        return
      }
      setConversationError(
        caughtError instanceof ApiError
          ? caughtError.message
          : 'Unable to refresh saved conversations.',
      )
    }
  }

  function startNewChat() {
    conversationRequestRef.current += 1
    setMessages([])
    setActiveConversationId(null)
    setQuestion('')
    setError('')
    setIsLoadingConversation(false)
    setIsSending(false)
  }

  async function selectConversation(conversationId: number) {
    const requestId = conversationRequestRef.current + 1
    conversationRequestRef.current = requestId
    setActiveConversationId(conversationId)
    setMessages([])
    setQuestion('')
    setError('')
    setIsLoadingConversation(true)
    setIsSending(false)

    try {
      const conversation = await getConversation(conversationId)
      if (requestId !== conversationRequestRef.current) {
        return
      }
      setActiveConversationId(conversation.id)
      setMessages(restoreConversationMessages(conversation))
    } catch (caughtError) {
      if (requestId !== conversationRequestRef.current) {
        return
      }
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        onLogout()
        return
      }
      setActiveConversationId(null)
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : 'Unable to load this conversation.',
      )
    } finally {
      if (requestId === conversationRequestRef.current) {
        setIsLoadingConversation(false)
      }
    }
  }

  async function renameSavedConversation(conversationId: number) {
    const conversation = conversations.find((item) => item.id === conversationId)
    if (!conversation) return

    const title = window.prompt('Enter a new conversation title:', conversation.title)
    if (title === null) return

    const trimmedTitle = title.trim()
    if (!trimmedTitle) {
      setConversationError('Conversation title cannot be empty.')
      return
    }

    try {
      const updated = await renameConversation(conversationId, trimmedTitle)
      setConversations((current) =>
        current.map((item) =>
          item.id === conversationId ? { ...item, title: updated.title } : item
        )
      )
      setConversationError('')
    } catch (caughtError) {
      setConversationError(
        caughtError instanceof ApiError
          ? caughtError.message
          : 'Unable to rename this conversation.'
      )
    }
  }

  async function removeConversation(conversationId: number) {
    const conversation = conversations.find((item) => item.id === conversationId)
    if (!conversation || !window.confirm(`Delete "${conversation.title}"?`)) {
      return
    }

    setIsDeletingConversationId(conversationId)
    try {
      await deleteConversationRequest(conversationId)
      setConversations((current) => current.filter((item) => item.id !== conversationId))
      if (activeConversationId === conversationId) {
        startNewChat()
      }
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        onLogout()
        return
      }
      setConversationError(
        caughtError instanceof ApiError
          ? caughtError.message
          : 'Unable to delete this conversation.',
      )
    } finally {
      setIsDeletingConversationId(null)
    }
  }

  async function sendQuestion(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault()
    const trimmedQuestion = question.trim()
    if (!trimmedQuestion || isSending || isLoadingConversation) {
      return
    }

    setQuestion('')
    setError('')
    setIsSending(true)
    const requestId = conversationRequestRef.current
    const conversationId = activeConversationId ?? undefined
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmedQuestion,
      createdAt: new Date().toISOString(),
    }
    setMessages((current) => [...current, userMessage])

    try {
      const response = await askAssistant(trimmedQuestion, conversationId)
      if (requestId !== conversationRequestRef.current) {
        void refreshConversations()
        return
      }
      setActiveConversationId(response.conversation_id)
      setMessages((current) => [...current, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.answer,
        createdAt: new Date().toISOString(),
        response,
      }])
      void refreshConversations()
    } catch (caughtError) {
      if (requestId !== conversationRequestRef.current) {
        return
      }
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        onLogout()
      } else if (caughtError instanceof ApiError && caughtError.status === 403) {
        setError('Your account does not have permission to use the AI Assistant.')
      } else if (caughtError instanceof ApiError && caughtError.status === 400) {
        setError(caughtError.message || 'Please enter a valid question.')
      } else if (caughtError instanceof ApiError && caughtError.status === 503) {
        setError('The AI answer service is temporarily unavailable. Please try again later.')
      } else {
        setError(caughtError instanceof ApiError ? caughtError.message : 'Something went wrong. Please try again.')
      }
    } finally {
      if (requestId === conversationRequestRef.current) {
        setIsSending(false)
      }
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void sendQuestion()
    }
  }

  return (
    <div className="flex h-screen min-h-[600px] bg-slate-50 text-slate-900">
      <Sidebar
        activeConversationId={activeConversationId}
        conversations={conversations}
        conversationError={conversationError}
        isDeletingConversationId={isDeletingConversationId}
        isLoadingConversations={isLoadingConversations}
        onDeleteConversation={(conversationId) => void removeConversation(conversationId)}
        onRenameConversation={(conversationId) => void renameSavedConversation(conversationId)}
        onLogout={onLogout}
        onNavigate={onNavigate}
        onNewChat={startNewChat}
        onSelectConversation={(conversationId) => void selectConversation(conversationId)}
      />
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-4 md:px-8">
          <div className="md:hidden"><Logo /></div>
          <div className="hidden md:block">
            <h1 className="text-lg font-bold text-slate-950">AI Assistant</h1>
            <p className="text-xs text-slate-500">Ask questions about your support knowledge base</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 sm:flex">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Ready to help
            </div>
            <button aria-label="Sign out" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 md:hidden" onClick={onLogout} type="button">
              <Icon name="logout" size={18} />
            </button>
          </div>
        </header>
        <section aria-label="Conversation" className="flex-1 overflow-y-auto px-4 py-6 sm:px-8">
          <div className="mx-auto flex min-h-full max-w-3xl flex-col">
            {isLoadingConversation ? (
              <div className="flex flex-1 items-center justify-center py-10 text-sm text-slate-400">
                Loading conversation…
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-1 flex-col items-center justify-center py-10 text-center">
                <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-100 text-indigo-600">
                  <Icon name="sparkles" size={30} />
                </div>
                <h2 className="text-2xl font-bold tracking-tight text-slate-950">How can I help today?</h2>
                <p className="mt-3 max-w-md text-sm leading-6 text-slate-500">Ask me anything about your products, policies, and support documentation.</p>
                <div className="mt-8 grid w-full max-w-2xl gap-3 sm:grid-cols-3">
                  {exampleQuestions.map((example) => (
                    <button className="rounded-xl border border-slate-200 bg-white p-4 text-left text-xs font-medium leading-5 text-slate-600 shadow-sm transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700" key={example} onClick={() => setQuestion(example)} type="button">
                      {example}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                {messages.map((message) => <MessageBubble key={message.id} message={message} />)}
                {isSending && (
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-100 text-indigo-600"><Icon name="sparkles" size={16} /></div>
                    <div className="flex gap-1 rounded-2xl rounded-bl-md border border-slate-200 bg-white px-4 py-4 shadow-sm">
                      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400" />
                      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:120ms]" />
                      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:240ms]" />
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </section>
        <div className="border-t border-slate-200 bg-white px-4 pb-5 pt-4 sm:px-8">
          <form className="mx-auto max-w-3xl" onSubmit={(event) => void sendQuestion(event)}>
            {error && (
              <div className="mb-3 flex items-center justify-between gap-3 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
                <span>{error}</span>
                <button className="font-semibold hover:underline" onClick={() => setError('')} type="button">Dismiss</button>
              </div>
            )}
            <div className="flex items-end gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-2 shadow-sm transition focus-within:border-indigo-400 focus-within:ring-4 focus-within:ring-indigo-100">
              <label className="sr-only" htmlFor="question">Ask a question</label>
              <textarea
                className="max-h-40 min-h-12 flex-1 resize-none bg-transparent px-3 py-2.5 text-sm leading-6 text-slate-800 outline-none placeholder:text-slate-400"
                disabled={isSending || isLoadingConversation}
                id="question"
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a question…"
                rows={1}
                value={question}
              />
              <button aria-label="Send question" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-4 focus:ring-indigo-200 disabled:cursor-not-allowed disabled:bg-slate-300" disabled={!question.trim() || isSending || isLoadingConversation} type="submit">
                <Icon name="send" size={17} />
              </button>
            </div>
            <p className="mt-2 text-center text-[11px] text-slate-400">Enter to send · Shift + Enter for a new line</p>
          </form>
        </div>
      </main>
    </div>
  )
}

function App() {
  const [tokens, setTokens] = useState<TokenSet | null>(() => getStoredTokens())
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [profileLoading, setProfileLoading] = useState(() => Boolean(getStoredTokens()))
  const [profileError, setProfileError] = useState('')
  const [showRegistration, setShowRegistration] = useState(() => window.location.hash === '#register')
  const [staffPage, setStaffPage] = useState<StaffPage>(
    () => window.location.hash === '#knowledge-base'
      ? 'knowledge-base'
      : window.location.hash === '#tickets' ? 'tickets' : 'assistant',
  )
  const [loginNotice, setLoginNotice] = useState('')
  const profileRequestRef = useRef<{ access: string; promise: Promise<CurrentUser> } | null>(null)

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash
      setShowRegistration(hash === '#register')
      setStaffPage(
        hash === '#knowledge-base'
          ? 'knowledge-base'
          : hash === '#tickets' ? 'tickets' : 'assistant',
      )
    }
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  useEffect(() => {
    if (!tokens) {
      profileRequestRef.current = null
      return
    }

    let cancelled = false

    const existingRequest = profileRequestRef.current
    const profileRequest = existingRequest?.access === tokens.access
      ? existingRequest.promise
      : getCurrentUser()
    profileRequestRef.current = { access: tokens.access, promise: profileRequest }

    profileRequest
      .then((user) => {
        if (!cancelled) {
          setCurrentUser(user)
          setProfileLoading(false)
        }
      })
      .catch((caughtError) => {
        if (cancelled) {
          return
        }
        setProfileLoading(false)
        if (caughtError instanceof ApiError && caughtError.status === 401) {
          clearStoredTokens()
          setTokens(null)
          return
        }
        if (caughtError instanceof ApiError && caughtError.status === 403) {
          setProfileError('Your account is not permitted to access ResolveAI.')
          return
        }
        setProfileError('Unable to load your account. Check your connection and try again.')
      })

    return () => {
      cancelled = true
    }
  }, [tokens])

  const handleLogout = useCallback(() => {
    clearStoredTokens()
    profileRequestRef.current = null
    setCurrentUser(null)
    setProfileError('')
    setTokens(null)
  }, [])

  function handleLogin(nextTokens: TokenSet) {
    setCurrentUser(null)
    setProfileError('')
    setProfileLoading(true)
    setTokens(nextTokens)
  }

  function navigateTo(page: StaffPage) {
    const nextHash = `#${page}`
    if (window.location.hash === nextHash) {
      setStaffPage(page)
      return
    }
    window.location.hash = page
  }

  if (!tokens) {
    if (showRegistration) {
      return <RegistrationScreen onBackToLogin={(registrationCompleted = false) => {
        setShowRegistration(false)
        window.location.hash = 'login'
        setLoginNotice(registrationCompleted ? 'Your customer account was created. You can now sign in.' : '')
      }} />
    }
    return <LoginScreen onCreateAccount={() => {
      setLoginNotice('')
      setShowRegistration(true)
      window.location.hash = 'register'
    }} onLogin={handleLogin} successMessage={loginNotice} />
  }

  if (profileLoading || !currentUser) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-5">
        <section className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-xl shadow-slate-200/50">
          <Logo />
          {profileError ? (
            <>
              <p className="mt-8 text-sm text-red-700">{profileError}</p>
              <button
                className="mt-6 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700"
                onClick={handleLogout}
                type="button"
              >
                Return to sign in
              </button>
            </>
          ) : (
            <p className="mt-8 text-sm text-slate-500">Loading your workspace…</p>
          )}
        </section>
      </main>
    )
  }

  if (!currentUser.is_staff) {
    return <CustomerDashboard onLogout={handleLogout} user={currentUser} />
  }

  if (staffPage === 'knowledge-base') {
    return <KnowledgeBasePage onLogout={handleLogout} onNavigate={navigateTo} />
  }

  if (staffPage === 'tickets') {
    return <TicketsPage onLogout={handleLogout} onNavigate={navigateTo} user={currentUser} />
  }

  return <AssistantPage onLogout={handleLogout} onNavigate={navigateTo} />
}

export default App
