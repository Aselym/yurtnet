export interface StatsResponse {
  total_sales: number
  active_licenses: number
  expiring_soon: number
  reminders_sent: number
  expired_licenses: number
}

export interface Sale {
  id: number
  product_name: string
  client_name: string
  client_email: string
  sales_rep: string | null
  license_key: string | null
  sale_date: string
  duration_type: string
  duration_months: number
  expiration_date: string
  reminder_type: string
  status: 'PENDING' | 'FIRST_REMINDER_SENT' | 'FINAL_REMINDER_SENT' | 'EXPIRED' | 'NEEDS_DURATION' | 'RENEWED'
  notes: string | null
  days_left: number
  created_at: string
  renewal_state: 'SUSPECT' | 'CONFIRMED' | 'REJECTED' | null
  renewed_by: number | null
  price: number | null
  client_phone: string | null
  client_city: string | null
}

export interface RenewalCandidate {
  eski_id: number
  musteri: string
  eski_urun: string
  eski_satis: string
  eski_bitis: string
  yeni_id: number
  yeni_urun: string
  yeni_satis: string
  yeni_bitis: string
}

export interface Subscription {
  id: number
  client_name: string
  client_email: string | null
  product_name: string
  first_invoice_date: string
  last_invoice_date: string
  invoice_count: number
  avg_interval_days: number | null
  days_since_last: number | null
  status: 'ACTIVE' | 'AT_RISK' | 'LOST'
  source: string | null
  updated_at: string
  client_phone: string | null
  client_city: string | null
}

export interface Product {
  id: number
  product_name: string
  product_code: string | null
  client_name: string
  client_email: string | null
  quantity: number
  unit_price: number | null
  line_total: number | null
  currency: string
  sale_date: string
  invoice_no: string | null
  source: string | null
  created_at: string
  client_phone: string | null
  client_city: string | null
}

export interface Offer {
  id: number
  product_name: string
  quantity: number
  client_name: string
  offer_price: number | null
  currency: string
  offer_date: string
  sales_rep: string | null
  status: 'PENDING' | 'ACCEPTED' | 'REJECTED'
  notes: string | null
  created_at: string
}

export interface NewOffer {
  product_name: string
  quantity: number
  client_name: string
  offer_price: number
  currency: string
  offer_date: string
  sales_rep: string
  notes: string
}

async function getJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(path, { credentials: 'include' })
    if (!res.ok) return null
    return (await res.json()) as T
  } catch {
    return null
  }
}

export function getStats(): Promise<StatsResponse | null> {
  return getJson<StatsResponse>('/api/stats')
}

export function getSales(): Promise<Sale[] | null> {
  return getJson<Sale[]>('/api/sales')
}

export function getSubscriptions(): Promise<Subscription[] | null> {
  return getJson<Subscription[]>('/api/subscriptions')
}

export function getProducts(): Promise<Product[] | null> {
  return getJson<Product[]>('/api/products')
}

export async function setSaleDuration(
  saleId: number,
  durationMonths: number
): Promise<{ success: boolean; message: string; expiration_date?: string }> {
  try {
    const res = await fetch(`/api/sales/${saleId}/set-duration`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ duration_months: durationMonths }),
    })
    const data = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Süre kaydedildi.' : 'Kayıt başarısız.'),
      expiration_date: data.expiration_date,
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}

export function getRenewals(): Promise<RenewalCandidate[] | null> {
  return getJson<RenewalCandidate[]>('/api/renewals')
}

export async function confirmRenewal(
  saleId: number,
  karar: 'CONFIRMED' | 'REJECTED'
): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch(`/api/sales/${saleId}/renewal`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ karar }),
    })
    const data = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Kaydedildi.' : 'İşlem başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}

export function getOffers(): Promise<Offer[] | null> {
  return getJson<Offer[]>('/api/offers')
}

export async function createOffer(offer: NewOffer): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch('/api/offers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(offer),
    })
    const data = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Teklif kaydedildi.' : 'Kayıt başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}

export async function updateOfferStatus(
  offerId: number,
  status: Offer['status']
): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch(`/api/offers/${offerId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ status }),
    })
    const data = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Durum güncellendi.' : 'Güncelleme başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}

export async function deleteOffer(offerId: number): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch(`/api/offers/${offerId}`, {
      method: 'DELETE',
      credentials: 'include',
    })
    const data = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Teklif silindi.' : 'Silme başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}

export type ReminderStage = 'FIRST_REMINDER' | 'FINAL_REMINDER'

export function getSettings(): Promise<Record<string, string> | null> {
  return getJson<Record<string, string>>('/api/settings')
}

export async function updateSettings(
  partial: Record<string, string>
): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(partial),
    })
    const data = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Kaydedildi.' : 'Kayıt başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}

export interface UpdateAccountPayload {
  current_password: string
  new_username?: string
  new_password?: string
}

export async function updateAccount(
  payload: UpdateAccountPayload
): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch('/api/account', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload),
    })
    const data = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Hesap güncellendi.' : 'Güncelleme başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}

export async function sendTestEmail(recipients?: string): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch('/api/test-email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ recipients: recipients ?? '' }),
    })
    const data = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Test e-postası gönderildi.' : 'Gönderim başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}

export async function testLogoConnection(): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch('/api/logo/test-connection', {
      method: 'POST',
      credentials: 'include',
    })
    const data = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Bağlantı başarılı.' : 'Bağlantı başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}

export async function triggerLogoSync(): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch('/api/logo/sync', {
      method: 'POST',
      credentials: 'include',
    })
    const data = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Senkronizasyon tamamlandı.' : 'Senkronizasyon başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}

export async function sendReminder(
  saleId: number,
  stage: ReminderStage
): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch(`/api/sales/${saleId}/send-reminder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ stage }),
    })
    const data = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Hatırlatma gönderildi.' : 'Gönderim başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}
