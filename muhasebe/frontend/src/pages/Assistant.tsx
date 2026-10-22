import { useState } from 'react'
import { AlertTriangle, Info, Mail, MailX, Radar, Send, Siren } from 'lucide-react'
import { api } from '../lib/api'
import { useAsync } from '../lib/hooks'
import { PageHeader } from '../components/Shell'
import { Badge, Button, ErrorBox, Loading, Panel, cn, toast } from '../components/ui'

interface Kayit { id: number; zaman: string; onem: 'acil' | 'onemli' | 'bilgi'; baslik: string; metin: string; kaynak: string; mail: string }

const ONEM = {
  acil: { ad: 'Acil', ton: 'critical' as const, ikon: Siren, cizgi: 'border-[var(--neg)]' },
  onemli: { ad: 'Önemli', ton: 'warning' as const, ikon: AlertTriangle, cizgi: 'border-[var(--warning)]' },
  bilgi: { ad: 'Bilgi', ton: 'neutral' as const, ikon: Info, cizgi: 'border-line-strong' },
}

function mailYazisi(m: string) {
  if (m === 'gonderildi') return { metin: 'Hemen e-postayla bildirildi', ikon: Mail }
  if (m === 'ozet_gonderildi') return { metin: 'Günlük özetle gönderildi', ikon: Mail }
  if (m === 'ozette') return { metin: 'Günlük özette gönderilecek', ikon: Mail }
  if (m.startsWith('gonderilemedi')) return { metin: `E-posta gönderilemedi (${m.replace(/^gonderilemedi:\s*/, '')})`, ikon: MailX }
  return null
}

const zamanYaz = (z: string) => new Date(z).toLocaleString('tr-TR', { dateStyle: 'medium', timeStyle: 'short' })

export default function Assistant() {
  const res = useAsync(() => api.get<{ kayitlar: Kayit[] }>('/api/asistan/gunluk'), [])
  const durum = useAsync(() => api.get<{ acik: boolean; ad?: string; model?: string }>('/api/ai/durum'), [])
  const [calisiyor, setCalisiyor] = useState<'denetim' | 'ozet' | null>(null)
  const [filtre, setFiltre] = useState<'hepsi' | Kayit['onem']>('hepsi')

  const calistir = async (tur: 'denetim' | 'ozet') => {
    setCalisiyor(tur)
    try {
      const r = await api.post<{ success: boolean; message: string }>(tur === 'denetim' ? '/api/asistan/denetle' : '/api/asistan/ozet', {})
      r.success ? toast.ok(r.message) : toast.err(r.message)
      res.reload()
    } catch (e) { toast.err(e instanceof Error ? e.message : 'Çalıştırılamadı.') } finally { setCalisiyor(null) }
  }

  const kayitlar = (res.data?.kayitlar ?? []).filter((k) => filtre === 'hepsi' || k.onem === filtre)
  const say = (o: Kayit['onem']) => res.data?.kayitlar.filter((k) => k.onem === o).length ?? 0

  return (
    <div>
      <PageHeader title="Asistan günlüğü"
        subtitle="Yapay zekâ denetçisi her senkrondan sonra şirketin hareketini tarar. Bulduğu her şey burada; acil olanlar iç ekibe hemen, diğerleri günlük özetle e-postayla gider." />
      {durum.data && !durum.data.acik && (
        <Panel className="mb-5">
          <p className="text-[13.5px] text-ink-2">Denetçi için bir yapay zekâ sağlayıcısı gerekli. <a href="#/ayarlar" className="font-medium text-ink underline"
            onClick={() => { try { localStorage.setItem('ayar.bolum', JSON.stringify('ai')) } catch { /* yok */ } }}>Ayarlar &gt; Yapay zekâ</a> bölümünden seçin.</p>
        </Panel>
      )}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div role="radiogroup" aria-label="Önem" className="flex flex-wrap gap-1.5">
          {([['hepsi', `Hepsi (${res.data?.kayitlar.length ?? 0})`], ['acil', `Acil (${say('acil')})`], ['onemli', `Önemli (${say('onemli')})`], ['bilgi', `Bilgi (${say('bilgi')})`]] as const).map(([k, ad]) => (
            <button key={k} role="radio" aria-checked={filtre === k} onClick={() => setFiltre(k)}
              className={cn('h-8 border px-3 text-[12.5px] rounded-[var(--radius-ctl)]', filtre === k ? 'border-ink bg-ink text-surface' : 'border-line text-ink-2 hover:border-line-strong')}>{ad}</button>
          ))}
        </div>
        <div className="ml-auto flex gap-2">
          <Button loading={calisiyor === 'ozet'} disabled={!!calisiyor} onClick={() => calistir('ozet')}><Send className="size-4" />Özeti şimdi gönder</Button>
          <Button variant="primary" loading={calisiyor === 'denetim'} disabled={!!calisiyor || !durum.data?.acik} onClick={() => calistir('denetim')}><Radar className="size-4" />Şimdi denetle</Button>
        </div>
      </div>
      {res.error && <ErrorBox message={res.error} onRetry={res.reload} />}
      {!res.data && !res.error && <Loading />}
      {res.data && !kayitlar.length && (
        <Panel>
          <p className="text-[13.5px] text-ink-2">{filtre === 'hepsi'
            ? 'Henüz kayıt yok. Denetçi bir sonraki senkrondan sonra çalışır; "Şimdi denetle" ile hemen başlatabilirsiniz.'
            : 'Bu önem derecesinde kayıt yok.'}</p>
        </Panel>
      )}
      <div className="flex flex-col gap-3">
        {kayitlar.map((k) => {
          const o = ONEM[k.onem] ?? ONEM.bilgi
          const m = mailYazisi(k.mail)
          return (
            <article key={k.id} className={cn('panel border-l-[3px] px-5 py-4', o.cizgi, k.kaynak === 'hata' && 'opacity-75')}>
              <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted">
                <Badge tone={o.ton}>{o.ad}</Badge>
                <span>{zamanYaz(k.zaman)}</span>
                {k.kaynak === 'hata' && <span>· Denetim kaydı</span>}
              </div>
              <h3 className="mt-1.5 text-[15px] font-semibold text-ink">{k.baslik}</h3>
              <p className="mt-1 whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink-2">{k.metin}</p>
              {m && <p className="mt-2 flex items-center gap-1.5 text-[12px] text-muted"><m.ikon className="size-3.5" />{m.metin}</p>}
            </article>
          )
        })}
      </div>
    </div>
  )
}
