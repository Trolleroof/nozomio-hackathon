import { AppFrame } from "@/components/app-frame";
import { ProviderMatrix } from "@/components/provider-matrix";
import { providerCapabilities } from "@crucible/shared/fixtures";

export default function ProvidersPage() {
  return (
    <AppFrame>
      <div className="mb-8">
        <h1 className="text-2xl font-medium tracking-tight">Provider status</h1>
      </div>
      <ProviderMatrix providers={providerCapabilities} />
    </AppFrame>
  );
}
