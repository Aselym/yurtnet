import type { ReactNode } from 'react'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

export interface DataTableColumn<T> {
  key: string
  header: string
  render: (row: T) => ReactNode
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[]
  rows: T[]
  status: 'loading' | 'error' | 'ready'
  onRetry: () => void
  searchPlaceholder: string
  searchValue: string
  onSearchChange: (value: string) => void
  getRowKey: (row: T) => string | number
  emptyMessage: string
}

export function DataTable<T>({
  columns,
  rows,
  status,
  onRetry,
  searchPlaceholder,
  searchValue,
  onSearchChange,
  getRowKey,
  emptyMessage,
}: DataTableProps<T>) {
  return (
    <div className="space-y-4">
      <Input
        value={searchValue}
        onChange={(e) => onSearchChange(e.target.value)}
        placeholder={searchPlaceholder}
        className="max-w-xs"
      />
      <Card className="overflow-x-auto p-0">
        {status === 'loading' && (
          <div className="space-y-2 p-5">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-9 animate-pulse rounded-lg bg-black/5 dark:bg-white/5" />
            ))}
          </div>
        )}

        {status === 'error' && (
          <div className="flex flex-col items-center gap-3 p-10 text-center">
            <p className="text-sm text-black/50 dark:text-white/50">Veriler yüklenemedi.</p>
            <Button variant="ghost" onClick={onRetry}>
              Tekrar dene
            </Button>
          </div>
        )}

        {status === 'ready' && rows.length === 0 && (
          <p className="p-10 text-center text-sm text-black/50 dark:text-white/50">{emptyMessage}</p>
        )}

        {status === 'ready' && rows.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-black/5 text-xs uppercase tracking-wide text-black/40 dark:border-white/10 dark:text-white/40">
                {columns.map((col) => (
                  <th key={col.key} className="px-5 py-3 font-medium">
                    {col.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={getRowKey(row)} className="border-b border-black/5 last:border-0 dark:border-white/5">
                  {columns.map((col) => (
                    <td key={col.key} className="px-5 py-3 text-black/80 dark:text-white/80">
                      {col.render(row)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
