import { useEffect, useMemo, useState } from 'react'
import { DataTable, type DataTableColumn } from './DataTable'
import { CustomerProfileModal } from './CustomerProfileModal'
import { getProducts, type Product } from '@/lib/api'

type Status = 'loading' | 'error' | 'ready'

export function ProductsTab() {
  const [products, setProducts] = useState<Product[]>([])
  const [status, setStatus] = useState<Status>('loading')
  const [search, setSearch] = useState('')
  const [profileClient, setProfileClient] = useState<string | null>(null)

  async function load() {
    setStatus('loading')
    const data = await getProducts()
    if (data) {
      setProducts(data)
      setStatus('ready')
    } else {
      setStatus('error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return products
    return products.filter(
      (p) => p.client_name.toLowerCase().includes(q) || p.product_name.toLowerCase().includes(q)
    )
  }, [products, search])

  const columns: DataTableColumn<Product>[] = [
    { key: 'product', header: 'Ürün', render: (p) => p.product_name },
    { key: 'quantity', header: 'Adet', render: (p) => String(p.quantity) },
    {
      key: 'line_total',
      header: 'Tutar',
      render: (p) => (p.line_total != null ? `${p.line_total.toLocaleString('tr-TR')} ${p.currency}` : '-'),
    },
    { key: 'sale_date', header: 'Satış Tarihi', render: (p) => p.sale_date },
  ]

  return (
    <>
      <DataTable
        columns={columns}
        rows={filtered}
        status={status}
        onRetry={load}
        searchPlaceholder="Müşteri veya ürün ara..."
        searchValue={search}
        onSearchChange={setSearch}
        getRowKey={(p) => p.id}
        emptyMessage="Henüz ürün kaydı yok."
        groupBy={(p) => p.client_name}
        onGroupClick={setProfileClient}
      />
      {profileClient && <CustomerProfileModal clientName={profileClient} onClose={() => setProfileClient(null)} />}
    </>
  )
}
