
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  clearStoredTokens,
  deleteTicket,
  getCurrentUser,
  getStoredTokens,
  listTickets,
  login,
} from './api'

function mockResponse(data: unknown, status = 200) {
  return new Response(
    data === undefined ? null : JSON.stringify(data),
    {
      status,
      headers: { 'Content-Type': 'application/json' },
    },
  )
}

describe('API client', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('returns null when no tokens are stored', () => {
    expect(getStoredTokens()).toBeNull()
  })

  it('stores and retrieves tokens after login', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        mockResponse({
          access: 'access-token',
          refresh: 'refresh-token',
        }),
      ),
    )

    const tokens = await login('testuser', 'password123')

    expect(tokens.access).toBe('access-token')
    expect(getStoredTokens()).toEqual(tokens)
  })

  it('removes stored tokens on logout', () => {
    localStorage.setItem(
      'resolveai_tokens',
      JSON.stringify({
        access: 'a',
        refresh: 'r',
      }),
    )

    clearStoredTokens()

    expect(getStoredTokens()).toBeNull()
  })

  it('sends the access token when requesting the current user', async () => {
    localStorage.setItem(
      'resolveai_tokens',
      JSON.stringify({
        access: 'my-token',
        refresh: 'refresh-token',
      }),
    )

    const fetchMock = vi.fn().mockResolvedValue(
      mockResponse({
        id: 1,
        username: 'testuser',
        is_staff: false,
      }),
    )

    vi.stubGlobal('fetch', fetchMock)

    const user = await getCurrentUser()

    expect(user.username).toBe('testuser')

    expect(
      fetchMock.mock.calls[0][1].headers.get('Authorization'),
    ).toBe('Bearer my-token')
  })

  it('applies ticket filters to the request URL', async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse([]))

    vi.stubGlobal('fetch', fetchMock)

    await listTickets({
      status: 'OPEN',
      priority: 'HIGH',
    })

    const requestUrl = new URL(
      fetchMock.mock.calls[0][0] as string,
    )

    expect(requestUrl.pathname + requestUrl.search).toBe(
      '/api/tickets/?status=OPEN&priority=HIGH',
    )
  })

  it('throws ApiError when the server returns an error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        mockResponse(
          { detail: 'Access denied' },
          403,
        ),
      ),
    )

    await expect(getCurrentUser()).rejects.toMatchObject({
      name: 'ApiError',
      status: 403,
      message: 'Access denied',
    })
  })

  it('uses the default error message for an invalid server response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        mockResponse({}, 500),
      ),
    )

    await expect(getCurrentUser()).rejects.toBeInstanceOf(ApiError)
  })

  it('flattens nested validation errors into field details', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        mockResponse({
          file: ['The file is invalid.'],
          metadata: { title: ['A title is required.'] },
        }, 400),
      ),
    )

    await expect(getCurrentUser()).rejects.toMatchObject({
      status: 400,
      message: 'The file is invalid.',
      details: {
        file: ['The file is invalid.'],
        metadata: ['A title is required.'],
      },
    })
  })

  it('removes malformed tokens from local storage', () => {
    localStorage.setItem('resolveai_tokens', '{invalid-json')

    expect(getStoredTokens()).toBeNull()
    expect(localStorage.getItem('resolveai_tokens')).toBeNull()
  })

  it('throws ApiError when the backend is unreachable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new Error('Network failure')),
    )

    await expect(getCurrentUser()).rejects.toMatchObject({
      name: 'ApiError',
      status: 0,
    })
  })

  it('refreshes the access token and retries after a 401 response', async () => {
    localStorage.setItem(
      'resolveai_tokens',
      JSON.stringify({
        access: 'old-access',
        refresh: 'valid-refresh',
      }),
    )

    const fetchMock = vi.fn()
      .mockResolvedValueOnce(mockResponse(undefined, 401))
      .mockResolvedValueOnce(
        mockResponse({ access: 'new-access' }),
      )
      .mockResolvedValueOnce(
        mockResponse({
          id: 1,
          username: 'testuser',
          is_staff: false,
        }),
      )

    vi.stubGlobal('fetch', fetchMock)

    const user = await getCurrentUser()

    expect(user.username).toBe('testuser')
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(getStoredTokens()?.access).toBe('new-access')
  })

  it('clears stored tokens when refresh fails', async () => {
    localStorage.setItem(
      'resolveai_tokens',
      JSON.stringify({
        access: 'expired-access',
        refresh: 'expired-refresh',
      }),
    )

    const fetchMock = vi.fn()
      .mockResolvedValueOnce(mockResponse(undefined, 401))
      .mockResolvedValueOnce(mockResponse(undefined, 401))

    vi.stubGlobal('fetch', fetchMock)

    await expect(getCurrentUser()).rejects.toMatchObject({
      name: 'ApiError',
      status: 401,
      message: 'Your session has expired. Please sign in again.',
    })

    expect(getStoredTokens()).toBeNull()
  })

  it('handles successful DELETE requests with a 204 response', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockResponse(undefined, 204),
    )

    vi.stubGlobal('fetch', fetchMock)

    await expect(deleteTicket(10)).resolves.toBeUndefined()

    expect(fetchMock.mock.calls[0][0]).toContain('/api/tickets/10/')
    expect(fetchMock.mock.calls[0][1].method).toBe('DELETE')
  })
})


