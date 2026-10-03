import { useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { useAuth } from '../context/AuthContext';
import { applyCompanyTabBrand } from '../utils/companyBranding';

export default function CompanyTabBrand() {
  const { workingCompany } = useApp();
  const { user } = useAuth();
  const company = workingCompany || user?.company || null;

  useEffect(() => {
    applyCompanyTabBrand(company);
  }, [company]);

  return null;
}
