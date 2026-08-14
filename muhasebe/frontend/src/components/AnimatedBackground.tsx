export function AnimatedBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden bg-[#0a0714]">
      <div className="animate-aurora-1 absolute -left-1/3 -top-1/3 h-[85vh] w-[85vh] rounded-full bg-brand/70 blur-[100px]" />
      <div className="animate-aurora-2 absolute -right-1/4 -top-1/4 h-[75vh] w-[75vh] rounded-full bg-fuchsia-600/65 blur-[110px]" />
      <div className="animate-aurora-3 absolute -bottom-1/3 left-[8%] h-[80vh] w-[80vh] rounded-full bg-purple-600/65 blur-[120px]" />
      <div className="animate-aurora-4 absolute -bottom-1/4 right-[2%] h-[70vh] w-[70vh] rounded-full bg-sky-500/60 blur-[110px]" />
      <div className="animate-aurora-5 absolute left-[32%] top-[25%] h-[60vh] w-[60vh] rounded-full bg-orange-500/55 blur-[100px]" />
      <div className="absolute inset-0 bg-black/10" />
    </div>
  )
}
