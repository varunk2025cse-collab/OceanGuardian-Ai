import api from './client'

export const getLiveWeather = async (lat, lon) => {
  const response = await api.get('/weather/live', {
    baseURL: '/api/v2',
    params: { lat, lon }
  })
  return response.data
}
