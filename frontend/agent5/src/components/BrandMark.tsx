import { useEffect, useState } from 'react'

import {
  applyCompanyDocumentBrand,
  resolveCompanyBrand,
  subscribeCompanyBrand,
} from '../lib/branding'

interface BrandMarkProps {
  subtitle?: string
  size?: 'sm' | 'md' | 'lg'
}

export function BrandMark({ subtitle, size = 'md' }: BrandMarkProps) {
  const [brand, setBrand] = useState(() => resolveCompanyBrand())

  useEffect(() => {
    const sync = () => {
      const next = resolveCompanyBrand()
      applyCompanyDocumentBrand(next)
      setBrand(next)
    }
    sync()
    return subscribeCompanyBrand(sync)
  }, [])

  const height = size === 'lg' ? 56 : size === 'sm' ? 32 : 36
  return (
    <div className="brand-lockup">
      {brand.logo ? (
        <img src={brand.logo} alt={brand.name} className="brand-logo" style={{ height }} />
      ) : null}
      <div className="brand-copy">
        <div className="brand">{brand.name}</div>
        <div className="brand-subtitle">{subtitle ?? brand.subtitle}</div>
      </div>
    </div>
  )
}
