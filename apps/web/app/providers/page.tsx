import { AppFrame } from "@/components/app-frame";
import { ProviderMatrix } from "@/components/provider-matrix";
import { providerCapabilities } from "@crucible/shared/fixtures";

export default function ProvidersPage() {
  return (
    <AppFrame>
      <div className="mb-8">
        <p className="crucible-eyebrow">Capability only, no provider deploy buttons</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Provider status</h1>
      </div>
      <ProviderMatrix providers={providerCapabilities} />
    </AppFrame>
  );
}
