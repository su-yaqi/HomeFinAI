export function Footer() {
  const currentYear = new Date().getFullYear()

  return (
    <footer className="border-t px-4 py-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-6">
      <div className="flex items-center justify-center">
        <p className="text-muted-foreground text-sm">HomeFin - {currentYear}</p>
      </div>
    </footer>
  )
}
