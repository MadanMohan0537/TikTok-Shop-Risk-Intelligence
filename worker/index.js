const RULES = [
  { id: 'REFUND_SERIAL_28D', type: 'Refund abuse', severity: 'high', action: 'refund_hold' },
  { id: 'BRUSH_NEW_BUYER_REVIEW', type: 'Brushing', severity: 'high', action: 'gmv_clawback' },
  { id: 'PROMO_NEW_ACCOUNT_STACK', type: 'Promo abuse', severity: 'medium', action: 'coupon_ban' },
  { id: 'NETWORK_SHARED_DEVICE', type: 'Seller collusion', severity: 'critical', action: 'network_hold' },
  { id: 'ATO_GEO_DEVICE_VELOCITY', type: 'Account takeover', severity: 'critical', action: 'step_up_auth' },
  { id: 'PAY_VELOCITY_AVS', type: 'Payment fraud', severity: 'high', action: 'payment_block' },
  { id: 'AFFILIATE_SELF_LOOP', type: 'Affiliate fraud', severity: 'high', action: 'clawback_commission' },
]

function seeded(index) {
  const x = Math.sin(index * 999) * 10000
  return x - Math.floor(x)
}

function cases() {
  return Array.from({ length: 32 }, (_, i) => {
    const rule = RULES[i % RULES.length]
    const score = Math.round(48 + seeded(i + 3) * 51)
    return {
      case_id: `CASE-${String(i + 1).padStart(5, '0')}`,
      entity_id: `${i % 3 === 0 ? 'SELLER' : i % 3 === 1 ? 'BUYER' : 'ORDER'}-${1000 + i}`,
      market: ['US', 'UK', 'ID', 'TH'][i % 4],
      rule_id: rule.id,
      fraud_type: rule.type,
      risk_score: score,
      severity: rule.severity,
      action: rule.action,
      status: i % 5 === 0 ? 'ESCALATED' : 'OPEN',
      gmv_at_risk: Math.round(40 + seeded(i + 11) * 2460),
    }
  }).sort((a, b) => b.risk_score - a.risk_score)
}

function overview() {
  const queue = cases()
  return {
    orders_28d: 128420,
    gmv_28d: 4862510,
    rule_hits: 1847,
    open_cases: queue.filter(x => x.status === 'OPEN').length,
    gmv_at_risk: queue.reduce((sum, x) => sum + x.gmv_at_risk, 0),
    estimated_precision: 0.873,
    estimated_recall: 0.816,
    disclaimer: 'Synthetic portfolio data; not TikTok production metrics.',
  }
}

function scoreOrder(input) {
  const hits = []
  let score = 0
  const add = (rule, weight, evidence) => { score += weight; hits.push({ ...rule, evidence }) }
  if (input.refund_rate_28d >= 0.55 && input.refunds_28d >= 3) add(RULES[0], 35, 'High repeat-refund rate')
  if (input.shared_device_peers >= 3) add(RULES[3], 40, 'Device shared across multiple shops/accounts')
  if (input.new_device && input.distance_miles >= 500 && input.velocity_1h >= 2) add(RULES[4], 35, 'New device, distant location, compressed velocity')
  if (input.auth_fail_1h >= 3 && input.avs_mismatch) add(RULES[5], 30, 'Payment retries with AVS mismatch')
  score = Math.min(100, score)
  return { risk_score: score, decision: score >= 70 ? 'BLOCK' : score >= 35 ? 'REVIEW' : 'APPROVE', hits }
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } })
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url)
    if (url.pathname === '/health') return json({ status: 'ok', runtime: 'cloudflare-workers' })
    if (url.pathname === '/api/overview') return json(overview())
    if (url.pathname === '/api/cases') return json(cases())
    if (url.pathname === '/api/rules') return json(RULES)
    if (url.pathname === '/api/policy') {
      const threshold = Math.max(0, Math.min(100, Number(url.searchParams.get('threshold') || 70)))
      const queue = cases().filter(x => x.risk_score >= threshold)
      return json({ threshold, enforcement_volume: queue.length, gmv_reviewed: queue.reduce((s, x) => s + x.gmv_at_risk, 0), estimated_precision: Math.min(.98, .58 + threshold / 250), estimated_recall: Math.max(.28, 1.12 - threshold / 210) })
    }
    if (url.pathname === '/api/score' && request.method === 'POST') {
      try { return json(scoreOrder(await request.json())) } catch { return json({ error: 'Invalid JSON body' }, 400) }
    }
    if (url.pathname.startsWith('/api/')) return json({ error: 'Not found' }, 404)
    return env.ASSETS.fetch(request)
  }
}

