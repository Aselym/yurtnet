import { Fragment, type ReactNode } from 'react'
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
  /** When set, rows are clustered under a header row per group (e.g. client name), sorted alphabetically. */
  groupBy?: (row: T) => string
  /** When set alongside groupBy, the group header becomes clickable (e.g. to open a customer profile). */
  onGroupClick?: (groupName: string) => void
}

function groupRows<T>(rows: T[], groupBy: (row: T) => string) {
  const groups = new Map<string, T[]>()
  for (const row of rows) {
    const key = groupBy(row)
    const bucket = groups.get(key)
    if (bucket) bucket.push(row)
    else groups.set(key, [row])
  }
  return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0], 'tr'))
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
  groupBy,
  onGroupClick,
}: DataTableProps<T>) {
  const grouped = groupBy && status === 'ready' ? groupRows(rows, groupBy) : null
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
              {grouped
                ? grouped.map(([groupName, groupRows]) => (
                    <Fragment key={groupName}>
                      <tr className="bg-black/[0.03] dark:bg-white/[0.04]">
                        <td
                          colSpan={columns.length}
                          className="px-5 py-2 text-xs font-semibold uppercase tracking-wide text-black/50 dark:text-white/50"
                        >
                          {onGroupClick ? (
                            <button
                              onClick={() => onGroupClick(groupName)}
                              className="hover:text-brand-dark dark:hover:text-brand hover:underline"
                            >
                              {groupName}
                            </button>
                          ) : (
                            groupName
                          )}{' '}
                          <span className="font-normal normal-case text-black/30 dark:text-white/30">({groupRows.length})</span>
                        </td>
                      </tr>
                      {groupRows.map((row) => (
                        <tr key={getRowKey(row)} className="border-b border-black/5 last:border-0 dark:border-white/5">
                          {columns.map((col) => (
                            <td key={col.key} className="px-5 py-3 text-black/80 dark:text-white/80">
                              {col.render(row)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </Fragment>
                  ))
                : rows.map((row) => (
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
