import { useEffect, useMemo, useState } from 'react'

const apiBase = import.meta.env.VITE_API_BASE_URL || '/api'
const identityKey = 'demand-intelligence-agent.identity'
const cognitoClientId = import.meta.env.VITE_COGNITO_APP_CLIENT_ID || ''
const cognitoRegion = import.meta.env.VITE_COGNITO_REGION || 'us-east-2'

function loadIdentity() {
  try {
    const raw = window.localStorage.getItem(identityKey)
    const identity = raw ? JSON.parse(raw) : null
    if (!identity?.idToken) return null
    const claims = decodeJwtPayload(identity.idToken)
    if (!claims.exp || claims.exp * 1000 <= Date.now()) return null
    return identity
  } catch {
    return null
  }
}

function persistIdentity(identity) {
  if (!window?.localStorage) return
  if (identity) {
    window.localStorage.setItem(identityKey, JSON.stringify(identity))
  } else {
    window.localStorage.removeItem(identityKey)
  }
}

function requestHeaders(identity) {
  const headers = { 'Content-Type': 'application/json' }
  if (identity?.idToken) headers.Authorization = `Bearer ${identity.idToken}`
  return headers
}

function decodeJwtPayload(token) {
  const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
  return JSON.parse(decodeURIComponent(atob(payload).split('').map((char) => `%${(`00${char.charCodeAt(0).toString(16)}`).slice(-2)}`).join('')))
}

async function cognitoLogin(username, password) {
  const response = await fetch(`https://cognito-idp.${cognitoRegion}.amazonaws.com/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-amz-json-1.1', 'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth' },
    body: JSON.stringify({ AuthFlow: 'USER_PASSWORD_AUTH', ClientId: cognitoClientId, AuthParameters: { USERNAME: username, PASSWORD: password } }),
  })
  const payload = await response.json()
  if (!response.ok) throw new Error(payload.message || 'Cognito login failed')
  const claims = decodeJwtPayload(payload.AuthenticationResult.IdToken)
  const groups = claims['cognito:groups'] || []
  const role = groups.includes('EMPLOYEE') ? 'EMPLOYEE' : groups.includes('ADMIN') ? 'ADMIN' : 'CUSTOMER'
  return { userId: claims.sub || claims.username, email: claims.email || username, role, idToken: payload.AuthenticationResult.IdToken, accessToken: payload.AuthenticationResult.AccessToken, refreshToken: payload.AuthenticationResult.RefreshToken }
}

async function apiJson(path, { identity = null, method = 'GET', body } = {}) {
  const response = await fetch(`${apiBase}${path}`, {
    method,
    headers: requestHeaders(identity),
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const text = await response.text()
  const payload = text ? JSON.parse(text) : null
  if (!response.ok) {
    const detail = payload?.detail || payload?.message || response.statusText
    const error = new Error(detail)
    error.status = response.status
    throw error
  }
  return payload
}

function formatMoney(value) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value || 0)
}

function formatNumber(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return Number(value).toFixed(digits)
}

function clampInventoryRows(products) {
  return products.slice(0, 3).map((product) => ({
    product_id: product.id,
    product_name: product.name,
    current_stock: product.current_inventory,
    unit_cost: product.unit_cost,
    supplier_lead_time_days: product.supplier_lead_time_days,
    minimum_order_quantity: product.minimum_order_quantity,
  }))
}

function createDraft(regions, stores, products) {
  const firstRegion = regions[0] || null
  const storesForRegion = stores.filter((store) => store.region === firstRegion?.region)
  const firstStore = storesForRegion[0] || stores[0] || null

  return {
    regionKey: firstRegion?.region || '',
    storeId: firstStore?.store_id || '',
    forecast_horizon_days: 7,
    constraints: { max_purchase_budget: 50000 },
    inventory: clampInventoryRows(products),
  }
}

function Sparkline({ values }) {
  if (!values?.length) return <div className="sparkline-empty">No data</div>

  const width = 280
  const height = 80
  const max = Math.max(...values)
  const min = Math.min(...values)
  const range = max - min || 1
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1 || 1)) * width
      const y = height - ((value - min) / range) * (height - 14) - 7
      return `${x},${y}`
    })
    .join(' ')

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="sparkline">
      <polyline points={points} />
    </svg>
  )
}

function App() {
  const initialIdentity = loadIdentity()
  if (!initialIdentity) persistIdentity(null)
  const [identity, setIdentity] = useState(initialIdentity)
  const [view, setView] = useState(() => (initialIdentity?.role === 'EMPLOYEE' ? 'employee' : initialIdentity?.role === 'CUSTOMER' ? 'customer' : 'login'))
  const [products, setProducts] = useState([])
  const [regions, setRegions] = useState([])
  const [stores, setStores] = useState([])
  const [analytics, setAnalytics] = useState(null)
  const [requests, setRequests] = useState([])
  const [selectedRequestId, setSelectedRequestId] = useState('')
  const [requestBundle, setRequestBundle] = useState(null)
  const [selectedRecommendationId, setSelectedRecommendationId] = useState('')
  const [selectedProductId, setSelectedProductId] = useState('')
  const [selectedProductDetail, setSelectedProductDetail] = useState(null)
  const [draft, setDraft] = useState(() => createDraft([], [], []))
  const [loginForm, setLoginForm] = useState({ userId: '', email: '', password: '', role: 'CUSTOMER' })
  const [employeeForm, setEmployeeForm] = useState({ quantity: '', status: 'REVIEW_REQUIRED', priority: 'HIGH', reason: 'Supplier delivery is arriving tomorrow' })
  const [loading, setLoading] = useState(false)
  const [busyAction, setBusyAction] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  const selectedRegion = useMemo(() => regions.find((region) => region.region === draft.regionKey) || regions[0] || null, [draft.regionKey, regions])
  const availableStores = useMemo(() => stores.filter((store) => store.region === selectedRegion?.region), [selectedRegion, stores])
  const selectedStore = useMemo(() => availableStores.find((store) => store.store_id === draft.storeId) || availableStores[0] || stores[0] || null, [availableStores, draft.storeId, stores])
  const selectedProduct = useMemo(() => products.find((product) => product.id === selectedProductId) || products[0] || null, [products, selectedProductId])
  const selectedRequest = useMemo(() => requestBundle?.request || requests.find((item) => item.request_id === selectedRequestId) || null, [requestBundle, requests, selectedRequestId])
  const selectedRecommendation = useMemo(() => requestBundle?.recommendations?.find((item) => item.recommendation_id === selectedRecommendationId) || requestBundle?.recommendations?.[0] || null, [requestBundle, selectedRecommendationId])
  const customerRequests = useMemo(() => requests.filter((request) => request.created_by === identity?.userId), [identity?.userId, requests])
  const reviewQueue = useMemo(() => requests.filter((request) => ['SUBMITTED', 'ANALYZING', 'REVIEW_REQUIRED', 'MODIFIED'].includes(request.status)), [requests])

  function setAndPersistIdentity(nextIdentity) {
    setIdentity(nextIdentity)
    persistIdentity(nextIdentity)
    setView(nextIdentity ? (nextIdentity.role === 'EMPLOYEE' ? 'employee' : 'customer') : 'login')
  }

  async function refreshWorkspace(nextSelectedRequestId = selectedRequestId) {
    if (!identity) return
    const [nextRequests, nextAnalytics] = await Promise.all([
      apiJson('/requests', { identity }),
      ['EMPLOYEE', 'ADMIN'].includes(identity.role) ? apiJson('/analytics', { identity }) : Promise.resolve(null),
    ])
    setRequests(nextRequests.requests || [])
    setAnalytics(nextAnalytics)
    if (nextSelectedRequestId && nextRequests.requests?.some((request) => request.request_id === nextSelectedRequestId)) {
      setSelectedRequestId(nextSelectedRequestId)
    } else if (!nextSelectedRequestId && nextRequests.requests?.length) {
      setSelectedRequestId(nextRequests.requests[0].request_id)
    }
  }

  async function loadRequestBundle(requestId) {
    if (!identity || !requestId) return
    const [request, forecast, recommendations, audit] = await Promise.all([
      apiJson(`/requests/${requestId}`, { identity }),
      apiJson(`/requests/${requestId}/forecast`, { identity }),
      apiJson(`/requests/${requestId}/recommendations`, { identity }),
      apiJson(`/requests/${requestId}/audit`, { identity }),
    ])
    const nextRecommendations = recommendations.recommendations || []
    setRequestBundle({ request, forecast: forecast.forecasts || [], recommendations: nextRecommendations, audit: audit.events || [] })
    const firstRecommendation = nextRecommendations[0]
    if (firstRecommendation) {
      setSelectedRecommendationId(firstRecommendation.recommendation_id)
      setEmployeeForm({
        quantity: firstRecommendation.manager_quantity ?? firstRecommendation.ai_quantity ?? '',
        status: firstRecommendation.final_status || firstRecommendation.ai_status || 'REVIEW_REQUIRED',
        priority: firstRecommendation.final_priority || firstRecommendation.ai_priority || 'HIGH',
        reason: firstRecommendation.modification_reason || firstRecommendation.ai_reason || '',
      })
    }
  }

  async function loadProductDetail(productId) {
    if (!productId) return
    const detail = await apiJson(`/products/${productId}`)
    setSelectedProductDetail(detail)
  }

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      setLoading(true)
      setError('')
      try {
        const [nextProducts, nextRegions, nextStores] = await Promise.all([
          apiJson('/products'),
          apiJson('/regions'),
          apiJson('/stores'),
        ])

        if (cancelled) return
        setProducts(nextProducts)
        setRegions(nextRegions.regions || [])
        setStores(nextStores.stores || [])

        if (!selectedProductId && nextProducts[0]) {
          setSelectedProductId(nextProducts[0].id)
        }

        if (!draft.inventory.length) {
          setDraft(createDraft(nextRegions.regions || [], nextStores.stores || [], nextProducts))
        }

        if (identity) {
          const nextRequests = await apiJson('/requests', { identity })
          if (cancelled) return
          setRequests(nextRequests.requests || [])
          const nextAnalytics = ['EMPLOYEE', 'ADMIN'].includes(identity.role) ? await apiJson('/analytics', { identity }) : null
          if (cancelled) return
          setAnalytics(nextAnalytics)
          const firstRequestId = nextRequests.requests?.[0]?.request_id || ''
          if (!selectedRequestId && firstRequestId) {
            setSelectedRequestId(firstRequestId)
          }
        }
      } catch (err) {
        if (err.status === 401) {
          setAndPersistIdentity(null)
          if (!cancelled) setError('Your session expired. Please sign in again.')
        } else if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    bootstrap()
    return () => {
      cancelled = true
    }
  }, [identity])

  useEffect(() => {
    if (!selectedProductId) return
    let cancelled = false
    loadProductDetail(selectedProductId).catch((err) => {
      if (!cancelled) setError(err.message)
    })
    return () => {
      cancelled = true
    }
  }, [selectedProductId])

  useEffect(() => {
    if (!identity || !selectedRequestId) return
    let cancelled = false
    loadRequestBundle(selectedRequestId).catch((err) => {
      if (!cancelled) setError(err.message)
    })
    return () => {
      cancelled = true
    }
  }, [identity, selectedRequestId])

  useEffect(() => {
    if (!identity) {
      setView('login')
      return
    }
    if (view === 'login') {
      setView(identity.role === 'EMPLOYEE' ? 'employee' : 'customer')
    }
  }, [identity, view])

  async function handleLoginSubmit(event) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const nextIdentity = await cognitoLogin((loginForm.email || loginForm.userId).trim(), loginForm.password)
      setAndPersistIdentity(nextIdentity)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function handleLogout() {
    setIdentity(null)
    persistIdentity(null)
    setRequests([])
    setRequestBundle(null)
    setSelectedRequestId('')
    setSelectedRecommendationId('')
    setAnalytics(null)
    setView('login')
  }

  function updateInventoryRow(index, patch) {
    setDraft((current) => {
      const nextInventory = current.inventory.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row))
      return { ...current, inventory: nextInventory }
    })
  }

  function replaceInventoryProduct(index, productId) {
    const product = products.find((item) => item.id === productId)
    if (!product) return
    updateInventoryRow(index, {
      product_id: product.id,
      product_name: product.name,
      current_stock: product.current_inventory,
      unit_cost: product.unit_cost,
      supplier_lead_time_days: product.supplier_lead_time_days,
      minimum_order_quantity: product.minimum_order_quantity,
    })
  }

  function addInventoryRow() {
    const fallback = products[0]
    if (!fallback) return
    setDraft((current) => ({
      ...current,
      inventory: [
        ...current.inventory,
        {
          product_id: fallback.id,
          product_name: fallback.name,
          current_stock: fallback.current_inventory,
          unit_cost: fallback.unit_cost,
          supplier_lead_time_days: fallback.supplier_lead_time_days,
          minimum_order_quantity: fallback.minimum_order_quantity,
        },
      ],
    }))
  }

  function removeInventoryRow(index) {
    setDraft((current) => ({ ...current, inventory: current.inventory.filter((_, rowIndex) => rowIndex !== index) }))
  }

  async function createRequest({ submitAfterCreate }) {
    if (!identity) return
    if (!draft.inventory.length) {
      setError('Add at least one inventory item before creating a request.')
      return
    }
    setBusyAction(submitAfterCreate ? 'submit' : 'save')
    setError('')
    setNotice('')
    try {
      const payload = {
        region: {
          country: selectedStore?.country || selectedRegion?.country || 'India',
          state: selectedStore?.state || selectedRegion?.state || 'Karnataka',
          city: selectedStore?.city || selectedRegion?.city || 'Bangalore',
          region: selectedRegion?.region || selectedStore?.region || 'South India',
          store_id: selectedStore?.store_id || draft.storeId,
        },
        forecast_horizon_days: Number(draft.forecast_horizon_days || 7),
        inventory: draft.inventory.map((row) => ({
          product_id: row.product_id,
          product_name: row.product_name,
          current_stock: Number(row.current_stock || 0),
          unit_cost: Number(row.unit_cost || 0),
          supplier_lead_time_days: Number(row.supplier_lead_time_days || 1),
          minimum_order_quantity: Number(row.minimum_order_quantity || 1),
        })),
        constraints: {
          max_purchase_budget: Number(draft.constraints.max_purchase_budget || 0),
        },
      }

      const created = await apiJson('/requests', { identity, method: 'POST', body: payload })
      let finalRequest = created
      if (submitAfterCreate) {
        finalRequest = await apiJson(`/requests/${created.request_id}/submit`, { identity, method: 'POST' })
      }
      setNotice(submitAfterCreate ? `Request ${finalRequest.request_id} created and submitted.` : `Draft ${created.request_id} saved.`)
      await refreshWorkspace(created.request_id)
      setSelectedRequestId(created.request_id)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyAction('')
    }
  }

  async function submitSelectedRequest() {
    if (!identity || !selectedRequestId) return
    setBusyAction('submit-selected')
    setError('')
    try {
      await apiJson(`/requests/${selectedRequestId}/submit`, { identity, method: 'POST' })
      setNotice(`Request ${selectedRequestId} submitted.`)
      await refreshWorkspace(selectedRequestId)
      await loadRequestBundle(selectedRequestId)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyAction('')
    }
  }

  async function analyzeSelectedRequest() {
    if (!identity || !selectedRequestId) return
    setBusyAction('analyze')
    setError('')
    try {
      const result = await apiJson(`/requests/${selectedRequestId}/analyze`, { identity, method: 'POST' })
      setNotice(`Request ${selectedRequestId} analyzed.`)
      await refreshWorkspace(selectedRequestId)
      setRequestBundle((current) => ({
        request: result.request,
        forecast: current?.forecast || [],
        recommendations: result.recommendations || [],
        audit: current?.audit || [],
      }))
      if (result.recommendations?.[0]) {
        setSelectedRecommendationId(result.recommendations[0].recommendation_id)
        setEmployeeForm({
          quantity: result.recommendations[0].manager_quantity ?? result.recommendations[0].ai_quantity ?? '',
          status: result.recommendations[0].final_status || result.recommendations[0].ai_status || 'REVIEW_REQUIRED',
          priority: result.recommendations[0].final_priority || result.recommendations[0].ai_priority || 'HIGH',
          reason: result.recommendations[0].modification_reason || result.recommendations[0].ai_reason || '',
        })
      }
      await loadRequestBundle(selectedRequestId)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyAction('')
    }
  }

  async function applyRecommendationAction(action) {
    if (!identity || !selectedRecommendationId) return
    setBusyAction(action)
    setError('')
    try {
      if (action === 'modify') {
        await apiJson(`/recommendations/${selectedRecommendationId}/modify`, {
          identity,
          method: 'POST',
          body: {
            quantity: employeeForm.quantity === '' ? null : Number(employeeForm.quantity),
            status: employeeForm.status,
            priority: employeeForm.priority,
            reason: employeeForm.reason,
          },
        })
      } else if (action === 'approve') {
        await apiJson(`/recommendations/${selectedRecommendationId}/approve`, { identity, method: 'POST' })
      } else if (action === 'reject') {
        await apiJson(`/recommendations/${selectedRecommendationId}/reject`, { identity, method: 'POST', body: { reason: employeeForm.reason } })
      }
      setNotice(`Recommendation ${selectedRecommendationId} updated.`)
      await refreshWorkspace(selectedRequestId)
      await loadRequestBundle(selectedRequestId)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyAction('')
    }
  }

  async function reloadAll() {
    setBusyAction('refresh')
    setError('')
    try {
      const [nextProducts, nextRegions, nextStores] = await Promise.all([
        apiJson('/products'),
        apiJson('/regions'),
        apiJson('/stores'),
      ])
      setProducts(nextProducts)
      setRegions(nextRegions.regions || [])
      setStores(nextStores.stores || [])
      const nextAnalytics = identity && ['EMPLOYEE', 'ADMIN'].includes(identity.role) ? await apiJson('/analytics', { identity }) : null
      setAnalytics(nextAnalytics)
      if (identity) {
        const nextRequests = await apiJson('/requests', { identity })
        setRequests(nextRequests.requests || [])
        if (!selectedRequestId && nextRequests.requests?.[0]) {
          setSelectedRequestId(nextRequests.requests[0].request_id)
        }
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyAction('')
    }
  }

  const dashboardMetrics = analytics || {
    total_products: products.length,
    stockout_risk: 0,
    reorder_required: 0,
    overstock: 0,
    total_recommended_purchase_value: 0,
    products: products.map((product) => ({
      product,
      current_inventory: product.current_inventory,
      forecast_7_day: 0,
      days_until_stockout: 0,
      risk: 'NORMAL',
      recommended_order: 0,
      priority: 'LOW',
    })),
  }

  const customerMetrics = {
    total: customerRequests.length,
    processing: customerRequests.filter((request) => ['SUBMITTED', 'ANALYZING'].includes(request.status)).length,
    review: customerRequests.filter((request) => request.status === 'REVIEW_REQUIRED').length,
    approved: customerRequests.filter((request) => request.status === 'APPROVED').length,
    rejected: customerRequests.filter((request) => request.status === 'REJECTED').length,
    urgent: customerRequests.reduce((total, request) => total + Number(request.urgent_risks || 0), 0),
  }

  if (!identity) {
    return (
      <LoginScreen
        loginForm={loginForm}
        setLoginForm={setLoginForm}
        onSubmit={handleLoginSubmit}
        loading={loading}
        error={error}
      />
    )
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />

      <header className="topbar">
        <div>
          <p className="eyebrow">DemandOps AI</p>
          <h1>Demand and inventory decisions with humans in control.</h1>
          <p className="lede">Customer requests, deterministic forecasting, employee review, and auditable approvals in one workspace.</p>
        </div>

        <div className="topbar-meta">
          <div className="identity-chip">
            <span>{identity.role}</span>
            <small>{identity.email}</small>
          </div>
          <div className="topbar-actions">
            <button className="ghost" onClick={reloadAll} disabled={Boolean(busyAction)}>
              {busyAction === 'refresh' ? 'Refreshing...' : 'Refresh'}
            </button>
            <button className="ghost" onClick={handleLogout}>
              Sign out
            </button>
          </div>
        </div>
      </header>

      <nav className="view-switcher">
        <button className={view === 'customer' ? 'switch active' : 'switch'} onClick={() => setView('customer')}>
          Customer Dashboard
        </button>
        {['EMPLOYEE', 'ADMIN'].includes(identity.role) ? (
          <>
            <button className={view === 'employee' ? 'switch active' : 'switch'} onClick={() => setView('employee')}>Employee Review</button>
            <button className={view === 'analytics' ? 'switch active' : 'switch'} onClick={() => setView('analytics')}>Analytics</button>
          </>
        ) : null}
        <div className="switch-hint">{busyAction ? `Working: ${busyAction}` : loading ? 'Loading workspace...' : 'Ready'}</div>
      </nav>

      {error ? <div className="banner banner-error">{error}</div> : null}
      {notice ? <div className="banner banner-notice">{notice}</div> : null}

      {['EMPLOYEE', 'ADMIN'].includes(identity.role) ? (
        <section className="stats-grid">
          <StatCard label="Total products" value={dashboardMetrics.total_products} tone="amber" />
          <StatCard label="Stockout risk" value={dashboardMetrics.stockout_risk} tone="rose" />
          <StatCard label="Reorder required" value={dashboardMetrics.reorder_required} tone="violet" />
          <StatCard label="Overstock" value={dashboardMetrics.overstock} tone="teal" />
          <StatCard label="Recommended purchase" value={formatMoney(dashboardMetrics.total_recommended_purchase_value)} tone="gold" wide />
        </section>
      ) : (
        <section className="stats-grid">
          <StatCard label="Total requests" value={customerMetrics.total} tone="amber" />
          <StatCard label="Processing" value={customerMetrics.processing} tone="violet" />
          <StatCard label="Awaiting review" value={customerMetrics.review} tone="gold" />
          <StatCard label="Approved" value={customerMetrics.approved} tone="teal" />
          <StatCard label="Rejected" value={customerMetrics.rejected} tone="rose" />
          <StatCard label="Urgent risks" value={customerMetrics.urgent} tone="rose" />
        </section>
      )}

      {view === 'customer' ? (
        <CustomerView
          products={products}
          regions={regions}
          stores={stores}
          draft={draft}
          setDraft={setDraft}
          selectedRegion={selectedRegion}
          selectedStore={selectedStore}
          selectedProduct={selectedProduct}
          selectedProductDetail={selectedProductDetail}
          customerRequests={customerRequests}
          selectedRequest={selectedRequest}
          selectedRequestId={selectedRequestId}
          setSelectedRequestId={setSelectedRequestId}
          requestBundle={requestBundle}
          onPickProduct={setSelectedProductId}
          onPickRegion={(regionName) => {
            const nextRegion = regions.find((region) => region.region === regionName)
            const nextStore = stores.find((store) => store.region === nextRegion?.region) || stores[0] || null
            setDraft((current) => ({ ...current, regionKey: nextRegion?.region || '', storeId: nextStore?.store_id || '' }))
          }}
          onPickStore={(storeId) => setDraft((current) => ({ ...current, storeId }))}
          onUpdateInventoryRow={updateInventoryRow}
          onReplaceInventoryProduct={replaceInventoryProduct}
          onAddInventoryRow={addInventoryRow}
          onRemoveInventoryRow={removeInventoryRow}
          onCreateDraft={() => createRequest({ submitAfterCreate: false })}
          onCreateAndSubmit={() => createRequest({ submitAfterCreate: true })}
          onSubmitSelected={submitSelectedRequest}
          onSelectRequest={setSelectedRequestId}
          busyAction={busyAction}
        />
      ) : null}

      {view === 'employee' ? (
        <EmployeeView
          products={products}
          requests={requests}
          reviewQueue={reviewQueue}
          selectedRequest={selectedRequest}
          selectedRequestId={selectedRequestId}
          setSelectedRequestId={setSelectedRequestId}
          requestBundle={requestBundle}
          selectedRecommendation={selectedRecommendation}
          selectedRecommendationId={selectedRecommendationId}
          setSelectedRecommendationId={setSelectedRecommendationId}
          employeeForm={employeeForm}
          setEmployeeForm={setEmployeeForm}
          onAnalyze={analyzeSelectedRequest}
          onApply={applyRecommendationAction}
          busyAction={busyAction}
        />
      ) : null}

      {view === 'analytics' ? (
        <AnalyticsView
          analytics={dashboardMetrics}
          products={products}
          selectedProduct={selectedProduct}
          selectedProductDetail={selectedProductDetail}
          onPickProduct={setSelectedProductId}
          requests={requests}
          reviewQueue={reviewQueue}
        />
      ) : null}
    </div>
  )
}

function LoginScreen({ loginForm, setLoginForm, onSubmit, loading, error }) {
  return (
    <div className="login-shell">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />
      <section className="login-card">
        <div>
          <p className="eyebrow">DemandOps AI</p>
          <h1>Inventory decisions with an approval gate.</h1>
          <p className="lede">Sign in with your DemandOps Cognito account. Your role is derived from the server-issued token.</p>
        </div>

        <form className="login-form" onSubmit={onSubmit}>
          <label>
            Email
            <input type="email" value={loginForm.email} onChange={(event) => setLoginForm((current) => ({ ...current, email: event.target.value }))} placeholder="user@example.com" required />
          </label>

          <label>
            Password
            <input type="password" value={loginForm.password} onChange={(event) => setLoginForm((current) => ({ ...current, password: event.target.value }))} required />
          </label>

          {error ? <div className="banner banner-error">{error}</div> : null}

          <button className="primary" type="submit" disabled={loading}>
            {loading ? 'Loading...' : 'Enter workspace'}
          </button>
        </form>
      </section>
    </div>
  )
}

function CustomerView({
  products,
  regions,
  stores,
  draft,
  setDraft,
  selectedRegion,
  selectedStore,
  selectedProduct,
  selectedProductDetail,
  customerRequests,
  selectedRequest,
  selectedRequestId,
  setSelectedRequestId,
  requestBundle,
  onPickProduct,
  onPickRegion,
  onPickStore,
  onUpdateInventoryRow,
  onReplaceInventoryProduct,
  onAddInventoryRow,
  onRemoveInventoryRow,
  onCreateDraft,
  onCreateAndSubmit,
  onSubmitSelected,
  onSelectRequest,
  busyAction,
}) {
  return (
    <section className="workspace-grid customer-layout">
      <div className="column stack">
        <Panel title="Create request" description="Build a regional request with request-specific inventory and sales metadata.">
          <div className="field-grid three-up">
            <label>
              Region
              <select value={draft.regionKey} onChange={(event) => onPickRegion(event.target.value)}>
                {regions.map((region) => (
                  <option key={region.region} value={region.region}>{region.region}</option>
                ))}
              </select>
            </label>

            <label>
              Store
              <select value={draft.storeId} onChange={(event) => onPickStore(event.target.value)}>
                {stores.filter((store) => store.region === selectedRegion?.region).map((store) => (
                  <option key={store.store_id} value={store.store_id}>{store.store_id} - {store.name}</option>
                ))}
              </select>
            </label>

            <label>
              Forecast horizon
              <input type="number" min="1" value={draft.forecast_horizon_days} onChange={(event) => setDraft((current) => ({ ...current, forecast_horizon_days: Number(event.target.value) }))} />
            </label>
          </div>

          <div className="field-grid two-up">
            <label>
              Max purchase budget
              <input type="number" min="0" value={draft.constraints.max_purchase_budget} onChange={(event) => setDraft((current) => ({ ...current, constraints: { ...current.constraints, max_purchase_budget: Number(event.target.value) } }))} />
            </label>
          </div>

          <div className="subtle-card">
            <div className="subtle-grid">
              <Metric label="Selected store" value={selectedStore?.name || 'Choose a store'} />
              <Metric label="Selected region" value={selectedRegion?.region || 'Choose a region'} />
              <Metric label="Historical sales" value="Deployed dataset" />
            </div>
          </div>

          <div className="table-headline">
            <h3>Inventory items</h3>
            <button className="ghost" type="button" onClick={onAddInventoryRow}>
              Add product
            </button>
          </div>

          <div className="inventory-table">
            {draft.inventory.map((row, index) => (
              <div className="inventory-row" key={`${row.product_id}-${index}`}>
                <label>
                  Product
                  <select value={row.product_id} onChange={(event) => onReplaceInventoryProduct(index, event.target.value)}>
                    {products.map((product) => (
                      <option key={product.id} value={product.id}>{product.name}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Current stock
                  <input type="number" min="0" value={row.current_stock} onChange={(event) => onUpdateInventoryRow(index, { current_stock: Number(event.target.value) })} />
                </label>
                <button className="ghost danger" type="button" onClick={() => onRemoveInventoryRow(index)} disabled={draft.inventory.length === 1}>
                  Remove
                </button>
              </div>
            ))}
          </div>

          <div className="button-row">
            <button className="ghost" type="button" onClick={onCreateDraft} disabled={busyAction === 'save' || busyAction === 'submit'}>
              {busyAction === 'save' ? 'Saving...' : 'Save draft'}
            </button>
            <button className="primary" type="button" onClick={onCreateAndSubmit} disabled={busyAction === 'save' || busyAction === 'submit'}>
              {busyAction === 'submit' ? 'Submitting...' : 'Create and submit'}
            </button>
          </div>
        </Panel>

        <Panel title="My requests" description="Track draft, submitted, and review-required work. Select a request to inspect its forecast and audit trail.">
          <div className="request-list">
            {customerRequests.length ? customerRequests.map((request) => (
              <RequestCard key={request.request_id} request={request} active={request.request_id === selectedRequestId} onClick={() => onSelectRequest(request.request_id)} />
            )) : <EmptyState title="No requests yet" description="Save or submit your first request to populate this list." />}
          </div>

          <div className="button-row">
            <button className="ghost" type="button" onClick={onSubmitSelected} disabled={!selectedRequest || busyAction === 'submit-selected'}>
              {busyAction === 'submit-selected' ? 'Submitting...' : 'Submit selected'}
            </button>
          </div>
        </Panel>
      </div>

      <div className="column stack">
        <Panel title="Request detail" description="Forecast, recommendation, and audit history for the selected request.">
          {selectedRequest ? (
            <>
              <div className="detail-topline">
                <div>
                  <strong>Request details</strong>
                  <p>{selectedRequest.region.city}, {selectedRequest.region.state}</p>
                </div>
                <Badge status={selectedRequest.status} />
              </div>

              <div className="detail-grid">
                <Metric label="Forecast horizon" value={`${selectedRequest.forecast_horizon_days} days`} />
                <Metric label="Inventory rows" value={selectedRequest.inventory?.length || 0} />
                <Metric label="Historical sales" value="Deployed dataset" />
              </div>

              <ProcessingTimeline status={selectedRequest.status} events={requestBundle?.audit || []} />

              <div className="detail-stack">
                <div>
                  <h3>Forecast</h3>
                  <div className="forecast-list">
                    {requestBundle?.forecast?.length ? requestBundle.forecast.map((item) => (
                      <div className="forecast-card" key={item.product_id}>
                        <div className="forecast-head">
                          <strong>{products.find((product) => product.id === item.product_id)?.name || 'Product'}</strong>
                          <span>{formatNumber(item.forecast.forecast_quantity)} units / {selectedRequest.forecast_horizon_days} days</span>
                        </div>
                        <Sparkline values={item.forecast.daily_forecast} />
                        <p>{item.forecast.explanation}</p>
                        <div className="metric-strip">
                          <Metric label="Safety stock" value={item.inventory.safety_stock} />
                          <Metric label="ROP" value={item.inventory.reorder_point} />
                          <Metric label="Avg daily demand" value={formatNumber(item.inventory.average_daily_demand)} />
                          <Metric label="Days until stockout" value={formatNumber(item.inventory.days_until_stockout)} />
                          <Metric label="Recommended" value={item.inventory.recommended_order_quantity} />
                          <Metric label="Risk" value={item.decision?.status || item.risk?.status || 'Pending'} />
                        </div>
                      </div>
                    )) : <EmptyState title="Forecast not generated yet" description="Submit the request or ask an employee to analyze it." />}
                  </div>
                </div>

                <div>
                  <h3>Recommendations</h3>
                  <div className="recommendation-stack">
                    {requestBundle?.recommendations?.length ? requestBundle.recommendations.map((item) => (
                      <div key={item.recommendation_id} className="recommendation-card static">
                        <div className="recommendation-head">
                          <strong>{products.find((product) => product.id === item.product_id)?.name || 'Product'}</strong>
                          <Badge status={item.approval_status} />
                        </div>
                        <div className="metric-strip compact">
                          <Metric label="AI qty" value={item.ai_quantity} />
                          <Metric label="Priority" value={item.ai_priority} />
                          <Metric label="Confidence" value={formatNumber(item.ai_confidence, 2)} />
                        </div>
                        <p>{item.ai_reason}</p>
                      </div>
                    )) : <EmptyState title="No recommendations yet" description="Employee analysis creates the review queue and recommendation trail." />}
                  </div>
                </div>

                <div>
                  <h3>Audit trail</h3>
                  <Timeline events={requestBundle?.audit || []} />
                </div>
              </div>
            </>
          ) : (
            <EmptyState title="Select a request" description="Requests appear here after you create or submit one." />
          )}
        </Panel>

        <Panel title="Product detail" description="Selected catalog item with deterministic history and forecast signals.">
          <div className="panel-header compact">
            <select value={selectedProduct?.id || ''} onChange={(event) => onPickProduct(event.target.value)}>
              {products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
            </select>
            <Badge status={selectedProductDetail?.product?.id || 'CATALOG'} />
          </div>
          {selectedProductDetail ? (
            <>
              <div className="detail-grid">
                <Metric label="Category" value={selectedProductDetail.product.category} />
                <Metric label="Current inventory" value={selectedProductDetail.product.current_inventory} />
                <Metric label="Lead time" value={`${selectedProductDetail.product.supplier_lead_time_days} days`} />
                <Metric label="Unit cost" value={formatMoney(selectedProductDetail.product.unit_cost)} />
              </div>
              <Sparkline values={(selectedProductDetail.history || []).map((point) => point.units)} />
              <p className="recommendation-text">Catalog history can be paired with the request flow to validate current recommendation behavior without changing the deterministic math.</p>
            </>
          ) : (
            <EmptyState title="Loading product detail" description="Select a product to inspect its historical demand pattern." />
          )}
        </Panel>
      </div>
    </section>
  )
}

function EmployeeView({
  products,
  requests,
  reviewQueue,
  selectedRequest,
  selectedRequestId,
  setSelectedRequestId,
  requestBundle,
  selectedRecommendation,
  selectedRecommendationId,
  setSelectedRecommendationId,
  employeeForm,
  setEmployeeForm,
  onAnalyze,
  onApply,
  busyAction,
}) {
  return (
    <section className="workspace-grid employee-layout">
      <div className="column stack">
        <Panel title="Review queue" description="Submitted requests waiting for employee analysis or approval.">
          <div className="request-list compact-list">
            {reviewQueue.length ? reviewQueue.map((request) => (
              <RequestCard key={request.request_id} request={request} active={request.request_id === selectedRequestId} onClick={() => setSelectedRequestId(request.request_id)} />
            )) : <EmptyState title="Queue is empty" description="No request currently needs review." />}
          </div>
          <div className="subtle-card">
            <div className="subtle-grid">
              <Metric label="Total requests" value={requests.length} />
              <Metric label="Review queue" value={reviewQueue.length} />
            </div>
          </div>
        </Panel>

        <Panel title="Decision controls" description="Analyze, modify, approve, or reject the selected recommendation.">
          {selectedRequest ? (
            <>
              <div className="detail-topline">
                <div>
                  <strong>{selectedRequest.request_id}</strong>
                  <p>{selectedRequest.region.city}, {selectedRequest.region.state} - {selectedRequest.region.store_id}</p>
                </div>
                <Badge status={selectedRequest.status} />
              </div>

              <div className="button-row wrap">
                <button className="ghost" type="button" onClick={onAnalyze} disabled={busyAction === 'analyze'}>
                  {busyAction === 'analyze' ? 'Analyzing...' : 'Analyze request'}
                </button>
                <button className="ghost" type="button" onClick={() => onApply('modify')} disabled={!selectedRecommendationId || busyAction === 'modify'}>
                  {busyAction === 'modify' ? 'Saving...' : 'Save modification'}
                </button>
                <button className="primary" type="button" onClick={() => onApply('approve')} disabled={!selectedRecommendationId || busyAction === 'approve'}>
                  {busyAction === 'approve' ? 'Approving...' : 'Approve'}
                </button>
                <button className="danger-button" type="button" onClick={() => onApply('reject')} disabled={!selectedRecommendationId || busyAction === 'reject'}>
                  {busyAction === 'reject' ? 'Rejecting...' : 'Reject'}
                </button>
              </div>

              <div className="field-grid three-up">
                <label>
                  Quantity
                  <input type="number" min="0" value={employeeForm.quantity} onChange={(event) => setEmployeeForm((current) => ({ ...current, quantity: event.target.value }))} />
                </label>
                <label>
                  Priority
                  <select value={employeeForm.priority} onChange={(event) => setEmployeeForm((current) => ({ ...current, priority: event.target.value }))}>
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                  </select>
                </label>
                <label>
                  Status
                  <select value={employeeForm.status} onChange={(event) => setEmployeeForm((current) => ({ ...current, status: event.target.value }))}>
                    <option value="REVIEW_REQUIRED">REVIEW_REQUIRED</option>
                    <option value="APPROVED">APPROVED</option>
                    <option value="REJECTED">REJECTED</option>
                    <option value="MODIFIED">MODIFIED</option>
                  </select>
                </label>
              </div>

              <label>
                Modification reason
                <textarea rows="3" value={employeeForm.reason} onChange={(event) => setEmployeeForm((current) => ({ ...current, reason: event.target.value }))} />
              </label>

              {selectedRecommendation ? (
                <div className="comparison-card">
                  <div className="comparison-topline">
                    <div>
                      <p className="eyebrow">Recommendation</p>
                      <h3>{products.find((product) => product.id === selectedRecommendation.product_id)?.name || 'Product'}</h3>
                    </div>
                    <Badge status={selectedRecommendation.approval_status} />
                  </div>

                  <div className="comparison-grid">
                    <Metric label="AI quantity" value={selectedRecommendation.ai_quantity} />
                    <Metric label="Manager quantity" value={selectedRecommendation.manager_quantity ?? 'Pending'} />
                    <Metric label="AI priority" value={selectedRecommendation.ai_priority} />
                    <Metric label="Final priority" value={selectedRecommendation.final_priority || 'Pending'} />
                    <Metric label="Confidence" value={formatNumber(selectedRecommendation.ai_confidence, 2)} />
                    <Metric label="Risk" value={selectedRecommendation.ai_status} />
                  </div>

                  <p className="recommendation-text">{selectedRecommendation.ai_reason}</p>
                </div>
              ) : (
                <EmptyState title="Analyze a request" description="The analysis step creates the recommendation card and audit record." />
              )}
            </>
          ) : (
            <EmptyState title="Select a request" description="Choose a request from the review queue to start analysis." />
          )}
        </Panel>
      </div>

      <div className="column stack">
        <Panel title="Request detail" description="Request context, forecast, recommendations, and audit log.">
          {requestBundle?.request ? (
            <>
              <div className="detail-grid">
                <Metric label="Inventory rows" value={requestBundle.request.inventory?.length || 0} />
                <Metric label="Forecast horizon" value={`${requestBundle.request.forecast_horizon_days} days`} />
                <Metric label="Status" value={requestBundle.request.status} />
              </div>

              <div className="detail-stack">
                <div>
                  <h3>Recommendations</h3>
                  <div className="recommendation-stack">
                    {requestBundle.recommendations?.length ? requestBundle.recommendations.map((item) => (
                      <button
                        key={item.recommendation_id}
                        className={item.recommendation_id === selectedRecommendationId ? 'recommendation-card active' : 'recommendation-card'}
                        onClick={() => setSelectedRecommendationId(item.recommendation_id)}
                        type="button"
                      >
                        <div className="recommendation-head">
                          <strong>{products.find((product) => product.id === item.product_id)?.name || 'Product'}</strong>
                          <Badge status={item.approval_status} />
                        </div>
                        <div className="metric-strip compact">
                          <Metric label="AI qty" value={item.ai_quantity} />
                          <Metric label="Manager qty" value={item.manager_quantity ?? '—'} />
                          <Metric label="Confidence" value={formatNumber(item.ai_confidence, 2)} />
                        </div>
                        <p>{item.ai_reason}</p>
                      </button>
                    )) : <EmptyState title="Waiting for analysis" description="Run the analysis action to generate recommendations." />}
                  </div>
                </div>

                <div>
                  <h3>Forecast</h3>
                  <div className="forecast-list">
                    {requestBundle.forecast?.length ? requestBundle.forecast.map((item) => (
                      <div className="forecast-card" key={item.product_id}>
                        <div className="forecast-head">
                          <strong>{products.find((product) => product.id === item.product_id)?.name || 'Product'}</strong>
                          <span>{item.forecast.trend}</span>
                        </div>
                        <Sparkline values={item.forecast.daily_forecast} />
                        <p>{item.forecast.explanation}</p>
                      </div>
                    )) : <EmptyState title="Forecast unavailable" description="Analysis generates the deterministic forecast view." />}
                  </div>
                </div>

                <div>
                  <h3>Audit trail</h3>
                  <Timeline events={requestBundle.audit || []} />
                </div>
              </div>
            </>
          ) : (
            <EmptyState title="No request selected" description="Select a request in the review queue to see its analysis and audit trail." />
          )}
        </Panel>
      </div>
    </section>
  )
}

function AnalyticsView({ analytics, products, selectedProduct, selectedProductDetail, onPickProduct, requests, reviewQueue }) {
  const topRecommendations = analytics.products.slice(0, 5)
  return (
    <section className="workspace-grid analytics-layout">
      <div className="column stack wide-column">
        <Panel title="Portfolio overview" description="Aggregate demand and inventory view across all products.">
          <div className="detail-grid">
            <Metric label="Requests" value={requests.length} />
            <Metric label="Review queue" value={reviewQueue.length} />
            <Metric label="Urgent products" value={analytics.reorder_required} />
            <Metric label="Purchase value" value={formatMoney(analytics.total_recommended_purchase_value)} />
          </div>

          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Stock</th>
                  <th>7-day forecast</th>
                  <th>Risk</th>
                  <th>Recommended order</th>
                  <th>Priority</th>
                </tr>
              </thead>
              <tbody>
                {topRecommendations.map((row) => (
                  <tr key={row.product.id} onClick={() => onPickProduct(row.product.id)}>
                    <td>{row.product.name}</td>
                    <td>{row.current_inventory}</td>
                    <td>{formatNumber(row.forecast_7_day)}</td>
                    <td>{row.risk}</td>
                    <td>{row.recommended_order}</td>
                    <td>{row.priority}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel title="Product details" description="Inspect one product's historical demand and trend profile.">
          <div className="panel-header compact">
            <select value={selectedProduct?.id || ''} onChange={(event) => onPickProduct(event.target.value)}>
              {products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}
            </select>
            <Badge status={selectedProductDetail?.product?.id || 'CATALOG'} />
          </div>

          {selectedProductDetail ? (
            <>
              <div className="detail-grid">
                <Metric label="Category" value={selectedProductDetail.product.category} />
                <Metric label="Current inventory" value={selectedProductDetail.product.current_inventory} />
                <Metric label="Lead time" value={`${selectedProductDetail.product.supplier_lead_time_days} days`} />
                <Metric label="Cost" value={formatMoney(selectedProductDetail.product.unit_cost)} />
              </div>
              <Sparkline values={(selectedProductDetail.history || []).map((point) => point.units)} />
              <p className="recommendation-text">Catalog history can be paired with the request flow to validate current recommendation behavior without changing the deterministic math.</p>
            </>
          ) : (
            <EmptyState title="Select a product" description="Pick a catalog product to see the historical demand chart." />
          )}
        </Panel>
      </div>
    </section>
  )
}

function Panel({ title, description, children }) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {description ? <p>{description}</p> : null}
        </div>
      </div>
      {children}
    </section>
  )
}

function StatCard({ label, value, tone, wide = false }) {
  return (
    <article className={`stat-card tone-${tone} ${wide ? 'wide' : ''}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  )
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function Badge({ status }) {
  const value = String(status || '').toUpperCase()
  const tone = value.includes('APPROVED') || value === 'NORMAL' || value === 'CATALOG'
    ? 'good'
    : value.includes('REJECTED')
      ? 'danger'
      : value.includes('URGENT') || value.includes('REVIEW') || value.includes('REORDER')
        ? 'alert'
        : 'neutral'
  return <span className={`badge ${tone}`}>{value || 'UNKNOWN'}</span>
}

function RequestCard({ request, active, onClick }) {
  return (
    <button className={active ? 'request-card active' : 'request-card'} onClick={onClick} type="button">
      <div className="request-card-topline">
        <strong>{request.request_id}</strong>
        <Badge status={request.status} />
      </div>
      <p>{request.region.city}, {request.region.state} - {request.region.store_id}</p>
      <div className="request-card-meta">
          <span>{request.inventory?.map((item) => item.product_name).join(', ') || 'No products'}</span>
          <span>Created {new Date(request.created_at).toLocaleDateString()}</span>
          <span>Updated {new Date(request.updated_at).toLocaleDateString()}</span>
          <span>{request.urgent_risks ? `${request.urgent_risks} urgent risk(s)` : 'No urgent risks'}</span>
      </div>
    </button>
  )
}

function Timeline({ events }) {
  if (!events?.length) {
    return <EmptyState title="No audit events yet" description="The audit trail appears once a request is created and analyzed." />
  }

  return (
    <div className="timeline">
      {events.map((event) => (
        <div className="timeline-item" key={event.event_id}>
          <div className="timeline-dot" />
          <div className="timeline-card">
            <div className="timeline-topline">
              <strong>{event.action}</strong>
              <Badge status={event.user_role} />
            </div>
            <p>{event.user_id}</p>
            <small>{new Date(event.timestamp).toLocaleString()}</small>
          </div>
        </div>
      ))}
    </div>
  )
}

function ProcessingTimeline({ status, events }) {
  const completed = new Set((events || []).map((event) => event.action))
  const stages = [
    ['REQUEST_CREATED', 'Request received'],
    ['REQUEST_SUBMITTED', 'Historical demand loaded'],
    ['REQUEST_ANALYZING', 'Demand trend analyzed'],
    ['FORECAST_GENERATED', 'Forecast generated'],
    ['FORECAST_GENERATED', 'Inventory calculated'],
    ['FORECAST_GENERATED', 'Risk analyzed'],
    ['AI_RECOMMENDATION_GENERATED', 'AI recommendation generated'],
    ['REQUEST_REVIEW_REQUIRED', 'Awaiting employee review'],
  ]
  const analysisComplete = ['REVIEW_REQUIRED', 'MODIFIED', 'APPROVED', 'REJECTED'].includes(status)
  const stageComplete = (index, eventName) => {
    if (index >= 4 && completed.has('FORECAST_GENERATED')) return true
    if (index === 6 && completed.has('AI_RECOMMENDATION_GENERATED')) return true
    if (index === 7 && completed.has('REQUEST_REVIEW_REQUIRED')) return true
    return completed.has(eventName)
  }

  return (
    <div className="processing-timeline">
      <h3>Processing</h3>
      <div className="timeline">
        {stages.map(([eventName, label], index) => (
          <div className="timeline-item" key={`${eventName}-${label}`}>
            <div className={`timeline-dot ${stageComplete(index, eventName) ? 'complete' : ''}`} />
            <div className="timeline-card">
              <strong>{label}</strong>
              <small>{stageComplete(index, eventName) ? 'Complete' : index === 7 && analysisComplete ? 'Complete' : 'Pending'}</small>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function EmptyState({ title, description }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  )
}

export default App
