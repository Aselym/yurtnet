import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Building2, Database, Mail, Rows3, Shapes, ShieldCheck, Trash2, Users2 } from 'lucide-react'
import { api, type ActionResult, type SyncLog } from '../lib/api'
import { fmt } from '../lib/format'
import { useAsync, useLocal } from '../lib/hooks'
import { useWork } from '../lib/state'
import { PageHeader } from '../components/Shell'
import { EFaturaBaglayici, TabloBaglayici } from '../components/KaynakBaglama'
import { Badge, Button, ErrorBox, Field, Loading, Panel, cn, inputCls, toast } from '../components/ui'

type S = Record<string, string | boolean | null>
const BOLUMLER = [
  { key: 'veri', label: 'Veri kaynağı', icon: Database },
  { key: 'takip', label: 'Takip kuralları', icon: Rows3 },
  { key: 'sinif', label: 'Sınıflandırma', icon: Shapes },
  { key: 'grup', label: 'Firma grupları', icon: Users2 },
  { key: 'eposta', label: 'E-posta', icon: Mail },
  { key: 'gorunum', label: 'Şirket', icon: Building2 },
  { key: 'hesap', label: 'Hesap', icon: ShieldCheck },
]

export default function SettingsPage() {
  const [bolum, setBolum] = useLocal('ayar.bolum', 'veri')
  const res = useAsync(() => api.get<S>('/api/settings'), [])
  const [s, setS] = useState<S>({})
  useEffect(() => { if (res.data) setS(res.data) }, [res.data])
  const { reloadMeta } = useWork()
  const [busy, setBusy] = useState(false)

  const save = async (keys: string[]) => {
    setBusy(true)
    try {
      const body = Object.fromEntries(keys.map((k) => [k, s[k] ?? '']))
      const r = await api.post<ActionResult>('/api/settings', body)
      toast.ok(r.message)
      await reloadMeta()
      res.reload()
    } catch (e) { toast.err(e instanceof Error ? e.message : 'Kaydedilemedi.') } finally { setBusy(false) }
  }
  const inp = (k: string, props: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <input value={String(s[k] ?? '')} onChange={(e) => setS({ ...s, [k]: e.target.value })} className={inputCls} {...props} />
  )

  return (
    <div>
      <PageHeader title="Ayarlar" subtitle="Programdaki tüm eşikler, kurallar ve bağlantılar buradan yönetilir." />
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[220px_minmax(0,1fr)]">
        <nav className="panel h-fit p-2 lg:sticky lg:top-6" aria-label="Ayar bölümleri">
          {BOLUMLER.map((b) => (
            <button key={b.key} onClick={() => setBolum(b.key)}
              className={cn('flex w-full items-center gap-2.5 rounded-[var(--radius-panel)] px-3 py-2 text-left text-[13.5px]',
                bolum === b.key ? 'bg-brand-soft font-semibold text-brand-ink' : 'text-ink-2 hover:bg-surface-2 hover:text-ink')}>
              <b.icon className="size-4" />{b.label}
            </button>
          ))}
        </nav>
        <div className="min-w-0">
          {res.error && <ErrorBox message={res.error} onRetry={res.reload} />}
          {!res.data && <Loading />}
          {res.data && bolum === 'veri' && <DataSource s={s} setS={setS} inp={inp} save={save} busy={busy} />}
          {res.data && bolum === 'takip' && (
            <Panel title="Takip kuralları">
              <div className="grid max-w-3xl grid-cols-1 gap-5 md:grid-cols-2">
                <Field label="Hatırlatma günleri" hint="Bitişe kaç gün kala mail gitsin? Virgülle ayırın. Örn: 30,10,5,1">{inp('reminder_days')}</Field>
                <Field label="Yakında dolacak sayılma süresi (gün)" hint="Genel bakış ve lisans ekranlarındaki 'yakında doluyor' eşiği.">{inp('expiring_soon_days', { type: 'number' })}</Field>
                <Field label="Lisans takibine alınacak en eski bitiş tarihi" hint="Bundan önce bitmiş lisanslar takip listesine eklenmez (eski kayıtlar listeyi şişirmesin).">{inp('license_min_expiry', { type: 'date' })}</Field>
                <div />
                <Field label="Abonelik sayılması için en az fatura" hint="Bir ürün bir müşteriye en az bu kadar kez faturalandıysa abonelik sayılır.">{inp('sub_min_invoices', { type: 'number' })}</Field>
                <Field label="Abonelik için en uzun ortalama aralık (gün)" hint="Daha seyrek faturalananlar abonelik değil ara ara alım sayılır.">{inp('sub_max_interval_days', { type: 'number' })}</Field>
                <Field label="Risk katsayısı" hint="Son faturadan bu yana geçen süre normal aralığın bu katını aşınca 'riskli', iki katını aşınca 'kayıp' olur.">{inp('sub_risk_factor', { type: 'number', step: '0.1' })}</Field>
              </div>
              <Button variant="primary" className="mt-6" loading={busy}
                onClick={() => save(['reminder_days', 'expiring_soon_days', 'license_min_expiry', 'sub_min_invoices', 'sub_max_interval_days', 'sub_risk_factor'])}>
                Kaydet
              </Button>
              <p className="mt-3 text-[12.5px] text-muted">Abonelik eşikleri bir sonraki senkronda (ya da firma grubu değiştiğinde) yeniden hesaplanır.</p>
            </Panel>
          )}
          {res.data && bolum === 'sinif' && <Classification />}
          {res.data && bolum === 'grup' && <Groups />}
          {res.data && bolum === 'eposta' && <EmailSettings s={s} inp={inp} save={save} busy={busy} />}
          {res.data && bolum === 'gorunum' && (
            <Panel title="Şirket" hint="Tailglass Analytics bu şirket adına çalışır. Ad ve logo sol üstte, giriş ekranında ve sekme başlığında görünür.">
              <div className="grid max-w-3xl grid-cols-1 gap-5 md:grid-cols-2">
                <Field label="Şirket adı">{inp('company_name')}</Field>
                <Field label="Sabit marka sekmeleri" hint="Ürünler ve stok sayfasında sekme olarak görünen markalar. Virgülle ayırın.">{inp('pinned_brands')}</Field>
                <LogoAlani etiket="Şirket logosu" ipucu="Açık zemin için. PNG, JPG, WEBP ya da SVG; en fazla ~300 KB." deger={s.company_logo} degistir={(v) => setS({ ...s, company_logo: v })} />
                <LogoAlani etiket="Koyu tema logosu" ipucu="İsteğe bağlı. Boşsa koyu temada da yukarıdaki logo kullanılır." deger={s.company_logo_dark} degistir={(v) => setS({ ...s, company_logo_dark: v })} koyu />
              </div>
              <Button variant="primary" className="mt-6" loading={busy} onClick={() => save(['company_name', 'pinned_brands', 'company_logo', 'company_logo_dark'])}>Kaydet</Button>
            </Panel>
          )}
          {res.data && bolum === 'hesap' && <Account />}
        </div>
      </div>
    </div>
  )
}

type Inp = (k: string, p?: React.InputHTMLAttributes<HTMLInputElement>) => ReactNode

function DataSource({ s, setS, inp, save, busy }: { s: S; setS: (s: S) => void; inp: Inp; save: (k: string[]) => void; busy: boolean }) {
  const log = useAsync(() => api.get<SyncLog[]>('/api/sync/gecmis'), [])
  const [testing, setTesting] = useState(false)
  const kayitli = String(s.logo_source || 'mssql')
  const [secim, setSecim] = useState(kayitli)
  const durum = useAsync(() => api.get<{ mod: string; tablo: string | null }>('/api/kaynak/durum'), [])
  const demo = secim === 'demo'
  const dosyaMi = secim === 'dosya' || secim === 'efatura'
  const { reloadMeta } = useWork()
  const bitti = () => { setS({ ...s, logo_source: secim }); durum.reload(); setTimeout(reloadMeta, 4000) }
  return (
    <div className="flex flex-col gap-5">
      <Panel title="Veri kaynağı" hint="Tailglass verinizi nereden okusun? Bütün ekranlar seçilen kaynağın verisiyle çalışır; veri şirketinizin sunucusundan çıkmaz.">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {([
            ['mssql', 'Logo', 'MS SQL veritabanına salt-okunur bağlantı'],
            ['efatura', 'e-Fatura', 'UBL-TR XML / ZIP arşivleri; her muhasebe programıyla'],
            ['dosya', 'Excel / CSV', 'Herhangi bir programdan alınmış satış/alış listesi'],
            ['demo', 'Demo veri', 'Programı örnek veriyle denemek için'],
          ] as const).map(([k, ad, alt]) => (
            <button key={k} onClick={() => { setSecim(k); if (k === 'mssql' || k === 'demo') setS({ ...s, logo_source: k }) }}
              className={cn('rounded-[var(--radius-panel)] border px-4 py-3 text-left transition-colors',
                secim === k ? 'border-ink bg-surface ring-1 ring-ink' : 'border-line bg-surface-2 hover:border-line-strong')}>
              <span className="flex items-center justify-between text-[14px] font-semibold text-ink">{ad}
                {kayitli === k && <Badge tone="good">kullanımda</Badge>}</span>
              <span className="mt-0.5 block text-[12.5px] text-ink-2">{alt}</span>
            </button>
          ))}
        </div>
        {secim === 'dosya' && <div className="mt-5"><TabloBaglayici mevcutDosya={durum.data?.tablo} onBitti={bitti} /></div>}
        {secim === 'efatura' && <div className="mt-5"><EFaturaBaglayici onBitti={bitti} /></div>}
        {!dosyaMi && <p className="mt-3 text-[12.5px] text-muted">
          {demo
            ? 'Demo veri, Logo tablolarının birebir kopyası olan örnek bir veritabanıdır. Şirket ağına bağlı değilken programı denemek içindir.'
            : 'Logo veritabanına salt-okunur bağlanılır; hiçbir şey yazılmaz. Sorgular kilitlenmeyi önlemek için NOLOCK ile çalışır.'}
        </p>}
        {secim === 'mssql' && (
          <div className="mt-5 grid max-w-3xl grid-cols-1 gap-4 md:grid-cols-2">
            <Field label="SQL sunucu">{inp('logo_sql_server')}</Field>
            <Field label="Port">{inp('logo_sql_port')}</Field>
            <Field label="Veritabanı">{inp('logo_sql_db')}</Field>
            <Field label="Kullanıcı">{inp('logo_sql_user', { autoComplete: 'off' })}</Field>
            <Field label="Şifre" hint={s.logo_sql_pass_set ? 'Kayıtlı bir şifre var; değiştirmek istemiyorsanız boş bırakın.' : undefined}>
              {inp('logo_sql_pass', { type: 'password', autoComplete: 'new-password', placeholder: s.logo_sql_pass_set ? '••••••••' : '' })}
            </Field>
            <Field label="Firma no">{inp('logo_firm_no')}</Field>
            <Field label="Dönem no" hint="Birden fazla dönem varsa virgülle: 01,02,03">{inp('logo_period_no')}</Field>
          </div>
        )}
        {!dosyaMi && <>
        <div className="mt-5 grid max-w-3xl grid-cols-1 gap-4 md:grid-cols-2">
          <Field label="Veri başlangıç tarihi" hint="Bu tarihten itibaren veri alınır. Boş bırakırsanız kaynaktaki tüm geçmiş alınır.">
            <span className="flex gap-2">{inp('data_start_date', { type: 'date' })}
              <Button variant="ghost" onClick={() => setS({ ...s, data_start_date: '' })}>Tümü</Button></span>
          </Field>
          <Field label="Otomatik senkron saatleri" hint="Günün hangi saatlerinde Logo'dan veri çekilsin? Virgülle: 9,12,15,18">{inp('sync_hours')}</Field>
          <label className="flex items-center gap-2 text-[13.5px]">
            <input type="checkbox" checked={s.logo_auto_sync === 'ON'} onChange={(e) => setS({ ...s, logo_auto_sync: e.target.checked ? 'ON' : 'OFF' })} className="accent-[var(--brand)]" />
            Otomatik senkron açık
          </label>
        </div>
        <div className="mt-6 flex flex-wrap gap-2">
          <Button variant="primary" loading={busy} onClick={() => save(['logo_source', 'logo_sql_server', 'logo_sql_port', 'logo_sql_db', 'logo_sql_user', 'logo_sql_pass',
            'logo_firm_no', 'logo_period_no', 'data_start_date', 'sync_hours', 'logo_auto_sync'])}>Kaydet</Button>
          <Button loading={testing} onClick={async () => {
            setTesting(true)
            try {
              const r = await api.post<ActionResult>('/api/logo/test-connection')
              r.success ? toast.ok(r.message) : toast.err(r.message)
            } catch (e) { toast.err(e instanceof Error ? e.message : 'Test edilemedi.') } finally { setTesting(false) }
          }}>Bağlantıyı test et</Button>
        </div>
        <p className="mt-2 text-[12.5px] text-muted">Önce kaydedin, sonra test edin. Senkronu üst çubuktaki düğmeyle başlatabilirsiniz.</p>
        </>}
      </Panel>
      <Panel title="Senkron geçmişi" bodyClass="p-0">
        {log.data && log.data.length === 0 && <p className="p-5 text-[13px] text-muted">Henüz senkron yapılmadı.</p>}
        {log.data && log.data.length > 0 && (
          <div className="scroll-thin overflow-x-auto">
            <table className="w-full min-w-[520px] text-[13px]">
            <thead className="bg-surface-2 text-left text-ink-2"><tr>
              <th className="px-5 py-2 font-medium">Bitiş</th><th className="font-medium">Kaynak</th><th className="text-right font-medium">Satır</th>
              <th className="text-right font-medium">Ürün</th><th className="px-5 text-right font-medium">Cari</th></tr></thead>
            <tbody>{log.data.map((l) => (
              <tr key={l.id} className="border-t border-line">
                <td className="tnum px-5 py-2">{l.finished_at?.replace('T', ' ')}</td><td>{({ demo: 'Demo', dosya: 'Excel / CSV', efatura: 'e-Fatura' } as Record<string, string>)[l.source] ?? 'Logo'}</td>
                <td className="tnum text-right">{fmt(l.lines, 'num')}</td><td className="tnum text-right">{fmt(l.items, 'num')}</td>
                <td className="tnum px-5 text-right">{fmt(l.clients, 'num')}</td>
              </tr>
            ))}</tbody>
          </table>
          </div>
        )}
      </Panel>
    </div>
  )
}

interface Rule { id: number; field: string; pattern: string; value: string }
interface Review { item_ref: number; name: string; code: string; brand: string; brand_src: string; category: string; category_src: string; sales_tl: number }
const ALAN: Record<string, string> = { brand: 'Marka', category: 'Kategori', revenue_type: 'Gelir tipi' }
const KAYNAK: Record<string, string> = { kural: 'kural', logo: 'Logo kartı', sozluk: 'sözlük', tahmin: 'tahmin', yok: 'bulunamadı' }

function Classification() {
  const rules = useAsync(() => api.get<Rule[]>('/api/kurallar'), [])
  const ozet = useAsync(() => api.get<{ brand_sources: { src: string; n: number }[]; category_sources: { src: string; n: number }[]; review: Review[] }>('/api/siniflandirma'), [])
  const [yeni, setYeni] = useState({ field: 'brand', pattern: '', value: '' })
  const [busy, setBusy] = useState(false)
  const ekle = async (r: { field: string; pattern: string; value: string }) => {
    setBusy(true)
    try {
      const x = await api.post<ActionResult>('/api/kurallar', r)
      toast.ok(x.message)
      rules.reload(); ozet.reload()
      setYeni({ ...yeni, pattern: '', value: '' })
    } catch (e) { toast.err(e instanceof Error ? e.message : 'Eklenemedi.') } finally { setBusy(false) }
  }
  return (
    <div className="flex flex-col gap-5">
      <Panel title="Sınıflandırma kuralları"
        hint="Ürün adında ya da kodunda geçen bir metne göre marka, kategori veya gelir tipi atar. Kurallar Logo kartındaki bilgiden ve yerleşik sözlükten önce gelir.">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Alan">
            <select value={yeni.field} onChange={(e) => setYeni({ ...yeni, field: e.target.value })} className={cn(inputCls, 'w-36')}>
              <option value="brand">Marka</option><option value="category">Kategori</option><option value="revenue_type">Gelir tipi</option>
            </select>
          </Field>
          <Field label="Ürün adında/kodunda geçen"><input value={yeni.pattern} onChange={(e) => setYeni({ ...yeni, pattern: e.target.value })} placeholder="Örn: ORICO" className={cn(inputCls, 'w-56')} /></Field>
          <Field label="Atanacak değer">
            {yeni.field === 'revenue_type'
              ? <select value={yeni.value} onChange={(e) => setYeni({ ...yeni, value: e.target.value })} className={cn(inputCls, 'w-44')}>
                <option value="">Seçin</option><option>Ürün</option><option>Tekrarlayan</option></select>
              : <input value={yeni.value} onChange={(e) => setYeni({ ...yeni, value: e.target.value })} placeholder={yeni.field === 'brand' ? 'Orico' : 'Aksesuar'} className={cn(inputCls, 'w-48')} />}
          </Field>
          <Button variant="primary" loading={busy} disabled={!yeni.pattern || !yeni.value} onClick={() => ekle(yeni)}>Kural ekle</Button>
        </div>
        <ul className="mt-5 divide-y divide-line rounded-[var(--radius-panel)] border border-line">
          {(rules.data ?? []).length === 0 && <li className="px-4 py-3 text-[13px] text-muted">Henüz kural yok.</li>}
          {(rules.data ?? []).map((r) => (
            <li key={r.id} className="flex items-center justify-between gap-3 px-4 py-2 text-[13px]">
              <span><Badge>{ALAN[r.field]}</Badge> <b>{r.pattern}</b> geçen ürünler <b>{r.value}</b></span>
              <button onClick={async () => { await api.del(`/api/kurallar/${r.id}`); rules.reload(); ozet.reload() }} aria-label="Kuralı sil" className="text-muted hover:text-neg"><Trash2 className="size-4" /></button>
            </li>
          ))}
        </ul>
      </Panel>
      <Panel title="Kontrol edilmesi gereken ürünler" hint="Markası tahminle bulunmuş ya da hiç bulunamamış ürünler, satış tutarına göre. Doğrusu farklıysa kural ekleyin.">
        {ozet.data && (
          <p className="mb-3 text-[13px] text-ink-2">
            Marka kaynakları: {ozet.data.brand_sources.map((x) => `${KAYNAK[x.src] ?? x.src} ${x.n.toLocaleString('tr-TR')}`).join(', ')}
          </p>
        )}
        <ul className="scroll-thin max-h-[480px] divide-y divide-line overflow-auto rounded-[var(--radius-panel)] border border-line">
          {(ozet.data?.review ?? []).slice(0, 150).map((r) => <ReviewRow key={r.item_ref} r={r} onRule={ekle} />)}
        </ul>
      </Panel>
    </div>
  )
}

function ReviewRow({ r, onRule }: { r: Review; onRule: (x: { field: string; pattern: string; value: string }) => void }) {
  const [marka, setMarka] = useState(r.brand === 'Markasız' ? '' : r.brand)
  const ilk = r.name.split(/\s+/)[0]
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 text-[13px]">
      <span className="min-w-0 flex-1">
        <span className="block truncate">{r.name}</span>
        <span className="text-[12px] text-muted">marka: {r.brand} ({KAYNAK[r.brand_src]}), kategori: {r.category} — satış {fmt(r.sales_tl, 'tl')}</span>
      </span>
      <span className="flex items-center gap-1.5">
        <input value={marka} onChange={(e) => setMarka(e.target.value)} placeholder="Doğru marka" className={cn(inputCls, 'h-8 w-36 text-[13px]')} />
        <Button size="sm" disabled={!marka} title={`Adı "${ilk}" ile başlayan/geçen tüm ürünlere uygulanır`}
          onClick={() => onRule({ field: 'brand', pattern: ilk, value: marka })}>"{ilk}" için kural yap</Button>
      </span>
    </li>
  )
}

function Groups() {
  const g = useAsync(() => api.get<{ client_name: string; group_name: string }[]>('/api/firma-gruplari'), [])
  const gruplar = useMemo(() => {
    const m = new Map<string, string[]>()
    g.data?.forEach((x) => m.set(x.group_name, [...(m.get(x.group_name) ?? []), x.client_name]))
    return [...m.entries()]
  }, [g.data])
  return (
    <Panel title="Firma grupları" hint="Ana firma ve yan firmalar. Müşteri profilinden ya da Abonelikler sayfasından firma ekleyebilirsiniz.">
      {gruplar.length === 0 && <p className="text-[13px] text-muted">Henüz grup yok. Müşteriler sayfasında bir firmaya tıklayıp en alttaki "Firma grubu" bölümünden oluşturabilirsiniz.</p>}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {gruplar.map(([ad, firmalar]) => (
          <div key={ad} className="rounded-[var(--radius-panel)] border border-line p-4">
            <p className="font-semibold">{ad}</p>
            <ul className="mt-2 flex flex-col gap-1">
              {firmalar.map((f) => (
                <li key={f} className="flex items-center justify-between gap-2 text-[13px] text-ink-2">
                  <span className="truncate">{f}</span>
                  <button onClick={async () => { await api.del(`/api/firma-gruplari/${encodeURIComponent(f)}`); g.reload() }} aria-label="Gruptan çıkar" className="text-muted hover:text-neg"><Trash2 className="size-3.5" /></button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function EmailSettings({ s, inp, save, busy }: { s: S; inp: Inp; save: (k: string[]) => void; busy: boolean }) {
  const [testing, setTesting] = useState(false)
  return (
    <Panel title="E-posta (SMTP)" hint="Lisans hatırlatmaları bu hesapla, aşağıdaki iç alıcılara gönderilir.">
      <div className="grid max-w-3xl grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="SMTP sunucu">{inp('smtp_host')}</Field>
        <Field label="Port">{inp('smtp_port')}</Field>
        <Field label="Kullanıcı">{inp('smtp_user', { autoComplete: 'off' })}</Field>
        <Field label="Şifre" hint={s.smtp_password_set ? 'Kayıtlı bir şifre var; değiştirmek istemiyorsanız boş bırakın.' : undefined}>
          {inp('smtp_password', { type: 'password', autoComplete: 'new-password', placeholder: s.smtp_password_set ? '••••••••' : '' })}
        </Field>
        <Field label="Gönderen adres">{inp('sender_email')}</Field>
        <Field label="Gönderen adı">{inp('sender_name')}</Field>
        <div className="md:col-span-2"><Field label="İç alıcılar" hint="Hatırlatmaların gideceği adresler, virgülle ayırın.">{inp('internal_recipients')}</Field></div>
        <div className="md:col-span-2"><Field label="Uygulamanın ağdaki adresi" hint="Maildeki 'Uygulamada aç' bağlantısı için. Örn: http://192.168.0.250:5000">{inp('app_public_url')}</Field></div>
      </div>
      <div className="mt-6 flex gap-2">
        <Button variant="primary" loading={busy} onClick={() => save(['smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'sender_email', 'sender_name', 'internal_recipients', 'app_public_url'])}>Kaydet</Button>
        <Button loading={testing} onClick={async () => {
          setTesting(true)
          try {
            const r = await api.post<ActionResult>('/api/test-email', {})
            r.success ? toast.ok(r.message) : toast.err(r.message)
          } catch (e) { toast.err(e instanceof Error ? e.message : 'Gönderilemedi.') } finally { setTesting(false) }
        }}>Test e-postası gönder</Button>
      </div>
    </Panel>
  )
}

function Account() {
  const [f, setF] = useState({ current_password: '', new_username: '', new_password: '' })
  const [busy, setBusy] = useState(false)
  return (
    <Panel title="Hesap">
      <div className="grid max-w-md grid-cols-1 gap-4">
        <Field label="Mevcut şifre"><input type="password" value={f.current_password} onChange={(e) => setF({ ...f, current_password: e.target.value })} className={inputCls} /></Field>
        <Field label="Yeni kullanıcı adı" hint="Değiştirmeyecekseniz boş bırakın."><input value={f.new_username} onChange={(e) => setF({ ...f, new_username: e.target.value })} className={inputCls} /></Field>
        <Field label="Yeni şifre" hint="Değiştirmeyecekseniz boş bırakın."><input type="password" value={f.new_password} onChange={(e) => setF({ ...f, new_password: e.target.value })} className={inputCls} /></Field>
      </div>
      <Button variant="primary" className="mt-6" loading={busy} disabled={!f.current_password} onClick={async () => {
        setBusy(true)
        try {
          const r = await api.post<ActionResult>('/api/account', f)
          toast.ok(r.message)
          setF({ current_password: '', new_username: '', new_password: '' })
        } catch (e) { toast.err(e instanceof Error ? e.message : 'Güncellenemedi.') } finally { setBusy(false) }
      }}>Hesabı güncelle</Button>
    </Panel>
  )
}

function LogoAlani({ etiket, ipucu, deger, degistir, koyu }: {
  etiket: string; ipucu: string; deger: unknown; degistir: (v: string) => void; koyu?: boolean
}) {
  const sec = (f: File | undefined) => {
    if (!f) return
    if (f.size > 300 * 1024) { toast.err('Logo dosyası çok büyük (en fazla ~300 KB).'); return }
    const r = new FileReader()
    r.onload = () => degistir(String(r.result))
    r.readAsDataURL(f)
  }
  const v = typeof deger === 'string' ? deger : ''
  return (
    <Field label={etiket} hint={ipucu}>
      <div className="flex items-center gap-3">
        <span className={cn('grid h-14 w-40 place-items-center rounded-[var(--radius-panel)] border border-line-strong p-2', koyu ? 'bg-[#0b0f0e]' : 'bg-white')}>
          {v ? <img src={v} alt="" className="max-h-full max-w-full object-contain" /> : <span className={cn('text-[12px]', koyu ? 'text-[#82918e]' : 'text-muted')}>Logo yok</span>}
        </span>
        <label className="cursor-pointer text-[13px] font-medium text-brand-ink hover:underline">
          Dosya seç
          <input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" className="sr-only" onChange={(e) => sec(e.target.files?.[0])} />
        </label>
        {v && <button onClick={() => degistir('')} className="text-[13px] text-ink-2 hover:text-neg">Kaldır</button>}
      </div>
    </Field>
  )
}
