import { useState } from "react";

const LOCAL_LOGOS: Record<string, string> = { justos: "/insurers/justos.svg" };

/** Identidade visual apenas; disponibilidade e condições continuam vindo da API. */
export function InsurerIdentity({ cia, nome, logoUrl }: { cia: string; nome?: string; logoUrl?: string | null }) {
  // Somente assets locais: um logo remoto pode rastrear cada abertura da cotação.
  const safeLogo = logoUrl && /^\/insurers\/[a-zA-Z0-9_-]+\.(svg|png|webp)$/.test(logoUrl) ? logoUrl : null;
  const source = safeLogo || LOCAL_LOGOS[cia.toLowerCase()];
  const [failedSource, setFailedSource] = useState<string | null>(null);
  return <span className="inline-flex items-center gap-3 min-w-0">
    {source && source !== failedSource && <img src={source} alt="" width={72} height={30}
      className="h-8 w-[72px] shrink-0 object-contain" onError={() => setFailedSource(source)} />}
    <span className="capitalize break-words">{nome || cia}</span>
  </span>;
}
