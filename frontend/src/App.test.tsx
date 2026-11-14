
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import {
  ApiError,
  clearStoredTokens,
  getCurrentUser,
  getStoredTokens,
  listTickets,
  login,
  registerCustomer,
} from './api'

vi.mock('./api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api')>()

  return {
    ...actual,
    clearStoredTokens: vi.fn(),
    getCurrentUser: vi.fn(),
    getStoredTokens: vi.fn(),
    listTickets: vi.fn(),
    login: vi.fn(),
    registerCustomer: vi.fn(),
  }
})

const mockedGetStoredTokens = vi.mocked(getStoredTokens)
const mockedGetCurrentUser = vi.mocked(getCurrentUser)
const mockedLogin = vi.mocked(login)
const mockedRegisterCustomer = vi.mocked(registerCustomer)
const mockedListTickets = vi.mocked(listTickets)
const mockedClearStoredTokens = vi.mocked(clearStoredTokens)

const tokens = {
  access: 'test-access-token',
  refresh: 'test-refresh-token',
}

const customer = {
  id: 1,
  username: 'testcustomer',
  is_staff: false,
}

describe('App authentication and customer dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.history.replaceState({}, '', '/')

    mockedGetStoredTokens.mockReturnValue(null)
    mockedGetCurrentUser.mockResolvedValue(customer)
    mockedListTickets.mockResolvedValue([])
    mockedLogin.mockResolvedValue(tokens)
    mockedRegisterCustomer.mockResolvedValue({
      detail: 'Account created successfully.',
      username: 'testcustomer',
    })
  })

  it('shows the login screen when no token exists', () => {
    render(<App />)

    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/^username$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument()
  })

  it('shows an error when login credentials are invalid', async () => {
    const user = userEvent.setup()

    mockedLogin.mockRejectedValue(
      new ApiError(401, 'Invalid credentials'),
    )

    render(<App />)

    await user.type(screen.getByLabelText(/^username$/i), 'wronguser')
    await user.type(screen.getByLabelText(/^password$/i), 'wrongpassword')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(
      await screen.findByText('Enter a valid username and password.'),
    ).toBeInTheDocument()
  })

  it('logs in and loads the customer dashboard', async () => {
    const user = userEvent.setup()

    render(<App />)

    await user.type(screen.getByLabelText(/^username$/i), 'testcustomer')
    await user.type(screen.getByLabelText(/^password$/i), 'Password123!')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(mockedLogin).toHaveBeenCalledWith(
        'testcustomer',
        'Password123!',
      )
    })

    expect(
      await screen.findByRole('heading', { name: /welcome,\s*testcustomer/i }),
    ).toBeInTheDocument()

    await waitFor(() => {
      expect(mockedGetCurrentUser).toHaveBeenCalled()
      expect(mockedListTickets).toHaveBeenCalled()
    })
  })

  it('signs out and returns to the login screen', async () => {
    const user = userEvent.setup()

    mockedGetStoredTokens.mockReturnValue(tokens)

    render(<App />)

    expect(
      await screen.findByRole('heading', { name: /welcome,\s*testcustomer/i }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /sign out/i }))

    expect(mockedClearStoredTokens).toHaveBeenCalled()
    expect(
      await screen.findByRole('button', { name: /sign in/i }),
    ).toBeInTheDocument()
  })

  it('opens the customer registration screen', async () => {
    const user = userEvent.setup()

    render(<App />)

    await user.click(
      screen.getByRole('button', { name: /create a customer account/i }),
    )

    expect(await screen.findByLabelText(/^name$/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument()
  })

  it('validates empty registration fields', async () => {
    const user = userEvent.setup()

    window.history.replaceState({}, '', '/#register')

    render(<App />)

    await user.click(
      screen.getByRole('button', { name: /create account/i }),
    )

    expect(await screen.findByText('Enter your name.')).toBeInTheDocument()
    expect(screen.getByText('Enter your email address.')).toBeInTheDocument()
    expect(screen.getByText('Choose a username.')).toBeInTheDocument()
    expect(
      screen.getByText('Password must be at least 8 characters.'),
    ).toBeInTheDocument()

    expect(mockedRegisterCustomer).not.toHaveBeenCalled()
  })

  it('shows an error when registration passwords do not match', async () => {
    const user = userEvent.setup()

    window.history.replaceState({}, '', '/#register')

    render(<App />)

    await user.type(screen.getByLabelText(/^name$/i), 'Test Customer')
    await user.type(screen.getByLabelText(/email/i), 'test@example.com')
    await user.type(screen.getByLabelText(/^username$/i), 'testcustomer')
    await user.type(screen.getByLabelText(/^password$/i), 'Password123!')
    await user.type(
      screen.getByLabelText(/confirm password/i),
      'Different123!',
    )

    await user.click(
      screen.getByRole('button', { name: /create account/i }),
    )

    expect(
      await screen.findByText('Passwords do not match.'),
    ).toBeInTheDocument()

    expect(mockedRegisterCustomer).not.toHaveBeenCalled()
  })

  it('registers a customer successfully', async () => {
    const user = userEvent.setup()

    window.history.replaceState({}, '', '/#register')

    render(<App />)

    await user.type(screen.getByLabelText(/^name$/i), 'Test Customer')
    await user.type(screen.getByLabelText(/email/i), 'test@example.com')
    await user.type(screen.getByLabelText(/^username$/i), 'testcustomer')
    await user.type(screen.getByLabelText(/^password$/i), 'Password123!')
    await user.type(
      screen.getByLabelText(/confirm password/i),
      'Password123!',
    )

    await user.click(
      screen.getByRole('button', { name: /create account/i }),
    )

    expect(await screen.findByText('Account created')).toBeInTheDocument()

    expect(mockedRegisterCustomer).toHaveBeenCalledWith({
      name: 'Test Customer',
      email: 'test@example.com',
      username: 'testcustomer',
      password: 'Password123!',
      password_confirmation: 'Password123!',
    })
  })
})
