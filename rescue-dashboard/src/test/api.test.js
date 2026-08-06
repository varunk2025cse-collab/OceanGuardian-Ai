import api from '../api/client'
import { login } from '../api/auth'
import { getFleet } from '../api/tracking'
import { getOverview } from '../api/analytics'

describe('api client', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('sends login payload correctly', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: { token: 'abc' } })
    const result = await login('+911234567890', 'secret')
    expect(post).toHaveBeenCalledWith('/auth/login', { phone_number: '+911234567890', password: 'secret' })
    expect(result).toEqual({ token: 'abc' })
  })

  it('handles tracking 404 gracefully', async () => {
    const get = vi.spyOn(api, 'get').mockRejectedValue({ response: { status: 404 } })
    await expect(getFleet(1)).resolves.toBeNull()
    expect(get).toHaveBeenCalled()
  })

  it('handles analytics network error gracefully', async () => {
    const get = vi.spyOn(api, 'get').mockRejectedValue(new Error('Network Error'))
    await expect(getOverview()).resolves.toBeNull()
    expect(get).toHaveBeenCalled()
  })
})
