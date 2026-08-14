import * as React from 'react'
import { cn } from '@/lib/cn'

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-2xl border border-black/5 bg-white/80 backdrop-blur-xl shadow-[0_8px_30px_rgba(0,0,0,0.08)] dark:bg-white/5 dark:border-white/10',
        className
      )}
      {...props}
    />
  )
}
