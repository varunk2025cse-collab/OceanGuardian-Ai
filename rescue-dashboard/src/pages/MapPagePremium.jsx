import { useState, useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Circle } from 'react-leaflet'
import { getSOS, getWeather } from '../api/admin'
import { getFleet } from '../api/tracking'
import { Header } from '../components/layout/Header'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { usePolling } from '../hooks/usePolling'
import { fmtCoords, timeAgo } from '../utils/formatters'
import 'leaflet/dist/leaflet.css'

// Fix Leaflet default marker icons
import L from 'leaflet'
import icon from 'leaflet/dist/images/marker-icon.png'
import iconShadow from 'leaflet/dist/images/marker-shadow.png'
const DefaultIcon = L.icon({ iconUrl: icon, shadowUrl: iconShadow, iconSize: [25, 41], iconAnchor: [12, 41] })
L.Marker.prototype.options.icon = DefaultIcon

// LIVE/RECENT/LAST_KNOWN/STALE/UNKNOWN — computed server-side
// (backend app/services/tracking_service.py compute_freshness). Never
// recomputed here; a stale vessel must never render the same as a live one.
const FRESHNESS_COLOR = {
  LIVE: '#16a34a',
  RECENT: '#0080e6',
  LAST_KNOWN: '#f59e0b',
  STALE: '#ff1a1a',
  UNKNOWN: '#64748b',
}

function vesselIcon(freshness) {
  const color = FRESHNESS_COLOR[freshness] || FRESHNESS_COLOR.UNKNOWN
  return L.divIcon({
    className: '',
    html: `<div style="background:${color};width:16px;height:16px;border-radius:50%;border:2px solid white;box-shadow:0 0 4px rgba(0,0,0,0.4)"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  })
}

export function MapPagePremium() {
  const [sosAlerts, setSosAlerts] = useState([])
  const [weather, setWeather] = useState([])
  const [fleet, setFleet] = useState([])
  const [center, setCenter] = useState([11.0, 80.0])
  const [showSOS, setShowSOS] = useState(true)
  const [showWeather, setShowWeather] = useState(true)
  const [showFleet, setShowFleet] = useState(true)

  const load = async () => {
    try {
      const [sos, w, f] = await Promise.all([
        getSOS({ status: 'active', limit: 100 }),
        getWeather(),
        getFleet({ limit: 500 }),
      ])
      setSosAlerts(sos.items || [])
      setWeather(w || [])
      setFleet(f || [])
    } catch {}
  }
  usePolling(load, 30000)

  return (
    <div>
      <Header title="Live Operations Map" subtitle="Real-time positions and alerts">
        <div className="flex gap-2">
          <Button
            variant={showSOS ? 'primary' : 'ghost'}
            size="sm"
            icon="🆘"
            onClick={() => setShowSOS(!showSOS)}
          >
            SOS ({sosAlerts.length})
          </Button>
          <Button
            variant={showWeather ? 'primary' : 'ghost'}
            size="sm"
            icon="🌊"
            onClick={() => setShowWeather(!showWeather)}
          >
            Weather ({weather.length})
          </Button>
          <Button
            variant={showFleet ? 'primary' : 'ghost'}
            size="sm"
            icon="🚤"
            onClick={() => setShowFleet(!showFleet)}
          >
            Fleet ({fleet.length})
          </Button>
        </div>
      </Header>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Map */}
        <div className="lg:col-span-3">
          <Card className="p-0 overflow-hidden h-[700px]">
            <MapContainer
              center={center}
              zoom={8}
              className="h-full w-full rounded-2xl"
              scrollWheelZoom={true}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />

              {showFleet && fleet.filter(v => v.latitude != null && v.longitude != null).map(v => (
                <Marker
                  key={v.fisherman_id}
                  position={[v.latitude, v.longitude]}
                  icon={vesselIcon(v.freshness)}
                >
                  <Popup>
                    <div className="p-2">
                      <div className="font-bold mb-1">{v.fisherman_name}</div>
                      <div className="text-xs text-gray-600 mb-1">{v.boat_name || '—'}</div>
                      <div className="text-xs mb-1" style={{ color: FRESHNESS_COLOR[v.freshness] }}>
                        {v.freshness?.replace('_', ' ')}
                      </div>
                      <div className="text-xs text-gray-500">{fmtCoords(v.latitude, v.longitude)}</div>
                      {v.recorded_at && <div className="text-xs text-gray-500">{timeAgo(v.recorded_at)}</div>}
                    </div>
                  </Popup>
                </Marker>
              ))}

              {showSOS && sosAlerts.map(alert => (
                <Marker
                  key={alert.id}
                  position={[alert.latitude, alert.longitude]}
                >
                  <Popup>
                    <div className="p-2">
                      <div className="font-bold text-red-600 mb-1">🆘 SOS ALERT</div>
                      <div className="text-sm mb-1">{alert.fisherman?.full_name}</div>
                      <div className="text-xs text-gray-600 mb-1">{alert.fisherman?.boat_name}</div>
                      <div className="text-xs text-gray-500">{fmtCoords(alert.latitude, alert.longitude)}</div>
                      <div className="text-xs text-gray-500">{timeAgo(alert.triggered_at)}</div>
                    </div>
                  </Popup>
                </Marker>
              ))}

              {showWeather && weather.map(w => (
                <Circle
                  key={w.id}
                  center={[w.center_latitude, w.center_longitude]}
                  radius={w.radius_km * 1000}
                  pathOptions={{
                    color: w.severity === 'danger' ? '#ff1a1a' : w.severity === 'warning' ? '#f59e0b' : '#0080e6',
                    fillOpacity: 0.1,
                    weight: 2
                  }}
                >
                  <Popup>
                    <div className="p-2">
                      <div className="font-bold mb-1">{w.title}</div>
                      <div className="text-xs text-gray-600">{w.description}</div>
                      <div className="text-xs text-gray-500 mt-1">Radius: {w.radius_km}km</div>
                    </div>
                  </Popup>
                </Circle>
              ))}
            </MapContainer>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-1 space-y-4 max-h-[700px] overflow-y-auto">
          {/* Fleet */}
          {showFleet && (
            <Card className="p-4">
              <h3 className="text-white font-bold text-sm mb-3 flex items-center gap-2">
                <span>🚤</span>
                Active Fleet ({fleet.length})
              </h3>
              <div className="space-y-2">
                {fleet.length === 0 ? (
                  <div className="text-slate-400 text-xs text-center py-4">No active trips</div>
                ) : (
                  fleet.map(v => (
                    <div
                      key={v.fisherman_id}
                      onClick={() => v.latitude != null && setCenter([v.latitude, v.longitude])}
                      className="p-3 bg-slate-900/50 rounded-lg border border-slate-700 cursor-pointer hover:border-slate-500 transition-all"
                    >
                      <div className="flex items-center justify-between">
                        <div className="text-white text-sm font-semibold">{v.fisherman_name}</div>
                        <div
                          className="text-[10px] font-bold px-2 py-0.5 rounded-full text-white"
                          style={{ backgroundColor: FRESHNESS_COLOR[v.freshness] }}
                        >
                          {v.freshness?.replace('_', ' ')}
                        </div>
                      </div>
                      <div className="text-slate-400 text-xs">{v.boat_name || '—'}</div>
                      {v.recorded_at && <div className="text-slate-500 text-xs mt-1">{timeAgo(v.recorded_at)}</div>}
                    </div>
                  ))
                )}
              </div>
            </Card>
          )}

          {/* Active SOS */}
          {showSOS && (
            <Card className="p-4">
              <h3 className="text-white font-bold text-sm mb-3 flex items-center gap-2">
                <span>🆘</span>
                Active SOS Alerts ({sosAlerts.length})
              </h3>
              <div className="space-y-2">
                {sosAlerts.length === 0 ? (
                  <div className="text-slate-400 text-xs text-center py-4">No active alerts</div>
                ) : (
                  sosAlerts.map(alert => (
                    <div
                      key={alert.id}
                      onClick={() => setCenter([alert.latitude, alert.longitude])}
                      className="p-3 bg-slate-900/50 rounded-lg border border-red-500/30 cursor-pointer hover:border-red-500/60 transition-all"
                    >
                      <div className="text-white text-sm font-semibold mb-1">
                        {alert.fisherman?.full_name}
                      </div>
                      <div className="text-slate-400 text-xs">
                        {alert.fisherman?.boat_name || '—'}
                      </div>
                      <div className="text-slate-500 text-xs mt-1">
                        {timeAgo(alert.triggered_at)}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Card>
          )}

          {/* Weather Alerts */}
          {showWeather && (
            <Card className="p-4">
              <h3 className="text-white font-bold text-sm mb-3 flex items-center gap-2">
                <span>🌊</span>
                Weather Zones ({weather.length})
              </h3>
              <div className="space-y-2">
                {weather.length === 0 ? (
                  <div className="text-slate-400 text-xs text-center py-4">No active alerts</div>
                ) : (
                  weather.map(w => (
                    <div
                      key={w.id}
                      onClick={() => setCenter([w.center_latitude, w.center_longitude])}
                      className={`p-3 rounded-lg border cursor-pointer hover:border-opacity-60 transition-all ${
                        w.severity === 'danger' 
                          ? 'bg-red-500/10 border-red-500/30' 
                          : w.severity === 'warning'
                          ? 'bg-yellow-500/10 border-yellow-500/30'
                          : 'bg-blue-500/10 border-blue-500/30'
                      }`}
                    >
                      <div className="text-white text-sm font-semibold mb-1">
                        {w.title}
                      </div>
                      <div className="text-slate-400 text-xs">
                        {w.hazard_type?.replace('_', ' ')}
                      </div>
                      <div className="text-slate-500 text-xs mt-1">
                        Radius: {w.radius_km}km
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Card>
          )}

          {/* Legend */}
          <Card className="p-4">
            <h3 className="text-white font-bold text-sm mb-3">Map Legend</h3>
            <div className="space-y-2 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-500 rounded-full" />
                <span className="text-slate-300">Active SOS Alert</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-500 border-2 border-red-500 rounded-full opacity-30" />
                <span className="text-slate-300">Danger Zone</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-yellow-500 border-2 border-yellow-500 rounded-full opacity-30" />
                <span className="text-slate-300">Warning Zone</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-blue-500 border-2 border-blue-500 rounded-full opacity-30" />
                <span className="text-slate-300">Advisory Zone</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
