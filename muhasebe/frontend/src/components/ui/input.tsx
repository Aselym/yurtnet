import * as React from 'react'
import { cn } from '@/lib/cn'

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        'flex h-11 w-full rounded-lg border border-black/10 bg-white px-3.5 text-sm text-black outline-none transition-colors placeholder:text-black/40 focus:border-brand focus:ring-2 focus:ring-brand/20 dark:bg-white/5 dark:border-white/10 dark:text-white dark:placeholder:text-white/40',
        className
      )}
      {...props}
    />
  )
)
Input.displayName = 'Input'
