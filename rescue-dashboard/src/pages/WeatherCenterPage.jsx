import { useState, useEffect } from 'react'
import { Header } from '../components/layout/Header'
import { getLiveWeather } from '../api/weather'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'

// Default to a central ocean coordinate or a major harbor if none provided
const DEFAULT_LAT = 15.2993
const DEFAULT_LON = 74.1240

export function WeatherCenterPage() {
  const [weather, setWeather] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lat, setLat] = useState(DEFAULT_LAT)
  const [lon, setLon] = useState(DEFAULT_LON)

  const fetchWeather = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getLiveWeather(lat, lon)
      setWeather(data)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to fetch weather data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchWeather()
  }, [])

  return (
    <div>
      <Header title="Weather Center" subtitle="Live marine intelligence and risk indicators">
        <div className="flex items-center gap-2">
          <input 
            type="number" 
            value={lat} 
            onChange={e => setLat(Number(e.target.value))} 
            placeholder="Latitude"
            className="bg-slate-800 border border-slate-700 text-white rounded px-3 py-1.5 w-24 text-sm"
          />
          <input 
            type="number" 
            value={lon} 
            onChange={e => setLon(Number(e.target.value))} 
            placeholder="Longitude"
            className="bg-slate-800 border border-slate-700 text-white rounded px-3 py-1.5 w-24 text-sm"
          />
          <Button onClick={fetchWeather} size="sm">Update Location</Button>
        </div>
      </Header>

      {error && (
        <div className="bg-red-500/20 border border-red-500/30 text-red-400 p-4 rounded-xl mb-6">
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {[1,2,3,4].map(i => <Card key={i} className="h-32 animate-pulse bg-slate-800" />)}
        </div>
      ) : weather && (
        <div className="space-y-6">
          <div className="flex justify-between items-end bg-slate-900/50 p-4 rounded-xl border border-slate-700">
            <div>
              <div className="text-slate-400 text-sm mb-1">Observation Time</div>
              <div className="text-white font-bold">{new Date(weather.timestamp).toLocaleString()}</div>
            </div>
            <div className="text-right">
              <div className="text-slate-400 text-sm mb-1">Data Source</div>
              <div className="text-blue-400 font-bold uppercase text-sm tracking-wider bg-blue-500/10 px-2 py-1 rounded border border-blue-500/30 inline-block">
                {weather.source}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            
            {/* Wind */}
            <Card className="p-6">
              <div className="flex items-center gap-3 mb-4 border-b border-slate-700/50 pb-3">
                <div className="text-2xl">💨</div>
                <h3 className="text-slate-300 font-bold">Wind</h3>
              </div>
              <div className="text-3xl font-bold text-white mb-2">
                {weather.wind_speed_kmh !== null ? `${weather.wind_speed_kmh.toFixed(1)} km/h` : '--'}
              </div>
              <div className="text-slate-400 text-sm">
                Direction: {weather.wind_direction_deg !== null ? `${weather.wind_direction_deg.toFixed(0)}°` : '--'}
              </div>
            </Card>

            {/* Waves */}
            <Card className="p-6">
              <div className="flex items-center gap-3 mb-4 border-b border-slate-700/50 pb-3">
                <div className="text-2xl">🌊</div>
                <h3 className="text-slate-300 font-bold">Sea State</h3>
              </div>
              <div className="text-3xl font-bold text-blue-400 mb-2">
                {weather.wave_height_m !== null ? `${weather.wave_height_m.toFixed(1)} m` : '--'}
              </div>
              <div className="text-slate-400 text-sm">
                Dir: {weather.wave_direction_deg !== null ? `${weather.wave_direction_deg.toFixed(0)}°` : '--'}
              </div>
            </Card>

            {/* Rain / Precip */}
            <Card className="p-6">
              <div className="flex items-center gap-3 mb-4 border-b border-slate-700/50 pb-3">
                <div className="text-2xl">🌧️</div>
                <h3 className="text-slate-300 font-bold">Precipitation</h3>
              </div>
              <div className="text-3xl font-bold text-white mb-2">
                {weather.precipitation_mm !== null ? `${weather.precipitation_mm.toFixed(1)} mm` : '--'}
              </div>
              <div className="text-slate-400 text-sm">Last 1 hour</div>
            </Card>

            {/* Visibility & Pressure */}
            <Card className="p-6">
              <div className="flex items-center gap-3 mb-4 border-b border-slate-700/50 pb-3">
                <div className="text-2xl">👁️</div>
                <h3 className="text-slate-300 font-bold">Visibility</h3>
              </div>
              <div className="text-3xl font-bold text-white mb-2">
                {weather.visibility_m !== null ? `${(weather.visibility_m / 1000).toFixed(1)} km` : '--'}
              </div>
              <div className="text-slate-400 text-sm">
                Press: {weather.pressure_hpa !== null ? `${weather.pressure_hpa.toFixed(0)} hPa` : '--'}
              </div>
            </Card>

          </div>

          {/* Risk Indicators */}
          <div className="bg-slate-900/50 p-6 rounded-xl border border-slate-700">
            <h3 className="text-white font-bold text-lg mb-4">Risk Indicators & Marine Forecast</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              
              <div className={`p-4 rounded-lg border flex gap-4 ${
                weather.wind_speed_kmh > 40 ? 'bg-red-500/20 border-red-500/50 text-red-400' :
                weather.wind_speed_kmh > 20 ? 'bg-yellow-500/20 border-yellow-500/50 text-yellow-400' :
                'bg-green-500/10 border-green-500/30 text-green-400'
              }`}>
                <div className="text-3xl">⚠️</div>
                <div>
                  <div className="font-bold uppercase tracking-wider mb-1">Gale / Wind Risk</div>
                  <div className="text-sm opacity-90">
                    {weather.wind_speed_kmh > 40 ? 'Severe Gale Warning. Small crafts should not venture out.' :
                     weather.wind_speed_kmh > 20 ? 'Moderate breeze. Exercise caution.' :
                     'Calm conditions. Safe for operation.'}
                  </div>
                </div>
              </div>

              <div className={`p-4 rounded-lg border flex gap-4 ${
                weather.wave_height_m > 3 ? 'bg-red-500/20 border-red-500/50 text-red-400' :
                weather.wave_height_m > 1.5 ? 'bg-yellow-500/20 border-yellow-500/50 text-yellow-400' :
                'bg-green-500/10 border-green-500/30 text-green-400'
              }`}>
                <div className="text-3xl">⚓</div>
                <div>
                  <div className="font-bold uppercase tracking-wider mb-1">Rough Sea Risk</div>
                  <div className="text-sm opacity-90">
                    {weather.wave_height_m > 3 ? 'Very rough seas. Extreme danger.' :
                     weather.wave_height_m > 1.5 ? 'Moderate swells. Standard precautions advised.' :
                     'Calm seas.'}
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>
      )}
    </div>
  )
}
