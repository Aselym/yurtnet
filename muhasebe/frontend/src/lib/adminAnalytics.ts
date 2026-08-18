import type { Offer, Sale, Subscription } from './api'
import { MONTH_LABELS, getBrandStats, getLostCustomers, getRevenueForecast, isExpiringSoon } from './licenseAnalytics'

export interface RevenueHistoryBucket {
  key: string
  label: string
  revenue: number
  missingPrice: number
}

// getRevenueForecast'ın geçmişe bakan aynası: satış tarihine göre, önceki
// `months` ay içinde faturalanmış lisans gelirini toplar (mevcut durumdan
// bağımsız — geçmişte gerçekleşmiş satış her zaman geçmiş gelirdir).
export function getRevenueHistory(sales: Sale[], months = 6): RevenueHistoryBucket[] {
  const now = new Date()
  const buckets: RevenueHistoryBucket[] = []
  for (let i = months; i >= 1; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    buckets.push({
      key,
      label: `${MONTH_LABELS[d.getMonth()]} ${String(d.getFullYear()).slice(2)}`,
      revenue: 0,
      missingPrice: 0,
    })
  }
  const byKey = new Map(buckets.map((b) => [b.key, b]))

  for (const s of sales) {
    const key = s.sale_date.slice(0, 7)
    const bucket = byKey.get(key)
    if (!bucket) continue
    if (s.price) bucket.revenue += s.price
    else bucket.missingPrice += 1
  }

  return buckets
}

export interface SubscriptionHealthCounts {
  active: number
  atRisk: number
  lost: number
  total: number
}

export function getSubscriptionHealth(subscriptions: Subscription[]): SubscriptionHealthCounts {
  let active = 0
  let atRisk = 0
  let lost = 0
  for (const s of subscriptions) {
    if (s.status === 'ACTIVE') active += 1
    else if (s.status === 'AT_RISK') atRisk += 1
    else if (s.status === 'LOST') lost += 1
  }
  return { active, atRisk, lost, total: subscriptions.length }
}

export interface OfferFunnelStats {
  pending: number
  accepted: number
  rejected: number
  winRate: number | null // yüzde, kararı verilmiş (accepted+rejected) tekliflere göre
  pendingPipelineValue: number
  pendingMissingPrice: number
}

export function getOfferFunnel(offers: Offer[]): OfferFunnelStats {
  let pending = 0
  let accepted = 0
  let rejected = 0
  let pendingPipelineValue = 0
  let pendingMissingPrice = 0

  for (const o of offers) {
    if (o.status === 'PENDING') {
      pending += 1
      if (o.offer_price) pendingPipelineValue += o.offer_price * o.quantity
      else pendingMissingPrice += 1
    } else if (o.status === 'ACCEPTED') {
      accepted += 1
    } else if (o.status === 'REJECTED') {
      rejected += 1
    }
  }

  const decided = accepted + rejected
  return {
    pending,
    accepted,
    rejected,
    winRate: decided > 0 ? Math.round((accepted / decided) * 100) : null,
    pendingPipelineValue,
    pendingMissingPrice,
  }
}

export const UNKNOWN_REP = '(Bilinmeyen)'

export interface RepPerformance {
  rep: string
  activeLicenses: number
  expiringSoon: number
  openOffers: number
  wonOffers: number
  lostOffers: number
}

// RepsTab.tsx'in "temsilciler" sekmesiyle aynı hesaplama — tek yerden
// üretilip iki panelde de kullanılır.
export function getRepPerformance(sales: Sale[], offers: Offer[]): RepPerformance[] {
  const reps = new Map<string, RepPerformance>()

  function get(rep: string) {
    const key = rep.trim() || UNKNOWN_REP
    let stats = reps.get(key)
    if (!stats) {
      stats = { rep: key, activeLicenses: 0, expiringSoon: 0, openOffers: 0, wonOffers: 0, lostOffers: 0 }
      reps.set(key, stats)
    }
    return stats
  }

  for (const s of sales) {
    if (s.status === 'EXPIRED' || s.status === 'NEEDS_DURATION') continue
    const stats = get(s.sales_rep ?? '')
    stats.activeLicenses += 1
    if (isExpiringSoon(s)) stats.expiringSoon += 1
  }

  for (const o of offers) {
    const stats = get(o.sales_rep ?? '')
    if (o.status === 'PENDING') stats.openOffers += 1
    else if (o.status === 'ACCEPTED') stats.wonOffers += 1
    else if (o.status === 'REJECTED') stats.lostOffers += 1
  }

  return [...reps.values()].sort((a, b) => {
    if (a.rep === UNKNOWN_REP) return 1
    if (b.rep === UNKNOWN_REP) return -1
    return a.rep.localeCompare(b.rep, 'tr')
  })
}

export type InsightSeverity = 'good' | 'warning' | 'critical'

export interface Insight {
  severity: InsightSeverity
  text: string
}

// Eşik tabanlı, kural tabanlı tavsiye üretimi — makine öğrenmesi/tahmin
// modeli değil. Her kural yalnızca yeterli örneklem varken tetiklenir;
// projenin "emin olunmayan kayıt uyarı üretmez" ilkesiyle tutarlı (bkz.
// muhasebe skill: NEEDS_DURATION kayıtları da aynı sebeple sessiz kalır).
const MIN_BRAND_SAMPLE = 3
const MIN_DECIDED_SAMPLE = 3

export function generateInsights(sales: Sale[], subscriptions: Subscription[], offers: Offer[]): Insight[] {
  const insights: Insight[] = []

  const brandStats = getBrandStats(sales)
  const brandsWithRate = brandStats.filter(
    (b): b is typeof b & { renewalRate: number } => b.renewalRate !== null && b.expired >= MIN_BRAND_SAMPLE
  )
  if (brandsWithRate.length > 0) {
    const avgRate = brandsWithRate.reduce((sum, b) => sum + b.renewalRate, 0) / brandsWithRate.length
    const worst = [...brandsWithRate].sort((a, b) => a.renewalRate - b.renewalRate)[0]
    if (worst.renewalRate < avgRate - 15) {
      insights.push({
        severity: 'warning',
        text: `${worst.brand} markasında yenileme oranı %${worst.renewalRate} — takım ortalaması %${Math.round(avgRate)}'in belirgin altında.`,
      })
    }
    const best = [...brandsWithRate].sort((a, b) => b.renewalRate - a.renewalRate)[0]
    if (best.renewalRate >= 80 && best.brand !== worst.brand) {
      insights.push({
        severity: 'good',
        text: `${best.brand} markasında yenileme oranı %${best.renewalRate} ile güçlü seyrediyor.`,
      })
    }
  }

  const health = getSubscriptionHealth(subscriptions)
  if (health.lost > 0) {
    insights.push({
      severity: 'critical',
      text: `${health.lost} abonelik faturalanmayı bırakmış görünüyor — kayıp müşteri olabilir.`,
    })
  }
  if (health.atRisk > 0) {
    insights.push({
      severity: 'warning',
      text: `${health.atRisk} abonelik "risk altında" — faturalama aralığı normalin üzerine çıktı, iletişime geçilmesi önerilir.`,
    })
  }

  const reps = getRepPerformance(sales, offers)
    .filter((r) => r.rep !== UNKNOWN_REP)
    .map((r) => ({
      rep: r.rep,
      decided: r.wonOffers + r.lostOffers,
      winRate: r.wonOffers + r.lostOffers > 0 ? (r.wonOffers / (r.wonOffers + r.lostOffers)) * 100 : null,
    }))
    .filter((r): r is { rep: string; decided: number; winRate: number } => r.winRate !== null && r.decided >= MIN_DECIDED_SAMPLE)
  if (reps.length >= 2) {
    const avgWinRate = reps.reduce((sum, r) => sum + r.winRate, 0) / reps.length
    const worst = [...reps].sort((a, b) => a.winRate - b.winRate)[0]
    if (worst.winRate < avgWinRate - 20) {
      insights.push({
        severity: 'warning',
        text: `${worst.rep} için teklif kazanma oranı %${Math.round(worst.winRate)} — takım ortalaması %${Math.round(avgWinRate)}'in altında.`,
      })
    }
  }

  const forecast = getRevenueForecast(sales, 3)
  const totalForecast = forecast.reduce((sum, b) => sum + b.revenue, 0)
  if (totalForecast > 0) {
    const top = [...forecast].sort((a, b) => b.revenue - a.revenue)[0]
    const share = top.revenue / totalForecast
    if (share >= 0.6) {
      insights.push({
        severity: 'warning',
        text: `Önümüzdeki 3 aylık beklenen yenileme gelirinin %${Math.round(share * 100)}'i tek bir ayda (${top.label}) yoğunlaşıyor.`,
      })
    }
  }

  const lost = getLostCustomers(sales)
  if (lost.length > 0) {
    insights.push({
      severity: lost.length >= 5 ? 'critical' : 'warning',
      text: `${lost.length} müşterinin lisansı süresi dolmuş ve yenilendiğine dair kayıt yok — takip gerekebilir.`,
    })
  }

  const funnel = getOfferFunnel(offers)
  if (funnel.winRate !== null && funnel.accepted + funnel.rejected >= MIN_DECIDED_SAMPLE) {
    insights.push({
      severity: funnel.winRate >= 50 ? 'good' : 'warning',
      text: `Genel teklif kazanma oranı %${funnel.winRate} (${funnel.accepted}/${funnel.accepted + funnel.rejected}).`,
    })
  }

  if (insights.length === 0) {
    insights.push({
      severity: 'good',
      text: 'Şu an dikkat gerektiren belirgin bir sapma tespit edilmedi.',
    })
  }

  return insights
}
